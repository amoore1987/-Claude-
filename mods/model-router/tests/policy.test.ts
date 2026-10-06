import { describe, expect, test } from 'claude-code/testing'

import {
  actualCost,
  cacheKey,
  describeModel,
  estimateCost,
  heuristicTier,
  parseTags,
  parseTier,
  planRoute,
  SHAPES,
  shortName,
  type CacheMap,
  type PlanInput,
} from '../hooks/policy'

const NOW = 1_800_000_000_000
const MINUTE = 60_000

function plan(overrides: Partial<PlanInput> = {}): PlanInput {
  return {
    tier: 'light',
    sessionModel: 'claude-opus-5-5',
    sessionEffort: 'xhigh',
    lightModel: 'claude-haiku-4-5',
    standardModel: 'claude-sonnet-5-5',
    ctx: 20_000,
    now: NOW,
    cacheTtlMinutes: 60,
    caches: {},
    unavailable: [],
    minSavingRatio: 0.25,
    ...overrides,
  }
}

function warmOpus(tokens: number, ageMinutes = 1): CacheMap {
  return { [cacheKey('claude-opus-5-5', 'xhigh')]: { tokens, at: NOW - ageMinutes * MINUTE } }
}

describe('describeModel', () => {
  test('reads every spelling of a model id', () => {
    expect(describeModel('claude-opus-5-5')).toEqual(expect.objectContaining({ family: 'opus', version: 5.5, rank: 2 }))
    expect(describeModel('claude-haiku-4-5')).toEqual(expect.objectContaining({ family: 'haiku', version: 4.5, rank: 0 }))
    expect(describeModel('claude-3-5-haiku-20241022')).toEqual(expect.objectContaining({ family: 'haiku', version: 3.5 }))
    expect(describeModel('claude-sonnet-4-20250514')).toEqual(expect.objectContaining({ family: 'sonnet', version: 4 }))
    expect(describeModel('claude-opus-4-1-20250805')).toEqual(expect.objectContaining({ family: 'opus', version: 4.1 }))
    expect(describeModel('us.anthropic.claude-sonnet-4-5-20250929-v1:0')).toEqual(
      expect.objectContaining({ family: 'sonnet', version: 4.5 }),
    )
    expect(describeModel('claude-fable-5-1')).toEqual(expect.objectContaining({ family: 'fable', rank: 3 }))
    expect(describeModel('haiku')?.version).toBe(4.5)
    expect(describeModel('gpt-5')).toBeUndefined()
  })

  test('prices the current generation as the API lists it', () => {
    expect(describeModel('claude-opus-5-5')?.price).toEqual({ input: 4, cacheRead: 0.2, output: 20 })
    expect(describeModel('claude-sonnet-5-5')?.price).toEqual({ input: 2, cacheRead: 0.2, output: 10 })
    expect(describeModel('claude-haiku-4-5')?.price).toEqual({ input: 1, cacheRead: 0.1, output: 5 })
    expect(shortName('claude-opus-5-5')).toBe('opus 5.5')
  })
})

describe('estimateCost', () => {
  test('a warm cache is read, a cold one written', () => {
    const price = { input: 4, cacheRead: 0.2, output: 20 }
    const cold = estimateCost(price, SHAPES.light, 1, 100_000, 0, 2)
    const warm = estimateCost(price, SHAPES.light, 1, 100_000, 100_000, 2)
    expect(warm).toBeLessThan(cold)
    // cold writes 100K at 2x input ($0.80); warm reads it at $0.02
    expect(Math.abs(cold - warm - 0.78)).toBeLessThan(0.001)
  })

  test('actualCost bills the four counters at their rates', () => {
    const price = { input: 1, cacheRead: 0.1, output: 5 }
    const usage = { input_tokens: 1000, output_tokens: 1000, cache_read_input_tokens: 1000, cache_creation_input_tokens: 1000 }
    expect(Math.abs(actualCost(price, usage, 2) - (1 + 0.1 + 2 + 5) / 1000)).toBeLessThan(1e-9)
  })
})

