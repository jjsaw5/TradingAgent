---
name: print-review
description: Review the economic-print desk after a release or at week's end — settle, grade the model's distribution against the print, grade the desk's call and the client's fill separately, recompute the gate, and propose at most one change. Use when the user says "how did we do on CPI", "review the prints", "close the print desk", or after any release in the playbook.
---

# Reviewing the print desk

## 1. Settle and calibrate

```bash
bin/prints settle
bin/prints calibrate
```

## 2. Grade three things, separately

Read today's ledger lines (`state/pm/prints/ledger.jsonl`) and the tickets.

**The distribution.** For each released event: the print, the model's mean and
sigma, and z. A z inside ±1 is the model doing its job; a z beyond 2 is a
finding, and the question is which input was wrong (a partial-month gasoline
average, a revised prior print, a horizon the sigma did not cover). Compare the
model's ladder Brier with the market's on the same event: that is the only
number that says whether there was an edge to have.

**The desk's calls.** Every `play` and `paper`: predicted EV vs realized P/L per
contract. Note whether the chosen strike was near the mean (a distribution
call) or in a tail (a sigma call); they fail differently.

**The client's fills.** `pnl_real`, on the strike they traded, with
`against_desk` flagged. Theirs, not the desk's. Say it once either way.

## 3. The gate

Report `calibrate`'s stage and reason verbatim. The sample here grows by one
per event; say how many more events the next stage needs and roughly when that
is. Do not argue with it.

## 4. One change

At most one, with the evidence line:

1. A print whose z stdev is far from 1 across the replay and the ledger — fix
   the sigma before anything else.
2. `max_horizon_days` — were the plays inside a day of release, or a week out
   where the ladder is thin and the sigma is a guess?
3. `max_spread` — did the plays come from wide ladders that moved before the
   client could fill?
4. A print the market consistently beats (payrolls is the likely one) — drop
   it from the playbook rather than tune it.

Adding an input to a model is a replay project, not a review note.

## 5. Write it down

`state/pm/prints/reviews/<date>.md`: the releases, the model vs the print, the
calls, the fills, the gate, the one change. Then:

```bash
git add state/pm/prints && git commit -m "prints: review <date>" && git push
```

## 6. Weekly

```bash
bin/prints replay CLAIMS
bin/prints replay CPI
bin/prints replay-market CLAIMS
```

Compare with last week's files in `state/pm/prints/replay/`. Coverage and z
stdev should be stable; if they drift, the regime moved and the sigma is stale.
