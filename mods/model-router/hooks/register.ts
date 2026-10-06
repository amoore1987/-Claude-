// model-router: sends each prompt to the cheapest model and effort that can
// handle it, and only when that beats the prompt-cache miss a switch causes.
//
// The flow per prompt:
//   prompt.submit  strips a [haiku]/[light]/[heavy]... tag and remembers it
//   turn.start     records the prompt for its turn
//   turn.step #0   grades the prompt (rules first, a tiny classifier call for
//                  the unclear ones), prices the candidates, picks one, and
//                  rewrites `model`/`effort` on every request of the turn
//   turn.complete  books the real usage, estimates what the session model
//                  would have cost, and keeps running totals in $.store
//
// The policy itself (pricing, cost model, rules, classifier prompt) is pure
// and lives in policy.ts; this file is the plumbing between it and `$`.
// Every helper that takes `$` is a top-level function, as the validator asks.

import type { EngineInterface, PluginOptions, Register, SessionMessage, TurnStepInput, TurnStepResult } from 'claude-code'

import {
  actualCost,
  addUsage,
  cacheKey,
  cacheWriteMultiplier,
  CLASSIFIER_SYSTEM,
  classifierPrompt,
  describeModel,
  effortFor,
  effortMultiplier,
  estimateCost,
  estimateTokens,
  formatUsd,
  heuristicTier,
  isLearnedShapes,
  learnShape,
  parseTags,
  parseTier,
  planRoute,
  shapeFor,
  shortName,
  warmTokens,
  ZERO_USAGE,
  type CacheMap,
  type EffortLike,
  type LearnedShapes,
  type PlanInput,
  type RoutePlan,
  type Tag,
  type Tier,
  type Usage,
} from './policy'

const NAME = 'model-router'
/** What the system prompt and tool list weigh before the first request has been measured. */
const BASELINE_CONTEXT = 20_000
const STATS_KEY = 'stats'
const SHAPES_KEY = 'shapes'
const PREVIOUS_EXCERPT = 400

type Settings = {
  enabled: boolean
  classifier: boolean
  announce: boolean
  lightModel: string
  standardModel: string
  cacheTtlMinutes: number
  minSavingRatio: number
}

type Mode = { kind: 'auto' } | { kind: 'off' } | { kind: 'pin'; model: string; effort: EffortLike }

type Stats = {
  turns: number
  routed: number
  byModel: Record<string, number>
  estSavedUsd: number
  estSpentUsd: number
  classifierCalls: number
  classifierUsd: number
}

type Turn = {
  text: string
  attachments: number
  tag?: Tag
  isDecided: boolean
  tier: Tier
  reason: string
  isRouted: boolean
  model: string
  effort: EffortLike
  sessionModel: string
  sessionEffort: EffortLike
  plan?: RoutePlan
  ctxAtStart: number
  stayWarm: number
  /** What the model that ran the turn held warm when it started. */
  runWarm: number
  steps: number
  usage: Usage
}

/** Everything the hooks share; one per load of the module. */
type State = {
  settings: Settings
  writeMult: number
  ttlMs: number
  mode: Mode
  /** Prompt tokens of the main loop's last request; 0 until one was measured. */
  ctx: number
  lastOutput: number
  caches: CacheMap
  prevTier: Tier | undefined
  pending: { tag?: Tag; attachments: number } | undefined
  turns: Map<string, Turn>
  unavailable: Set<string>
  stats: Stats
  shapes: LearnedShapes
}

function emptyStats(): Stats {
  return { turns: 0, routed: 0, byModel: {}, estSavedUsd: 0, estSpentUsd: 0, classifierCalls: 0, classifierUsd: 0 }
}

function readSettings(options: PluginOptions | undefined): Settings {
  const o = options ?? {}
  const bool = (key: string, fallback: boolean): boolean => (typeof o[key] === 'boolean' ? (o[key] as boolean) : fallback)
  const str = (key: string, fallback: string): string => {
    const value = o[key]
    return typeof value === 'string' && value.trim() !== '' ? value.trim() : fallback
  }
  const num = (key: string, fallback: number, min: number, max: number): number => {
    const raw = o[key]
    const value = Number(raw)
    return typeof raw !== 'boolean' && Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : fallback
  }
  return {
    enabled: bool('enabled', true),
    classifier: bool('classifier', true),
    announce: bool('announce', true),
    lightModel: str('lightModel', 'claude-haiku-4-5'),
    standardModel: str('standardModel', 'claude-sonnet-5-5'),
    cacheTtlMinutes: num('cacheTtlMinutes', 60, 1, 120),
    minSavingRatio: num('minSavingPercent', 25, 0, 90) / 100,
  }
}