describe('planRoute', () => {
  test('never touches a heavy turn or an unpriceable session model', () => {
    expect(planRoute(plan({ tier: 'heavy' }))).toBeUndefined()
    expect(planRoute(plan({ sessionModel: 'mystery-model' }))).toBeUndefined()
  })

  test('sends a light prompt to haiku when every cache is cold', () => {
    const result = planRoute(plan())
    expect(result?.choice.model).toBe('claude-haiku-4-5')
    expect(result?.choice.effort).toBeUndefined() // Haiku takes no effort parameter
    expect(result?.choice.isStay).toBe(false)
    expect(result?.savingRatio).toBeGreaterThan(0.5)
  })

  test('stays on the session model when its cache is warm and the context is large', () => {
    const result = planRoute(plan({ ctx: 120_000, caches: warmOpus(120_000) }))
    expect(result?.choice.isStay).toBe(true)
    expect(result?.savingRatio).toBe(0)
  })

  test('switches again once the warm cache has aged past the TTL', () => {
    const result = planRoute(plan({ ctx: 120_000, caches: warmOpus(120_000, 61) }))
    expect(result?.choice.model).toBe('claude-haiku-4-5')
  })

  test('a lower effort on the same model is a candidate, but a changed effort loses the cache', () => {
    const result = planRoute(plan({ ctx: 60_000, caches: warmOpus(60_000) }))
    const lowOpus = result?.candidates.find(c => c.model === 'claude-opus-5-5' && c.effort === 'low')
    expect(lowOpus).toBeDefined()
    expect(lowOpus!.cost).toBeGreaterThan(result!.stay.cost)
    expect(result?.choice.isStay).toBe(true)
  })

  test('a standard prompt goes to sonnet, never haiku', () => {
    const result = planRoute(plan({ tier: 'standard' }))
    expect(result?.choice.model).toBe('claude-sonnet-5-5')
    expect(result?.choice.effort).toBe('medium')
    expect(result?.candidates.some(c => c.model === 'claude-haiku-4-5')).toBe(false)
  })

  test('never routes sideways or up, and skips models marked unavailable', () => {
    expect(planRoute(plan({ sessionModel: 'claude-haiku-4-5', sessionEffort: undefined }))?.choice.isStay).toBe(true)
    const sonnetSession = planRoute(plan({ sessionModel: 'claude-sonnet-5-5', tier: 'standard' }))
    expect(sonnetSession?.choice.isStay).toBe(true)
    const noHaiku = planRoute(plan({ unavailable: ['claude-haiku-4-5'] }))
    expect(noHaiku?.choice.model).toBe('claude-sonnet-5-5')
  })

  test('the saving margin keeps marginal switches on the session model', () => {
    const eager = planRoute(plan({ ctx: 40_000, caches: warmOpus(40_000), minSavingRatio: 0 }))
    const careful = planRoute(plan({ ctx: 40_000, caches: warmOpus(40_000), minSavingRatio: 0.9 }))
    expect(careful?.choice.isStay).toBe(true)
    expect(eager!.choice.cost).toBeLessThanOrEqual(eager!.stay.cost)
  })
})

describe('parseTags', () => {
  test('finds a tag anywhere and strips it from the prompt', () => {
    expect(parseTags('[haiku] rename foo to bar')).toEqual({ text: 'rename foo to bar', tag: 'haiku' })
    expect(parseTags('rename foo to bar [light]')).toEqual({ text: 'rename foo to bar', tag: 'light' })
    expect(parseTags('do the [HEAVY] thing')).toEqual({ text: 'do the thing', tag: 'heavy' })
    expect(parseTags('an array[light] index')).toEqual({ text: 'an array[light] index' })
    expect(parseTags('no tag here')).toEqual({ text: 'no tag here' })
  })
})

describe('heuristicTier', () => {
  test('settles the obvious cases without a model', () => {
    expect(heuristicTier('thanks!')).toEqual(expect.objectContaining({ tier: 'light', isConfident: true }))
    expect(heuristicTier('run the tests')).toEqual(expect.objectContaining({ tier: 'light', isConfident: true }))
    expect(heuristicTier('fix the typo in the README')).toEqual(expect.objectContaining({ tier: 'light', isConfident: true }))
    expect(heuristicTier('refactor the auth module to use the new session store')).toEqual(
      expect.objectContaining({ tier: 'heavy', isConfident: true }),
    )
    expect(heuristicTier('x'.repeat(2001))).toEqual(expect.objectContaining({ tier: 'heavy', isConfident: true }))
  })

  test('a go-ahead continues the previous turn, whatever its tier', () => {
    expect(heuristicTier('yes', 'heavy').tier).toBe('heavy')
    expect(heuristicTier('go ahead', 'light').tier).toBe('light')
    expect(heuristicTier('ok', undefined).tier).toBe('heavy')
  })

  test('leaves the rest to the classifier', () => {
    expect(heuristicTier('does this handle unicode?')).toEqual(expect.objectContaining({ tier: 'light', isConfident: false }))
    expect(heuristicTier('add a test for the parser')).toEqual(expect.objectContaining({ tier: 'heavy', isConfident: false }))
  })
})

describe('parseTier', () => {
  test('reads the one word out of a chatty reply', () => {
    expect(parseTier('standard')).toBe('standard')
    expect(parseTier('Grade: Heavy.')).toBe('heavy')
    expect(parseTier('I am not sure')).toBeUndefined()
  })
})
