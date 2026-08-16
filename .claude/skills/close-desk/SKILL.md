---
name: close-desk
description: Close the session. Grade the day's watchlist and triggers against what actually happened, record the outcome immutably, and note what should change tomorrow. Use at the close, when the user says "close the desk" or "how did we do today", or when the end-of-day Routine fires.
---

# Closing the desk

This is the only stage that makes the desk better over time. Without it you have a
system that generates opinions and never finds out whether they were any good.

## 1. Grade every name — including the ones you passed on

For each name on the watchlist, from `state/raw/` captures and a close pull:

- Did it reach the entry zone? At what time?
- Did it hit invalidation? A target?
- Where did it close relative to the reference price?
- Was the thesis right, wrong, or untested? **Untested is the most common and the
  most honestly reported outcome** — a name that never set up did not prove
  anything either way, and scoring it as a win or a loss is how a track record
  becomes fiction.

Then grade what you *rejected*. Pull the close on names in `flow_candidates.rejected`.
A name rejected for liquidity that ran 20% is a filter problem. This is the single
highest-value habit in the whole system and it is the one every trader skips,
because it feels like self-flagellation rather than research.

## 2. Grade the triggers, not just the names

From `state/alerts/<date>.json`:

- **Fired and useful** — led to a good decision.
- **Fired and noise** — technically correct, not actionable. Cooldown too short?
  Threshold too tight? Urgency overstated?
- **Never fired** — was the level unreachable, or the condition wrong?
- **Suppressed by `max_fires`** — did the cap hide something that mattered?
- **`not_evaluated`** — which triggers were blind, and for how long?

Trigger quality is the thing you can actually improve week over week. Name
selection is mostly regime luck over a sample this small; trigger design is craft.

## 3. Honest accounting on bounds

MFE/MAE come from bar extremes and have no ordering within the bar. If a minute bar
traded through both the target and the stop, **you cannot say which came first**.
Record the ambiguity and resolve it against the position — book it as the loss.
A backtest that resolves ambiguity in its own favour is worse than no backtest,
because it produces confidence rather than merely producing nothing.

## 4. Write it down, permanently

Append to `state/positions/outcomes.jsonl` — one JSON object per name per session,
append-only. **Never rewrite a past entry.** If you got something wrong, append a
correction that references it. The value of this file is entirely in its being
un-revised; a record you can edit after the fact is not a record.

Write the session review to `state/briefs/<date>-review.md`:
- What worked and what did not
- Trigger changes to make tomorrow
- Filter changes for the flow analyst
- Names carrying into tomorrow, with the reason
- Whether the regime read held

## 5. Report to the client

Plain and unflinching:
- What we watched, what we did, what happened
- P/L against the plan, if positions were open
- What we got right, what we got wrong, what we never found out
- What changes tomorrow

Do not spin an untested thesis as a win because the stock happened to go the right
way without you. That is exactly the habit that produces a confident, useless desk.

## 6. Commit

```bash
git add state/ && git commit -m "desk: close <date>" && git push
```

## 7. Weekly, on Fridays

Read the last five `-review.md` files and `outcomes.jsonl` together:
- Which flow signal kinds actually preceded moves? (`repeat_sweep` vs
  `single_large_sweep` vs `darkpool_accumulation` — you now have real data)
- What is the hit rate on entry zones being reached at all?
- Which trigger types are consistently noise?
- Is the rejection filter losing money?

Propose concrete changes to the flow analyst's filters and the trigger defaults.
**Change one thing at a time.** With a sample this small, changing three filters at
once means you learn nothing about any of them.