function isStats(value: unknown): value is Stats {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return typeof v.turns === 'number' && typeof v.routed === 'number' && typeof v.estSavedUsd === 'number'
}

/** The previous assistant answer, abridged, as context for the classifier. */
function lastAssistantText(rows: readonly SessionMessage[]): string | undefined {
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    const row = rows[i]
    if (row === undefined || row.role !== 'assistant') continue
    const text = row.text.trim()
    if (text === '') continue
    return text.length > PREVIOUS_EXCERPT ? `${text.slice(0, PREVIOUS_EXCERPT)} [...]` : text
  }
  return undefined
}

function effortLabel(effort: EffortLike): string {
  return effort === undefined ? 'default effort' : `${effort} effort`
}

function newTurn(text: string, queued: State['pending']): Turn {
  return {
    text,
    attachments: queued?.attachments ?? 0,
    tag: queued?.tag,
    isDecided: false,
    tier: 'heavy',
    reason: '',
    isRouted: false,
    model: '',
    effort: undefined,
    sessionModel: '',
    sessionEffort: undefined,
    ctxAtStart: 0,
    stayWarm: 0,
    runWarm: 0,
    steps: 0,
    usage: ZERO_USAGE,
  }
}

function contextNow(state: State): number {
  return state.ctx > 0 ? state.ctx + state.lastOutput : BASELINE_CONTEXT
}

function planBase(state: State, turn: Turn, now: number): Omit<PlanInput, 'tier'> {
  return {
    sessionModel: turn.sessionModel,
    sessionEffort: turn.sessionEffort,
    lightModel: state.settings.lightModel,
    standardModel: state.settings.standardModel,
    ctx: turn.ctxAtStart,
    now,
    cacheTtlMinutes: state.settings.cacheTtlMinutes,
    caches: state.caches,
    unavailable: [...state.unavailable],
    minSavingRatio: state.settings.minSavingRatio,
    shapes: state.shapes,
  }
}

function routedRequest(e: TurnStepInput, turn: Turn): TurnStepInput {
  const request: TurnStepInput = { ...e, model: turn.model }
  if (turn.effort !== undefined) request.effort = turn.effort
  else delete request.effort
  return request
}

function modeText(state: State): string {
  const mode = state.mode
  switch (mode.kind) {
    case 'auto':
      return 'auto'
    case 'off':
      return 'off'
    case 'pin':
      return `pinned to ${mode.model} at ${effortLabel(mode.effort)}`
  }
}

function statsText(state: State): string {
  const stats = state.stats
  const models = Object.entries(stats.byModel)
    .map(([model, n]) => `${shortName(model)} ×${n}`)
    .join(', ')
  return [
    `Turns: ${stats.turns}, routed away from the session model: ${stats.routed}${models === '' ? '' : ` (${models})`}.`,
    `Estimated saving: ${formatUsd(stats.estSavedUsd)} (spent ${formatUsd(stats.estSpentUsd)} on routed turns instead of about ${formatUsd(stats.estSpentUsd + stats.estSavedUsd)}).`,
    `Classifier: ${stats.classifierCalls} call(s), about ${formatUsd(stats.classifierUsd)}.`,
    'Savings are estimates from list prices and the measured token counts.',
  ].join('\n')
}

function shapesText(state: State): string {
  const parts: string[] = []
  for (const tier of ['light', 'standard'] as const) {
    for (const [family, shape] of Object.entries(state.shapes[tier] ?? {})) {
      if (shape === undefined) continue
      parts.push(`${tier} on ${family}: ${shape.steps.toFixed(1)} steps, ${Math.round(shape.out)} output tokens (${shape.n} turn${shape.n === 1 ? '' : 's'})`)
    }
  }
  return parts.length === 0 ? 'Turn shapes: none observed yet; pricing from priors.' : `Turn shapes observed: ${parts.join('; ')}.`
}

function statusLine($: EngineInterface, text: string | undefined): void {
  $.ui.status(text)
}

async function loadStats($: EngineInterface, state: State): Promise<void> {
  const stored = await $.store.get(STATS_KEY)
  if (isStats(stored)) state.stats = { ...emptyStats(), ...stored }
  const shapes = await $.store.get(SHAPES_KEY)
  if (isLearnedShapes(shapes)) state.shapes = shapes
}

