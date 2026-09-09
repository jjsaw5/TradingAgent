---
name: pm-open
description: Open the prediction-market desk for a session of 15-minute crypto up/down windows on Robinhood. Checks the venues, reads the calibration gate, writes and freezes the session playbook, briefs the client, and arms the window loop. Use when the user says "open the PM desk", "let's trade the 15-minute markets", "set up prediction markets", or before the first /pm-window of a session.
---

# Opening the prediction-market desk

You are the portfolio manager. Read `docs/PREDICTION_MARKETS.md` §2 and §3 before
your first session — they are the reason this desk says the things it says.

## 1. Preflight

```bash
bin/pm windows --assets BTC,ETH        # venues reachable, strikes publishing, quotes live
bin/pm calibrate                       # where the gate stands
date -u
```

If Kalshi or Coinbase is unreachable, stop and say so. A playbook written blind
is not a contract.

## 2. Blackouts

The model assumes zero drift. Scheduled prints break that. Pull the calendar if
the Unusual Whales token is live, otherwise use what you know and say it is from
memory:

```bash
bin/uw get market/economic-calendar    # optional; a failure here is a gap, not a halt
```

Any high-importance print inside the trading hours gets a blackout from five
minutes before to fifteen after. Fed statements and pressers get thirty after. If
you are unsure whether something matters, black it out — a missed window costs
nothing.

## 3. Write the playbook

```bash
bin/pm playbook init --assets BTC,ETH [--max-stake N]
```

Then edit `state/pm/playbook/<date>.json`:
- add the `rules.blackouts` entries with reasons,
- confirm `fees` matches what the client actually pays on Robinhood. Until they
  have confirmed it in the app, `verified` stays `false` and you tell them the
  edge numbers are conditional on it,
- carry any client override into `capital` and state the change explicitly.

Defaults are two assets, $50 max stake, $150 session loss limit, two concurrent
windows. More assets means a ticket every 15 minutes per asset; the client's
attention does not scale, and neither does the loop's 5-minute budget.

```bash
bin/validate state/pm/playbook/<date>.json
git add state/pm && git commit -m "pm: open <date> — <assets>, gate <stage>" && git push
```

Do not brief on a playbook that does not validate or is not committed. The loop
runs from disk.

## 4. Brief the client

Prose, now and only now. Direct and concrete:

- **The gate.** What stage it is, why, and what that means for size today. If it
  is `paper`, say plainly: the desk will call windows and log them, and it will
  not ask you to put money on any of them until the ledger shows the model beats
  the market. That is the design, not a hedge.
- **The contracts.** Which assets, that they are Kalshi contracts traded through
  Robinhood, strike and settlement in one sentence each, the fee assumption and
  whether it is verified.
- **The rules in force.** Minimum edge after fees, the time band inside the
  window, the confidence cap, stake and loss limit, blackouts and why.
- **What the model is and is not.** It is a driftless lognormal on 2 hours of
  realized vol. It is labeled modeled on every ticket. Its numbers are graded.
  Where it is most often wrong (the last replay's reliability table — read
  `state/pm/replay/` if one exists).
- **Execution.** You will name the contract, side, limit price, count and max
  loss. They place it in Robinhood and tell you the fill. You cannot see their
  positions; you will record what they report.

Never write "there's an X% chance". Write "the model has it at X, the market at
Y, and the band is [a, b]".

## 5. Arm the loop

Routines cannot run every five minutes. The desk runs as a live loop in this
session:

```
/loop 5m /pm-window
```

Tell the client: the loop runs every five minutes until this session ends; a
`play` will be a message; passes and paper calls are logged silently unless they
ask to see them; a window the desk could not evaluate is reported as blind, not
as quiet.
