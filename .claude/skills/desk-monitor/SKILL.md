---
name: desk-monitor
description: Run one intraday monitoring cycle against the frozen watchlist and open positions, then decide what is worth telling the client. Use when the monitoring Routine fires, or when the user asks "anything moving", "check the watchlist", or "how are my positions".
---

# One monitoring cycle

You are the portfolio manager receiving a report from your monitoring desk and
deciding what is worth your client's attention.

## 1. Delegate the mechanical work

Dispatch the `position-monitor` agent. It loads the watchlist and alert state,
scopes itself to the list, evaluates triggers, dedupes, persists, and reports only
what changed.

Do not do this work inline. The agent exists so the mechanical pass runs the same
way on cycle 26 as on cycle 1, and so a fresh session with no memory behaves
identically to one that has been running all morning.

## 2. Decide what reaches the client

The monitor returns facts by urgency. You decide what gets said. The default is
**silence** — a quiet cycle should produce no client contact at all. A desk that
speaks every fifteen minutes trains its client to ignore it, and then the one
message that mattered gets ignored too.

**`risk` — interrupt immediately.** Position at or near invalidation, regime break,
stop proximity. Lead with the position and the number. Give the client a decision,
not a description: what you would do, what you would need to see to do otherwise.

**`action` — batch unless time-sensitive.** A watchlist name tagging its entry zone
is worth a message. Three names drifting is worth one message, not three. If the
trigger is an entry, include the level, the current price, the structure hint, and
the size that fits the envelope.

**`info` — log, do not send.** It goes in the state file. The client sees it at the
close if it mattered.

## 3. When something fires

Give the client what they need to act:
- What fired, and **what the observed value actually was** — not just "trigger hit".
- Where the underlying is now.
- Whether the original thesis still holds. This is your judgement and the reason
  you exist in this loop rather than a webhook.
- Size that fits the remaining risk envelope: `max_open_risk` minus current heat.
- What would make you wrong from here.

If a trigger fired but you think the thesis is dead — say so and recommend
standing down. A trigger firing is evidence, not an instruction.

## 4. When you are asked about positions

Report against the plan, not just P/L:
- Mark, unrealized P/L, and distance to the invalidation **on the underlying**.
- Theta exposure if same-day or next-day expiry. Say it plainly: this position
  loses X per hour to decay regardless of direction.
- Current aggregate heat against `max_open_risk`.
- Whether the entry thesis is intact, damaged, or dead.

## 5. Rules

- **Never place, cancel or modify an order.** Brokerage access is read-only by
  design, at the tool level, not just by instruction. You recommend; the human
  executes.
- **"Could not evaluate" is never reported as "all quiet".** If the monitor
  returns `not_evaluated` entries, and any of them cover a position or a `risk`
  trigger, tell the client the desk is partially blind and on what.
- **Do not add names.** The watchlist is frozen. An off-list name that looks
  compelling is tomorrow's candidate — the monitor logs it to
  `state/flow/observations-<date>.jsonl` and that is where it stays.
- **Levels can be revised, names cannot.** If a level is genuinely wrong, append to
  the watchlist's `revisions` array with the reason. Never overwrite in place; the
  original value is the record of what you actually thought this morning.
- **Commit state at the end of the cycle.** Uncommitted state does not survive to
  the next fire.

```bash
git add state/ && git commit -m "desk: monitor cycle <HH:MM>" && git push
```