async function saveStats($: EngineInterface, state: State): Promise<void> {
  await $.store.set(STATS_KEY, state.stats)
  await $.store.set(SHAPES_KEY, state.shapes)
}

/** Folds a finished, graded turn into the shape its tier takes on the family that ran it. */
function learn(state: State, turn: Turn): void {
  if (turn.plan === undefined || turn.tier === 'heavy' || turn.steps === 0) return
  const ran = describeModel(turn.model)
  if (ran === undefined) return
  const u = turn.usage
  const coldPrefix = Math.max(0, turn.ctxAtStart - turn.runWarm)
  const out = u.output_tokens / effortMultiplier(turn.effort)
  const fresh = Math.max(0, (u.input_tokens + u.cache_creation_input_tokens - coldPrefix - u.output_tokens) / turn.steps)
  const byFamily = state.shapes[turn.tier] ?? {}
  byFamily[ran.family] = learnShape(byFamily[ran.family], { steps: turn.steps, fresh, out })
  state.shapes[turn.tier] = byFamily
}

/** Grades the prompt: rules first, the classifier for what they cannot settle. */
async function grade($: EngineInterface, state: State, turn: Turn, now: number): Promise<{ tier: Tier; reason: string }> {
  const rule = heuristicTier(turn.text, state.prevTier)
  const hasClassifier = state.settings.classifier && !state.unavailable.has(state.settings.lightModel.toLowerCase())
  if (rule.isConfident || !hasClassifier) return { tier: rule.tier, reason: rule.reason }

  // No point paying for a grade when no tier could switch anyway.
  const base = planBase(state, turn, now)
  const couldSwitch = (['light', 'standard'] as const).some(tier => {
    const plan = planRoute({ ...base, tier })
    return plan !== undefined && !plan.choice.isStay
  })
  if (!couldSwitch) return { tier: 'heavy', reason: 'no cheaper route while the cache is warm' }

  let previous: string | undefined
  try {
    previous = lastAssistantText(await $.session.messages())
  } catch {
    previous = undefined
  }
  const reply = await $.model.complete({
    model: state.settings.lightModel,
    system: CLASSIFIER_SYSTEM,
    prompt: classifierPrompt(turn.text, previous, turn.attachments),
    maxTokens: 8,
    effort: 'low',
    timeoutMs: 8000,
  })
  state.stats.classifierCalls += 1
  if (reply.isAnswered) {
    const light = describeModel(state.settings.lightModel)
    if (light !== undefined) state.stats.classifierUsd += actualCost(light.price, reply.usage, state.writeMult)
    const tier = parseTier(reply.text)
    if (tier !== undefined) return { tier, reason: 'classifier' }
    return { tier: rule.tier, reason: `classifier said "${reply.text.trim().slice(0, 24)}"; ${rule.reason}` }
  }
  const detail = reply.reason === 'api-error' ? `api error ${reply.status ?? ''} ${reply.error}`.trim() : reply.reason
  return { tier: rule.tier, reason: `classifier ${detail}; ${rule.reason}` }
}

function announce($: EngineInterface, state: State, turn: Turn): void {
  const plan = turn.plan
  if (turn.isRouted) {
    const costs =
      plan === undefined ? '' : ` Est. ${formatUsd(plan.choice.cost)} vs ${formatUsd(plan.stay.cost)} on ${shortName(turn.sessionModel)}.`
    const line = `${NAME} → ${shortName(turn.model)} at ${effortLabel(turn.effort)} (${turn.tier}: ${turn.reason}).${costs}`
    if (state.settings.announce) $.ui.log(line)
    else $.ui.log(line, { to: 'debug' })
    const estimate = plan === undefined ? '' : ` · est. ${formatUsd(plan.choice.cost)} vs ${formatUsd(plan.stay.cost)}`
    statusLine($, `router → ${shortName(turn.model)} · ${turn.tier}${estimate}`)
    return
  }
  let why = turn.reason
  if (plan !== undefined) {
    const best = plan.candidates.reduce((min, c) => Math.min(min, c.cost), plan.stay.cost)
    why += `; switching would not save ${Math.round(state.settings.minSavingRatio * 100)}% (best ${formatUsd(best)} vs ${formatUsd(plan.stay.cost)})`
  }
  $.ui.log(`${NAME}: stays on ${shortName(turn.sessionModel)} (${turn.tier}: ${why})`, { to: 'debug' })
  statusLine($, `router: ${shortName(turn.sessionModel)} · ${turn.tier}${plan !== undefined ? ' · cache warm, no switch' : ''}`)
}

