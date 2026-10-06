import type { On, TurnStepInput, TurnStepResult } from 'claude-code'
import { describe, expect, mock, test, type Engine } from 'claude-code/testing'

const NOW = 1_800_000_000_000
const OPUS = 'claude-opus-5-5'
const HAIKU = 'claude-haiku-4-5'
const SONNET = 'claude-sonnet-5-5'
const COMPOSER = { kind: 'composer' } as const
const PRESENTATION = { isFullscreen: false, columns: 80 }

type Seen = { model: string; effort: unknown; turnId: string; index: number }

/**
 * The engine beneath the plugin, in memory: every `$` call the mod makes is
 * answered here, and what reaches the bottom of `turn.step` is recorded.
 */
function world(on: On, options: { classifierReply?: string; promptTokens?: number } = {}) {
  const seen: Seen[] = []
  const graded: string[] = []
  const logs: string[] = []
  const store = new Map<string, unknown>()
  mock.clock(on, { now: NOW })
  on('store.get', ($, e) => ({ value: store.get(e.key) }))
  on('store.set', ($, e) => {
    store.set(e.key, e.value)
    return { value: undefined }
  })
  on('ui.log', ($, e) => {
    logs.push(e.text)
    return { value: undefined }
  })
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('command.register', ($, e) => ({ value: { command: e.name } }))
  on('session.messages', () => ({ value: [] }))
  on('model.complete', ($, e) => {
    graded.push(e.prompt)
    return {
      value: {
        isAnswered: true as const,
        text: options.classifierReply ?? 'standard',
        usage: { input_tokens: 300, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 },
      },
    }
  })
  on('prompt.submit', ($, e) => ({ text: e.text }))
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('turn.complete', ($, e) => ({ text: e.answer }))
  on('turn.step', async function* ($, e) {
    seen.push({ model: e.model, effort: e.effort, turnId: e.turnId, index: e.index })
    yield { kind: 'text', index: 0, text: 'ok' }
    const result: TurnStepResult = {
      turnId: e.turnId,
      index: e.index,
      answer: 'ok',
      toolUses: [],
      stopReason: 'end_turn',
      usage: {
        model: e.model,
        input_tokens: 0,
        output_tokens: 500,
        cache_read_input_tokens: 0,
        cache_creation_input_tokens: options.promptTokens ?? 20_000,
      },
    }
    return result
  })
  return { seen, graded, logs, store }
}

async function drain(stream: AsyncGenerator<unknown, TurnStepResult>): Promise<TurnStepResult> {
  let next = await stream.next()
  while (!next.done) next = await stream.next()
  return next.value
}

/** One whole main-loop turn: start, one step, complete. */
async function turn($: Engine, text: string, turnId: string, step: Partial<TurnStepInput> = {}): Promise<void> {
  await $.turn.start({ text, turnId })
  const input: TurnStepInput = { turnId, index: 0, model: OPUS, effort: 'xhigh', messageCount: 1, ...step }
  const result = await drain($.turn.step(input))
  await $.turn.complete({
    reason: 'answer',
    answer: result.answer,
    durationMs: 10,
    isAborted: false,
    turnId,
    ...(result.usage === null ? {} : { usage: result.usage }),
  })
}

async function route($: Engine, args: string): Promise<string> {
  const result = await $.command.run({ command: 'route', args, origin: COMPOSER, presentation: PRESENTATION })
  return result.text ?? ''
}

