---
name: pm-review
description: Close the prediction-market session. Settle every window, grade the desk's calls and the client's fills separately, recompute calibration and the sizing gate, and write the review. Use when the user says "close the PM desk", "how did the 15-minute markets go", or at the end of a /loop session. Weekly, also re-run the replay.
---

# Closing the prediction-market desk

This is the stage that makes the desk better. Without it, it is a system that
emits probabilities and never finds out whether they were any good.

## 1. Settle everything

```bash
bin/pm settle
bin/pm calibrate
```

Anything still `pending_result` an hour after its close is a gap to record — the
exchange has not published, or the settle call is failing. Do not fill it in.

## 2. Grade three things separately

Read today's ledger lines (`state/pm/ledger.jsonl`, filter by `window_start`) and
the tickets.

**The model.** Brier vs the market's Brier on today's windows, and where the
reliability table is off. "The model said 0.3 on 14 windows and 2 went up" is a
finding; act on it only if the replay shows the same thing across hundreds.

**The desk's decisions.** For every `play` and `paper`: predicted EV vs realized
P/L per contract. Hit rate is less informative than whether the realized mean is
anywhere near the predicted mean. Count the `no_model` / `no_quote` windows: how
blind was the desk today, and on what.

**The client's fills.** Real P/L from `pnl_real`. Fills flagged `against_desk`
are graded on their own line — theirs, not the desk's. If they made money
against the desk, say so plainly and ask what they saw; if they lost money
against the desk, say that plainly too, once.

Untested is an outcome. A window that passed and then went the model's way proved
nothing about a trade that was never made.

## 3. The gate

`bin/pm calibrate` prints the stage and the reason. Report it verbatim. If it
moved, say what moved it. If it did not, say what it needs: more settled windows,
or a model that beats the market, or decisions that make money on paper. The gate
does not promote on conviction, and you do not argue with it in the review.

## 4. One change

Propose at most one change for tomorrow's playbook, with the evidence line that
motivates it. Candidates, in order of how often they are the real problem:

1. The time band (`min_seconds_remaining` / `max_seconds_remaining`) — where in
   the window did the edge actually appear, if anywhere?
2. The minimum edge — were the wins at 0.05 or only at 0.10+?
3. The vol lookback — did 120 minutes lag a regime change?
4. Blackouts that were missing.
5. An asset that produced only `no_quote` all day — drop it.

Not candidates: adding a signal, raising the confidence cap, or promoting the gate
by hand. Those need a replay, not a day.

## 5. Write it down

Append nothing to the ledger by hand. Write the review to
`state/pm/reviews/<date>.md`: what the desk saw, what it called, what happened,
what the client did, the gate, the one change. Plain, unflinching, short.

```bash
git add state/pm && git commit -m "pm: review <date>" && git push
```

## 6. Weekly

```bash
bin/pm replay BTC --windows 400
bin/pm replay ETH --windows 400
```

Compare with last week's file in `state/pm/replay/`. Did the model-vs-market
Brier gap move? Did the by-minute table move? If the replay and the live ledger
disagree — replay says edge at minute 7, live tickets at minute 7 lose — the
difference is execution (fills at the displayed ask are the best case) or basis
(Coinbase vs the index), and both argue for smaller size, not a different model.