/** Settles where the turn runs, once, at its first request. */
async function decide($: EngineInterface, state: State, turn: Turn, e: TurnStepInput): Promise<void> {
  turn.isDecided = true
  turn.sessionModel = e.model
  turn.sessionEffort = e.effort
  turn.model = e.model
  turn.effort = e.effort
  turn.ctxAtStart = contextNow(state) + estimateTokens(turn.text)
  const now = await $.clock.now()
  turn.stayWarm = warmTokens(state.caches, e.model, e.effort, now, state.ttlMs)

  const mode = state.mode
  if (mode.kind === 'off') {
    turn.tier = 'heavy'
    turn.reason = 'routing off'
    return
  }
  const session = describeModel(e.model)

  if (mode.kind === 'pin') {
    const pinned = describeModel(mode.model)
    turn.tier = 'heavy'
    if (session !== undefined && pinned !== undefined && pinned.rank < session.rank && !state.unavailable.has(pinned.id.toLowerCase())) {
      turn.isRouted = true
      turn.model = pinned.id
      turn.effort = mode.effort
      turn.reason = 'pinned by /route'
    } else {
      turn.reason = `pin ignored: ${mode.model} is not below ${e.model}`
    }
    announce($, state, turn)
    return
  }

  // An explicit model tag skips the grade and the cost check: the person decided.
  if (turn.tag === 'haiku' || turn.tag === 'sonnet') {
    const wanted = turn.tag === 'haiku' ? state.settings.lightModel : state.settings.standardModel
    const target = describeModel(wanted)
    const tier = turn.tag === 'haiku' ? 'light' : 'standard'
    turn.tier = tier
    if (session !== undefined && target !== undefined && target.rank < session.rank) {
      turn.isRouted = true
      turn.model = target.id
      turn.effort = effortFor(target, tier)
      turn.reason = `[${turn.tag}] tag`
    } else {
      turn.reason = `[${turn.tag}] tag ignored: not below ${e.model}`
    }
    announce($, state, turn)
    return
  }

  if (turn.tag === 'light' || turn.tag === 'standard' || turn.tag === 'heavy' || turn.tag === 'default') {
    turn.tier = turn.tag === 'default' ? 'heavy' : turn.tag
    turn.reason = `[${turn.tag}] tag`
  } else {
    const graded = await grade($, state, turn, now)
    turn.tier = graded.tier
    turn.reason = graded.reason
  }
  if (turn.attachments > 0 && turn.tier === 'light') {
    turn.tier = 'standard'
    turn.reason += '; attachments raise it to standard'
  }

  const plan = planRoute({ ...planBase(state, turn, now), tier: turn.tier })
  turn.plan = plan
  if (plan !== undefined && !plan.choice.isStay) {
    turn.isRouted = true
    turn.model = plan.choice.model
    turn.effort = plan.choice.effort
  }
  turn.runWarm = warmTokens(state.caches, turn.model, turn.effort, now, state.ttlMs)
  announce($, state, turn)
}

/** Books one request's usage: the context size, the model's warm prefix, the turn's totals. */
async function observe(
  $: EngineInterface,
  state: State,
  turn: Turn | undefined,
  request: TurnStepInput,
  result: TurnStepResult,
  wasAborted: boolean,
): Promise<void> {
  const usage = result.usage
  if (usage !== null) {
    const prompt = usage.input_tokens + usage.cache_read_input_tokens + usage.cache_creation_input_tokens
    state.ctx = prompt
    state.lastOutput = usage.output_tokens
    state.caches[cacheKey(request.model, request.effort)] = { tokens: prompt, at: await $.clock.now() }
    if (turn !== undefined) {
      turn.steps += 1
      turn.usage = addUsage(turn.usage, usage)
    }
    return
  }
  if (turn?.isRouted === true && turn.steps === 0 && result.stopReason === null && !wasAborted) {
    state.unavailable.add(turn.model.toLowerCase())
    $.ui.toast(`${NAME}: ${turn.model} did not answer; not routing to it again this session`)
    $.ui.log(
      `${NAME}: ${turn.model} returned no response at the turn's first request; marked unavailable. /route check tests it, /route auto clears the mark.`,
    )
  }
}