describe('model-router', () => {
  test('a trivial prompt on a fresh session goes to the light model at low effort', async ($, on) => {
    const w = world(on)
    await turn($, 'run the tests', 't1')
    expect(w.seen).toHaveLength(1)
    expect(w.seen[0]).toMatchObject({ model: HAIKU, turnId: 't1', index: 0 })
    expect(w.seen[0]?.effort).toBeUndefined()
    expect(w.graded).toHaveLength(0)
    expect(w.logs.some(line => line.includes('→ haiku 4.5'))).toBe(true)
    const stats = w.store.get('stats') as { turns: number; routed: number; estSavedUsd: number }
    expect(stats.turns).toBe(1)
    expect(stats.routed).toBe(1)
    expect(stats.estSavedUsd).toBeGreaterThan(0)
  })

  test('a heavy prompt is never touched', async ($, on) => {
    const w = world(on)
    await turn($, 'refactor the auth module so sessions survive a restart', 't1')
    expect(w.seen[0]).toMatchObject({ model: OPUS, effort: 'xhigh' })
    expect(w.graded).toHaveLength(0)
  })

  test('every step of a routed turn runs on the same model', async ($, on) => {
    const w = world(on)
    await $.turn.start({ text: 'run the tests', turnId: 't1' })
    for (let index = 0; index < 3; index += 1) {
      await drain($.turn.step({ turnId: 't1', index, model: OPUS, effort: 'xhigh', messageCount: 1 + index }))
    }
    expect(w.seen.map(s => s.model)).toEqual([HAIKU, HAIKU, HAIKU])
  })

  test('the classifier grades what the rules cannot, and its grade routes the turn', async ($, on) => {
    const w = world(on, { classifierReply: 'standard' })
    await turn($, 'add a test for the parser', 't1')
    expect(w.graded).toHaveLength(1)
    expect(w.graded[0]).toContain('add a test for the parser')
    expect(w.seen[0]).toMatchObject({ model: SONNET, effort: 'medium' })
  })

  test('a large warm cache keeps the turn home without paying for a grade', async ($, on) => {
    const w = world(on, { promptTokens: 150_000 })
    await turn($, 'investigate why the build is flaky', 't1') // heavy: leaves opus warm at 150K
    await turn($, 'add a test for the parser', 't2')
    expect(w.graded).toHaveLength(0)
    expect(w.seen[1]).toMatchObject({ model: OPUS, effort: 'xhigh' })
  })

  test('a go-ahead after heavy work stays on the session model', async ($, on) => {
    const w = world(on)
    await turn($, 'investigate why the build is flaky', 't1')
    await turn($, 'yes', 't2')
    expect(w.seen[1]).toMatchObject({ model: OPUS, effort: 'xhigh' })
  })

  test('a [haiku] tag is stripped from the prompt and decides the model', async ($, on) => {
    const w = world(on)
    const entered = await $.prompt.submit({ text: '[haiku] what time zone does the server use?', wait: false, origin: COMPOSER })
    expect(entered).toMatchObject({ text: 'what time zone does the server use?' })
    await turn($, 'what time zone does the server use?', 't1')
    expect(w.seen[0]).toMatchObject({ model: HAIKU })
    expect(w.seen[0]?.effort).toBeUndefined()
    expect(w.graded).toHaveLength(0)
  })

  test('a [heavy] tag keeps a trivial prompt on the session model', async ($, on) => {
    const w = world(on)
    await $.prompt.submit({ text: 'run the tests [heavy]', wait: false, origin: COMPOSER })
    await turn($, 'run the tests', 't1')
    expect(w.seen[0]).toMatchObject({ model: OPUS, effort: 'xhigh' })
  })

  test('/route off and /route auto switch routing for the session', async ($, on) => {
    const w = world(on, { promptTokens: 2_000 })
    expect(await route($, 'off')).toContain('off')
    await turn($, 'run the tests', 't1')
    expect(w.seen[0]).toMatchObject({ model: OPUS })
    expect(await route($, 'auto')).toContain('auto')
    await turn($, 'run the tests', 't2')
    expect(w.seen[1]).toMatchObject({ model: HAIKU })
  })

  test('/route haiku pins every turn, and /route reports it', async ($, on) => {
    const w = world(on)
    await route($, 'haiku')
    await turn($, 'redesign the whole data model', 't1')
    expect(w.seen[0]).toMatchObject({ model: HAIKU })
    expect(w.seen[0]?.effort).toBeUndefined()
    expect(await route($, '')).toContain('pinned to claude-haiku-4-5')
  })

  test('the mod learns the shape of the turns it watches', async ($, on) => {
    const w = world(on)
    await turn($, 'run the tests', 't1')
    await turn($, 'git status', 't2')
    const shapes = w.store.get('shapes') as { light?: { haiku?: { n: number; steps: number } } }
    expect(shapes.light?.haiku?.n).toBe(2)
    expect(shapes.light?.haiku?.steps).toBe(1)
    expect(await route($, '')).toContain('light on haiku')
  })

  test('subagent steps are left alone', async ($, on) => {
    const w = world(on)
    await drain($.turn.step({ turnId: 'sub', index: 0, model: OPUS, effort: 'high', messageCount: 1, agentId: 'agent-1' }))
    expect(w.seen[0]).toMatchObject({ model: OPUS, effort: 'high' })
  })

  test('a session model already at the bottom is never routed', async ($, on) => {
    const w = world(on)
    await turn($, 'run the tests', 't1', { model: HAIKU, effort: undefined })
    expect(w.seen[0]).toMatchObject({ model: HAIKU })
  })

  test('routing is off when the option says so', { options: { enabled: false } }, async ($, on) => {
    const w = world(on)
    await turn($, 'run the tests', 't1')
    expect(w.seen[0]).toMatchObject({ model: OPUS, effort: 'xhigh' })
  })
})
