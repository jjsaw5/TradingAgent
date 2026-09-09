---
name: print-open
description: Open the economic-print desk for the week. Reads the release calendar and the calibration gate, runs or reads the replays, writes and freezes the weekly playbook, and briefs the client on which prints are in play and why. Use when the user says "open the print desk", "set up this week's prints", "what economic releases are we trading", or at the start of a week.
---

# Opening the print desk

You are the portfolio manager. Read `docs/ECONOMIC_PRINTS.md` §2 and §3 first:
the models are simple on purpose and the client needs to hear what they do not
know.

## 1. Preflight

```bash
bin/prints calendar               # every supported print, next three events, market median vs model mean
bin/prints calibrate              # where the gate stands
```

If FRED or Kalshi is unreachable, stop and say so. Calls made without the model
are not calls.

## 2. Read the replays — or run them

```bash
ls state/pm/prints/replay/
bin/prints replay CLAIMS          # ~1 minute each; run any that are older than a week
bin/prints replay CPI
bin/prints replay-market CLAIMS   # few events; a sanity check, not a track record
```

For each print you intend to include, know three numbers: coverage at 1σ
(honest is about 0.68), z stdev (honest is about 1), and whether
`replay-market` shows the model beating the ladder. A print whose sigma is
badly mis-scaled does not go in the playbook until the model is fixed, because
every edge it reports is fiction.

## 3. Write the playbook

```bash
bin/prints playbook init --prints CPI,CLAIMS [--max-stake N] [--days 7]
```

Then edit `state/pm/prints/playbook/<date>.json`:
- keep only prints whose replay you can defend,
- confirm `fees` with the client (Robinhood's per-contract fee; `verified` stays
  false until they have),
- carry any client override into `capital` and state it.

```bash
bin/validate state/pm/prints/playbook/<date>.json
git add state/pm/prints && git commit -m "prints: open week of <date> — <prints>, gate <stage>" && git push
```

## 4. Brief the client

- **The calendar.** Which releases fall inside the horizon this week, when
  (ET), and what the market's implied median is for each next to the model's
  mean and sigma, in the print's own units. "Market has August CPI at 0.32,
  model at 0.29 ± 0.12" is the sentence; the client can see at once that the
  disagreement is a quarter of a sigma.
- **The gate**, verbatim from `calibrate`, and what it means for size this week.
- **What each model knows and does not.** One line per print from
  `docs/ECONOMIC_PRINTS.md` §2. Say where you expect the market to be better.
- **Execution.** Contracts are placed by hand in Robinhood; the desk records
  fills as reported and cannot see positions.

Never state a probability as a fact. "The model has more-than-0.3 at 0.41; the
market is asking 0.62; that is a pass" is the register.

## 5. Arm the check

```
/loop 6h /print-check        # in a live session
```

or a fresh-session Routine that runs `/print-check` each morning (hourly cadence
is legal for this desk). Tell the client which, and that a `play` is a message
while everything else is logged.
