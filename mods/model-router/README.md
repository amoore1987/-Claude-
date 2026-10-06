# model-router

A Claude Code mod that sends each prompt to the cheapest model and effort that
can handle it. It runs on every prompt you type, grades it, and rewrites the
model on that turn's API requests. It switches only when the switch beats the
prompt-cache miss it causes, so it never makes a turn more expensive than
leaving it alone.

## Install

From a terminal session of Claude Code:

```
/plugin install model-router --marketplace amoore1987/-Claude-
```

Answer `y` to add the marketplace, pick the user scope, and it is active in
that session and every later one. To run it from a checkout instead:

```
claude --plugin-dir /path/to/-Claude-/mods/model-router
```

## What it does on each prompt

1. **Tags first.** `[haiku]`, `[sonnet]`, `[light]`, `[standard]`, `[heavy]` or
   `[default]` anywhere in a prompt decides the turn and is stripped before the
   model reads it. `[haiku]` and `[sonnet]` name the model outright; the tier
   tags still go through the cost check. Routes to Sonnet run at medium
   effort, to Haiku with no effort setting (Haiku 4.5 takes none).
2. **Rules next, for free.** Closing remarks and git or test commands are
   light. Heavy keywords (refactor, debug, migrate, security, "why does"...)
   and prompts over 2000 characters are heavy. A bare go-ahead ("yes", "do it",
   "continue") keeps the previous turn's tier, so an approved plan is not
   executed by a smaller model.
3. **A classifier for the rest.** Anything the rules cannot settle goes to the
   light model with a short grading prompt and the previous answer's first
   lines (one call, a few hundred tokens, about a tenth of a cent). It is
   skipped entirely when the cost check below could not switch anyway.
4. **The cost check.** For the tier, the candidates are the configured light
   or standard model, the session model at a lower effort, and the session
   model as is. Each is priced for the expected turn, including what a switch
   costs: prompt caches are per model, and a changed effort invalidates the
   messages cache, so a cold model re-writes the whole conversation. The
   cheapest wins, and only if it saves at least the configured margin.
5. **One decision per turn.** Every request of the turn runs on the chosen
   model, so tool loops never flip models halfway. Subagents are left alone;
   they pick their own model. Heavy turns are never touched, not even their
   effort.

Expected turn shapes start from priors and are learned from the turns the mod
watches (steps, output tokens, per tier and model family), so the estimates
calibrate to how you actually work. Learned shapes and running totals persist
across sessions.

## What to expect

- **Fresh session, after a long pause, or right after compaction:** trivial
  prompts go to Haiku, well-specified work to Sonnet. This is where most of the
  saving is.
- **Deep in a long session with a warm cache:** most prompts stay on the
  session model, because re-reading a 100K-token conversation on Haiku costs
  more than answering from the session model's cache. The status line says
  `cache warm, no switch` when that is the reason.
- **Never routes up.** If your session model is already Haiku or Sonnet, the
  mod only watches.

## Commands and feedback

- `/route` shows the mode, the models, the context size, which caches are
  warm, learned turn shapes and the running totals.
- `/route off` and `/route auto` turn routing off and on for the session.
- `/route haiku` and `/route sonnet` pin every turn to that model until
  `/route auto`.
- `/route stats` and `/route reset` show and clear the totals.
- `/route check` sends one tiny request to each configured model and reports
  whether your account can use them.

Each routed turn writes one dim transcript line naming the model, the tier,
the reason, and the estimated cost against the session model. The status line
under the prompt keeps the latest route and the session's estimated saving.
Savings are estimates from list prices and measured token counts, and can be
negative for a turn that grew larger than its tier predicted.

## Options

Set in `/config` or at install:

| Option | Default | Meaning |
| --- | --- | --- |
| `enabled` | true | Route at all. `/route off` and `/route auto` override it for one session. |
| `classifier` | true | Ask the light model to grade unclear prompts. Off: only obvious prompts are routed. |
| `announce` | true | Write the per-turn transcript line. Off: debug log only. |
| `lightModel` | `claude-haiku-4-5` | Model for light turns (no effort setting on the Haiku family, low effort elsewhere). |
| `standardModel` | `claude-sonnet-5-5` | Model for standard turns, at medium effort. |
| `cacheTtlMinutes` | 60 | How long a model's prompt cache stays warm. 60 on most Claude Code plans, 5 in overage. Lower values switch more eagerly. |
| `minSavingPercent` | 25 | Switch only when the turn gets at least this much cheaper. |

## Caveats

- Prices are list prices per model family, with cache writes at 2x input for a
  one-hour TTL and 1.25x for five minutes. Edit `priceFor` in `hooks/policy.ts`
  if yours differ. On a subscription the dollar figures stand in for usage
  quota; the ratios still hold.
- A grade is a judgment call. If a small model fumbles a turn, say so with a
  `[heavy]` tag or `/route off`, and prefer a prompt that names what you want.
- A model your account cannot use fails its first request. The mod then stops
  routing to it for the session and says so; `/route check` tests the
  configured models up front.
- Hot-reloading the mod while developing it forgets which caches are warm; the
  next measured request corrects it.

## Development

```
claude plugin validate mods/model-router
claude plugin test mods/model-router
```

`hooks/policy.ts` is pure (pricing, cost model, rules, classifier prompt) and
`hooks/register.ts` is the plumbing between it and the engine. The tests cover
both: the policy directly, and the hooks through the engine's own `$`.
