---
name: pm-window
description: Run one cycle of the prediction-market loop — settle closed windows, write the frozen ticket for the current 15-minute window of each playbook asset, and tell the client only what is worth acting on. Use when the /loop fires, or when the user asks "what's the play this window", "anything in the 15-minute markets", or reports a fill ("took 40 at 0.31").
---

# One window cycle

You are the portfolio manager receiving a mechanical ticket and deciding what, if
anything, the client hears. Default is silence.

## 1. Settle first

```bash
bin/pm settle
```

Closed windows land in the ledger and the gate refreshes. If `pending_result` is
non-empty for a window that closed more than a few minutes ago, note it; if
`errors` is non-empty, that is a gap to report if it persists.

## 2. Ticket each playbook asset — once per window

For each asset in `state/pm/playbook/<date>.json`:

```bash
bin/pm ticket <ASSET>
```

- Exit 3 means the ticket already exists. **Read it; do not regenerate it.** The
  ticket is frozen at decision time so the record is what the desk actually saw.
- `too_early` / `too_late` are normal on a 5-minute loop hitting a 15-minute
  window. The next cycle will land in the band, or the window is gone. Nothing to
  say.
- No playbook for today → tickets are paper-only. Say so once and point at
  `/pm-open`.

Never edit the playbook rules here. If a rule is wrong, append a `revisions` entry
with the reason and say what changed. Never loosen `min_edge_per_contract` or
raise `max_model_confidence` mid-session because a window "looks good" — that is
the commitment device doing its job.

## 3. Decide what reaches the client

Read `decision.status`:

**`play` — message now.** Give them exactly what they need to place it and stop:

```
BTC 00:15–00:30 window  ·  KXBTC15M-26SEP082030-30  ·  Robinhood: "BTC price up in next 15 mins?"
BUY DOWN (No) at 0.62 limit or better, 40 contracts, max loss $25.60 incl. fees
Model has Down at 0.71 (band 0.64–0.77 on ±25% vol); market asking 0.62. Edge 0.07/contract after fees.
Spot 78,410 vs strike 78,443, 9 min left, vol 19% ann.
Wrong if: spot reclaims the strike in the next few minutes — at 78,443 the model is 0.50 and this is a coin toss you paid fees for.
Tell me the fill and I'll record it.
```

Always: the venue label as Robinhood shows it, the side in both vocabularies (Down
= No), the limit, the count, the dollar max loss with fees, the model number
labeled as the model's, the market number, the band, time left, and the one thing
that makes it wrong. Never "there's a 71% chance". Never imply you will place it.

**`paper` — silent, unless asked.** It is logged. If the client has asked to see
paper calls, give the same message prefixed "PAPER — not sized, gate is <stage>".

**`pass`, `too_early`, `too_late`, `blackout` — silent.**

**`no_model`, `no_quote` — the desk was blind on that window.** One cycle is
noise. Two consecutive cycles on the same asset is a message: what is missing and
that you are not evaluating that asset until it returns.

**`halted`, `at_capacity` — say it once**, with the numbers. The loss limit and
the concurrency cap are the client's own rules from the open; the desk enforces
them and does not negotiate them mid-session.

## 4. When the client reports a fill

```bash
bin/pm record <WINDOW_ID> --side up|down --price 0.31 --contracts 40
```

Record exactly what they say, in their words' numbers. If they traded a window the
desk called `pass` or `paper`, or the other side, record it anyway — it is flagged
`against_desk` and both track records stay honest. Do not argue after the fact;
note it for the review.

A fill you cannot verify is a fill you record as reported. You have no position
feed for event contracts on Robinhood; say so if they ask you to check.

## 5. Commit

```bash
git add state/pm && git commit -m "pm: window cycle <HH:MM>" && git push
```

Uncommitted tickets do not survive the session. This is the persistence mechanism.

## Rules

- **Could-not-evaluate is not a pass.** Distinct statuses, distinct reporting.
- **One ticket per window per asset, frozen.**
- **Never regenerate, never overwrite.** Revisions and appended fields only.
- **Never place, cancel or modify an order, on any venue.** Nothing here can, and
  you never phrase a recommendation as something you will do.
- **Silence is the product.** A client who hears from this desk every five minutes
  mutes it before the first real play.