/** Closes the turn's books: the real spend, the counterfactual, the running totals. */
async function settle($: EngineInterface, state: State, turn: Turn): Promise<void> {
  const stats = state.stats
  stats.turns += 1
  let line: string
  if (turn.isRouted) {
    stats.routed += 1
    stats.byModel[turn.model] = (stats.byModel[turn.model] ?? 0) + 1
    const routed = describeModel(turn.model)
    const session = describeModel(turn.sessionModel)
    if (routed !== undefined && session !== undefined && turn.steps > 0) {
      const spent = actualCost(routed.price, turn.usage, state.writeMult)
      const tier = turn.tier === 'heavy' ? 'standard' : turn.tier
      // What the session model would have done: its own observed shape for the
      // tier once known, else this turn's shape with the output scaled by effort.
      const known = shapeFor(tier, session.family, state.shapes)
      const shape = known.isLearned
        ? known.shape
        : { steps: turn.steps, fresh: known.shape.fresh, out: turn.usage.output_tokens / effortMultiplier(turn.effort) }
      const counterfactual = estimateCost(
        session.price,
        shape,
        effortMultiplier(turn.sessionEffort),
        turn.ctxAtStart,
        turn.stayWarm,
        state.writeMult,
      )
      const saved = counterfactual - spent
      stats.estSavedUsd += saved
      stats.estSpentUsd += spent
      line = `router: ${shortName(turn.model)} took it · est. saved ${formatUsd(saved)} · session ${formatUsd(stats.estSavedUsd)}`
    } else {
      line = `router: ${shortName(turn.model)} took it · session est. saved ${formatUsd(stats.estSavedUsd)}`
    }
  } else {
    line = `router: ${shortName(turn.sessionModel)} · ${turn.tier} · session est. saved ${formatUsd(stats.estSavedUsd)}`
  }
  learn(state, turn)
  statusLine($, line)
  await saveStats($, state)
}

async function report($: EngineInterface, state: State): Promise<string> {
  const now = await $.clock.now()
  const s = state.settings
  const warm = Object.entries(state.caches)
    .filter(([, entry]) => now - entry.at < state.ttlMs)
    .map(([key, entry]) => `${key.replace('|', ' @ ').replace(/ @ $/, '')}: ${Math.round(entry.tokens / 1000)}K tokens`)
  return [
    `${NAME}: ${modeText(state)}.`,
    `light → ${s.lightModel} (low effort), standard → ${s.standardModel} (medium effort), heavy → the session model untouched.`,
    `Context now: about ${Math.round(contextNow(state) / 1000)}K tokens. Warm caches: ${warm.length === 0 ? 'none' : warm.join('; ')}.`,
    `Cache TTL ${s.cacheTtlMinutes} min, switch only when a turn gets ≥${Math.round(s.minSavingRatio * 100)}% cheaper, classifier ${s.classifier ? 'on' : 'off'}.`,
    state.unavailable.size === 0 ? '' : `Marked unavailable this session: ${[...state.unavailable].join(', ')}.`,
    shapesText(state),
    statsText(state),
    'Tags: [haiku] [sonnet] [light] [standard] [heavy] [default] anywhere in a prompt. Commands: /route auto|off|haiku|sonnet|stats|reset|check.',
  ]
    .filter(part => part !== '')
    .join('\n')
}

async function check($: EngineInterface, state: State): Promise<string> {
  const lines: string[] = []
  for (const model of [state.settings.lightModel, state.settings.standardModel]) {
    const reply = await $.model.complete({ model, prompt: 'Reply with the word ok.', maxTokens: 4, timeoutMs: 15000 })
    if (reply.isAnswered) {
      state.unavailable.delete(model.toLowerCase())
      lines.push(`${model}: ok`)
    } else {
      const detail = reply.reason === 'api-error' ? `${reply.error}${reply.status === null ? '' : ` (${reply.status})`}` : reply.reason
      lines.push(`${model}: ${detail}`)
    }
  }
  return lines.join('\n')
}

