# Architecture

## The problem with the obvious design

The intuitive way to build a multi-agent trading desk is a swarm: a coordinator
that keeps several specialist agents in conversation, passing observations around
until a consensus emerges. It is intuitive and it does not work, for three reasons
that show up in week one.

**Agents in conversation lose the thread.** Every handoff is prose, prose is lossy,
and by the fourth exchange nobody can say which claim came from data and which came
from another agent's summary of data.

**Nothing is replayable.** When Tuesday's watchlist turns out to have been wrong,
you want to re-run the flow analysis against Tuesday's exact bytes and find out
whether the analysis was bad or the data was thin. A chat log cannot do that.

**The costs are unbounded.** An agent free to look anywhere will, and Unusual
Whales bills by the request.

## What this does instead

**Two batch jobs, a daemon, and a review — with a frozen artifact between them.**

```
08:30  market-brief ─┐
                     ├─→  09:00  DESK  ──→  watchlist.json  (FROZEN)
08:45  flow-analyst ─┘         (you)              │
                                                  │  read-only, every ~15 min
                                                  ▼
                                          position-monitor
                                                  │
                                                  ▼
                                          alert_state.json
                                                  │
                               16:15  DESK ───────┘  grade + outcomes.jsonl
```

The three workers never talk to each other. They read and write files.

### Different clocks, deliberately not unified

| Stage | Clock | Shape |
|---|---|---|
| Brief | once, pre-market | wide input → narrow output |
| Flow | once, pre-market | wide input → ranked output |
| Monitor | every ~15 min, 6.5 hours | narrow input → event output |
| Review | once, post-close | full-day input → learning output |

Two batch jobs and a daemon have genuinely different failure modes, cost profiles
and latency requirements. Forcing one abstraction over all of them is what turns
these projects into mud. The brief can afford to be slow and thorough; the monitor
cannot. The monitor must be mechanically reliable on its 26th run; the brief runs
once and can afford judgement.

### The watchlist is a contract, not a conversation

This is the load-bearing decision. `schemas/watchlist.schema.json` is the only
thing that crosses from morning to afternoon, and it is frozen at 09:00.

What that buys:

- **The monitor is cheap.** It polls 6–10 tickers, not the tape. That is the
  difference between a system you can run every fifteen minutes and one that burns
  the daily quota by 10:15.
- **The monitor cannot hallucinate.** It evaluates `triggers` — declared conditions
  with fields, operators and values written by the desk when it had the full
  picture and was calm. It has no license to form new opinions from one slice of
  intraday data.
- **The day is replayable.** Watchlist plus raw captures reconstructs any moment.
- **The desk cannot chase.** A frozen list is a commitment device against the
  single most expensive habit in short-duration trading: abandoning the morning's
  work for whatever is moving at 11:40.

Levels can be revised intraday by appending to `revisions` with a reason. Names
cannot be added. The asymmetry is intentional — new information should change how
you trade a thesis, not manufacture a new one under time pressure.

### The desk is the only voice

The three workers return JSON. Only the PM writes prose. Sub-agents producing
client-facing narrative is how you get four tones and two contradictory opinions in
one morning, and the client cannot tell which one is the desk's actual view.

### State lives in git

Every scheduled stage runs as a **fresh session with no memory**. In an ephemeral
container, uncommitted files do not survive to the next fire. So state is committed
every cycle.

This looks heavy — a commit every fifteen minutes — and it is the right trade. The
git history becomes a perfect audit log: you can check out any commit and see
exactly what the desk knew at 11:47. That is worth far more than a clean history on
a repo nobody browses.

## Why the alert state file gets its own schema

The failure mode that kills these systems is not bad analysis. It is noise.

A stateless monitor re-alerts "NVDA crossed 182.50" every fifteen minutes for four
hours. The client mutes the desk by 10am, and then the one message that mattered at
14:30 gets ignored along with the rest.

So `alert_state.json` is not bookkeeping, it is the product:

- **Dedup keys.** Stable trigger ids (`NVDA:price_cross:182.50`) keyed in `fired`.
- **Cooldowns.** Per-trigger suppression windows, 30 minutes by default.
- **Fire caps.** `max_fires` bounds a single trigger's session budget.
- **Stage tracking.** Position events (`stop_proximity`, `target_1`) announce once.
- **`not_evaluated`.** Triggers the monitor could not check, and why.

That last one is the honesty mechanism. A trigger that failed to evaluate and a
trigger that did not fire are different facts, and a system that conflates them
tells the client "all quiet" while blind. Every quiet cycle is only trustworthy
because `not_evaluated` was empty.

## Two paths to Unusual Whales, on purpose

**`bin/uw`** — the wrapper the scheduled stages use. Every response is captured
raw to `state/raw/` before anything reads it. That is what makes the day
replayable. It also gives one place to count quota and one guarantee that a failed
call is loud rather than quietly empty.

**The UW MCP server** (`.mcp.json`) — 50+ native tools, for ad-hoc exploration when
you are sitting with the desk asking questions. Convenient, but it leaves no
artifact and no quota accounting.

Rule: **anything on a schedule goes through `bin/uw`.** Anything interactive can
use either.

## Deliberately not built

- **No execution.** Read-only brokerage access, enforced by a tool deny-list rather
  than by instruction. Instructions drift under pressure; deny-lists do not.
- **No numeric conviction score.** Ordinal ranking with a stated reason. A 0–100
  score on an unvalidated model implies a precision this has not earned, and a
  client will read it as one.
- **No backtest engine.** `outcomes.jsonl` accumulates honest records first. A
  backtest built before there is trustworthy outcome data produces confidence,
  which is worse than producing nothing.
- **No auto-tuning of filters.** `close-desk` proposes changes; a human decides.
  Change one thing at a time — at this sample size, three simultaneous changes
  teach you nothing about any of them.

## When to outgrow this

Pure Claude Code is the right substrate to *learn* what the desk should do. Move
the monitor to a real service when any of these bite:

- You need sub-minute reaction time (Claude Code Routines are minute-granularity).
- You want UW's WebSocket feeds (`/api/socket/*`) — those need a persistent
  connection this design cannot hold.
- The monitor is running long enough that cycles overlap.
- You want the desk to run when your account is not.

The migration is contained by design: the schemas and `bin/uw` port unchanged. Only
the agent runtime is replaced.
