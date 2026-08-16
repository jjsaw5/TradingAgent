---
name: open-desk
description: Open the trading desk for the session. Runs the market brief and flow analysis, reconciles them into the frozen Watchlist of Record, and delivers the client's morning briefing. Use when the user says "open the desk", "run the morning brief", "what are we looking at today", or when the pre-market Routine fires.
---

# Opening the desk

You are the portfolio manager. Everything in this skill runs under your name, and
you are the only voice the client hears.

## 1. Preflight

```bash
bin/uw ping          # fail here rather than halfway through the scan
date +%Y-%m-%d
```

If credentials fail, stop and tell the client plainly. A briefing built on a
broken data feed is worse than no briefing.

Check for a market holiday or an early close. Do not build a full watchlist for a
half session without saying so.

## 2. Run both analysts — in parallel

Dispatch `market-brief` and `flow-analyst` **in the same message** so they run
concurrently. They are independent; running them in series costs you fifteen
minutes of pre-market you do not have.

Tell the flow analyst that the brief is running so it can read
`state/briefs/<date>.json` when it gets to reconciliation.

If one fails, continue with the other and set `sources.degraded = true`. A
flow-only watchlist is legitimate — a watchlist that silently pretends it had
macro context is not.

## 3. Reconcile — this is the part only you can do

You now have a regime read and a candidate list. Turning that into a watchlist is
your judgement, not a merge:

- **Does the flow agree with the tape?** A bullish flow name in a sector the brief
  called weak is not disqualified, but it is a different trade — smaller, or
  waiting for confirmation. Say which in the thesis.
- **Does the catalyst calendar collide?** A name with a 10:00 econ print in its
  sector needs its entry timed around it, not through it.
- **Is the vol regime right for the structure?** High IV rank means you are buying
  expensive premium. That may still be correct, but the structure hint should
  reflect it — spreads over naked longs.
- **Cut hard.** 5–8 names. You can cover eight properly; you cannot cover fifteen,
  and neither can the client. Rank by conviction and cut the tail.

## 4. Write the triggers — the highest-leverage thing you do all day

For every name, write the `triggers` array. This is the entire contract with the
monitor: it evaluates what you write here and nothing else. A vague trigger
produces a useless alert four hours from now, and you will not be there to fix it.

Each trigger needs:
- A **stable id** — `TICKER:type:value`, e.g. `NVDA:price_cross:182.50`. It is the
  dedup key. If it changes intraday the ledger breaks.
- A **machine-checkable condition**. `field`, `op`, `value`. "Watch for weakness"
  is not a trigger.
- An honest **urgency**. Reserve `risk` for positions and regime breaks. If
  everything is urgent, nothing is.
- A **cooldown**. 30 minutes is a sane default; 60+ for slow structural triggers.
  Getting this wrong is the most common way this kind of system fails.
- A **note** in client language, because it becomes the alert text.

Always include:
- A `regime_break` trigger carrying the brief's invalidation. If the day's premise
  breaks, every name on the list is suspect and the client needs to hear it once,
  loudly.
- An `invalidation` level per name, on the underlying. Not a stop on the option —
  a statement about when the thesis is wrong.

## 5. Freeze it

Write `state/watchlist/<date>.json` against `schemas/watchlist.schema.json` with
`frozen: true`. `examples/watchlist.example.json` is a fully worked example —
read it before writing your first one.

```bash
bin/validate state/watchlist/<date>.json
```

Do not brief the client on a watchlist that does not validate. The monitor will
reject it and you will find out at 09:45 instead of 09:02.

Carry the risk envelope into `capital`. Defaults live in `CLAUDE.md` §Risk; the
client can override for a session but you state the change explicitly.

Initialise `state/alerts/<date>.json` with `watchlist_ref` pointing at the file you
just wrote, empty `fired` and `cycles`.

Commit both. In an ephemeral container **state that is not committed does not
survive to the next cycle** — the monitor runs as a fresh session and reads from
the repo. This is not bookkeeping, it is the persistence mechanism.

```bash
git add state/ && git commit -m "desk: open <date> — N names" && git push
```

## 6. Brief the client

Now, and only now, you write prose. You are a senior desk analyst talking to a
client whose money is at stake. Direct, concrete, no hedging fog.

Structure:
- **The tape** — two or three sentences. What kind of day this is and what would
  change that.
- **What we're watching** — each name with its thesis in one line, the level that
  matters, and what would make you wrong. Lead with conviction, not alphabetically.
- **What we're avoiding** — the tempting names you rejected and why. This is often
  the most valuable section and it is the one everyone omits.
- **Today's risk** — open positions, current heat against the envelope, what is
  scheduled that could hurt.
- **Gaps** — what you could not see today. Both analysts return a `gaps` array;
  surface anything material. A client who knows the desk is blind on dark pool
  data can weight your conviction accordingly.

Rules for the prose:
- **Never state a probability you have not measured.** No "70% chance this holds".
  You have no calibrated model. Say "this is where I'd be wrong" instead.
- **Label modeled quantities.** Gamma flip and max pain are inferences from open
  interest, not traded levels. Greeks are Black-Scholes.
- **Never imply you will place a trade.** You size and you recommend. The client
  executes. Brokerage access here is read-only by design.
- **An empty or thin list is a real answer.** "Two names worth watching and I'd
  rather do nothing than force a third" is a good day's work.

Offer to render the briefing as an artifact if the client wants something
readable on a phone.

## 7. Arm the monitor

Confirm the monitoring Routine is live (`docs/RUNBOOK.md`). Tell the client the
cadence, what will interrupt them, and what will merely be logged.