async function runCommand($: EngineInterface, state: State, args: string): Promise<{ text: string }> {
  const s = state.settings
  switch (args.trim().toLowerCase()) {
    case '':
      return { text: await report($, state) }
    case 'auto':
    case 'on':
      state.mode = { kind: 'auto' }
      state.unavailable.clear()
      statusLine($, 'router: auto')
      return { text: `${NAME}: auto. Prompts are graded and routed when a switch pays.` }
    case 'off':
      state.mode = { kind: 'off' }
      statusLine($, 'router: off')
      return { text: `${NAME}: off. Every turn runs on the session model until /route auto.` }
    case 'haiku':
    case 'sonnet': {
      const tier = args.trim().toLowerCase() === 'haiku' ? 'light' : 'standard'
      const model = tier === 'light' ? s.lightModel : s.standardModel
      const info = describeModel(model)
      const effort = info === undefined ? undefined : effortFor(info, tier)
      state.mode = { kind: 'pin', model, effort }
      statusLine($, `router: pinned ${shortName(model)}`)
      return { text: `${NAME}: every turn runs on ${model} at ${effortLabel(effort)} until /route auto.` }
    }
    case 'stats':
      return { text: statsText(state) }
    case 'reset':
      state.stats = emptyStats()
      await saveStats($, state)
      return { text: `${NAME}: stats reset.` }
    case 'check':
      return { text: await check($, state) }
    default:
      return { text: `${NAME}: unknown argument "${args.trim()}". Use /route [auto|off|haiku|sonnet|stats|reset|check].` }
  }
}

export const register: Register = (on, options) => {
  const settings = readSettings(options)
  const state: State = {
    settings,
    writeMult: cacheWriteMultiplier(settings.cacheTtlMinutes),
    ttlMs: settings.cacheTtlMinutes * 60_000,
    mode: settings.enabled ? { kind: 'auto' } : { kind: 'off' },
    ctx: 0,
    lastOutput: 0,
    caches: {},
    prevTier: undefined,
    pending: undefined,
    turns: new Map(),
    unavailable: new Set(),
    stats: emptyStats(),
    shapes: {},
  }

  on('session.start', async ($, e, next) => {
    await loadStats($, state)
    await $.command.register({
      name: 'route',
      description: 'Model router: status, auto/off, pin haiku or sonnet, stats, reset, check',
      argumentHint: '[auto|off|haiku|sonnet|stats|reset|check]',
    })
    statusLine($, `router: ${modeText(state)}`)
    return next(e)
  })

  on('prompt.submit', ($, e, next) => {
    const parsed = parseTags(e.text)
    // A prompt typed over a running turn joins that turn; only a fresh one starts the next.
    if (e.turnId === undefined) state.pending = { tag: parsed.tag, attachments: e.attachments?.length ?? 0 }
    return parsed.tag === undefined || parsed.text === '' ? next(e) : next({ ...e, text: parsed.text })
  }).catch(($, e, next) => next(e))

  on('turn.start', ($, e, next) => {
    const queued = state.pending
    state.pending = undefined
    if (e.text !== '') state.turns.set(e.turnId, newTurn(e.text, queued))
    return next(e)
  })

  on('turn.step', async function* ($, e, next) {
    if (e.agentId !== undefined) return yield* next(e)
    const turn = state.turns.get(e.turnId)
    if (turn !== undefined && e.index === 0 && !turn.isDecided) {
      try {
        await decide($, state, turn, e)
      } catch (error) {
        turn.isRouted = false
        turn.reason = `decision failed: ${error instanceof Error ? error.message : String(error)}`
        $.ui.log(`${NAME}: ${turn.reason}`, { to: 'debug' })
      }
    }
    const request = turn?.isRouted === true ? routedRequest(e, turn) : e
    const result = yield* next(request)
    await observe($, state, turn, request, result, next.signal.aborted)
    return result
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined) {
      const turn = state.turns.get(e.turnId)
      if (turn !== undefined) {
        state.turns.delete(e.turnId)
        state.prevTier = turn.tier
        await settle($, state, turn)
      }
    }
    return next(e)
  })

  on('session.compact', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId === undefined && result.skip === undefined) {
      // The prefix changed under every model: no cache survives it.
      state.caches = {}
      state.ctx = result.tokensAfter ?? 0
      state.lastOutput = 0
    }
    return result
  })

  on('session.end', ($, e, next) => {
    if (e.reason === 'clear') {
      state.caches = {}
      state.ctx = 0
      state.lastOutput = 0
      state.prevTier = undefined
      state.pending = undefined
      state.turns.clear()
    }
    return next(e)
  })

  on('command.run', { command: 'route' }, ($, e) => runCommand($, state, e.args)).catch(() => ({
    text: `${NAME}: that command failed; the debug log has the reason.`,
  }))
}
