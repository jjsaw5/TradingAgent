# TradingAgent

A multi-agent options trading desk built on Claude Code. One portfolio manager
talking to you; three specialist agents working for it.

**It does not trade.** Brokerage access is read-only, enforced by a tool deny-list
rather than by instruction. The desk sizes and recommends; you execute.

---

## The day

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

| | |
|---|---|
| **market-brief** | Reads the tape pre-market: regime, vol, calendar, sector tone, index levels. Returns structured data and a falsifiable stance. |
| **flow-analyst** | Scans Unusual Whales — options flow, dark pool, insider, congressional, institutional — for names where somebody appears to be positioning. Returns ranked candidates with evidence and counter-evidence. |
| **desk (you)** | Reconciles the two into a watchlist of 5–8 names, writes the triggers, sets the risk envelope, and briefs the client. The only agent that writes prose. |
| **position-monitor** | Every cycle: evaluates the declared triggers against the frozen list and open positions, dedupes against alert state, reports only what changed. |

## Two ideas the whole thing rests on

**The watchlist is a contract, not a conversation.** At 09:00 the desk freezes a
JSON artifact with explicit machine-checkable triggers. The monitor evaluates those
and nothing else. It cannot discover new names, cannot form new opinions from one
intraday slice, and polls 8 tickers instead of the tape. That is the difference
between a system you can run every fifteen minutes and one that burns its quota by
10:15 — and it is also a commitment device against chasing whatever is moving at
11:40.

**Silence has to be trustworthy.** The failure mode that kills these systems is
noise: a stateless monitor re-alerts the same level every cycle for four hours, the
client mutes the desk by 10am, and the one message that mattered at 14:30 gets
ignored with the rest. So `state/alerts/<date>.json` carries dedup keys, cooldowns,
fire caps, and per-position stage tracking — plus `not_evaluated`, which records
triggers the monitor *could not check*. A trigger that failed to evaluate and a
trigger that did not fire are different facts, and conflating them is how a desk
reassures a client while blind.

## The prediction-market desk

A second desk, same rules, for the 15-minute crypto up/down contracts on
Robinhood. Robinhood routes those to Kalshi, so every contract has a published
strike, settlement and result the desk can read without credentials.

```
/pm-open                  # freeze the session playbook: assets, rules, fees, stake, blackouts
/loop 5m /pm-window       # one frozen ticket per asset per window; a play is a message, a pass is silence
/pm-review                # settle, grade, recompute the calibration gate
bin/pm replay BTC         # grade the model against 400 already-settled windows, no capital needed
```

Every ticket carries a modeled probability, labeled as such, and every ticket
settles into an append-only ledger. A calibration gate keeps real stake at zero
until the model has measurably beaten the market it is betting against. Fills
happen by hand in Robinhood and are recorded as reported. `docs/PREDICTION_MARKETS.md`
says where an edge could and could not come from; read it first.

The same machinery runs the **economic-print desk**: Kalshi's strike ladders on
CPI, core CPI, CPI YoY, payrolls, unemployment and weekly claims, priced by
nowcast models built only from public FRED data.

```
/print-open               # weekly playbook: which prints, rules, fees, stake
/print-check              # daily: settle, one frozen ticket per event, a play is a message
/print-review             # after each release: grade the distribution, the call, the fill
bin/prints replay CPI     # grade a model on decades of prints before any ticket exists
```

`docs/ECONOMIC_PRINTS.md` explains the contracts, the models, and what each one
does not know.

## Quick start

```bash
cp .env.example .env      # add your Unusual Whales API token
chmod +x bin/uw
bin/uw ping

/open-desk                # brief + flow + watchlist + briefing
/desk-monitor             # one monitoring cycle
/close-desk               # grade the day
```

Run all three by hand for a few sessions before scheduling anything — the trigger
design needs tuning against real days, and you want to be watching when it is
wrong. Then see `docs/RUNBOOK.md`.

## Requirements

- An [Unusual Whales API](https://unusualwhales.com/public-api) subscription. The
  free weekly trial tier is enough to evaluate this — a full desk day is ~1,200
  requests against a 30,000/day trial cap.
- Claude Code.
- Optional: a read-only brokerage connection for position monitoring.

## Layout

```
.claude/agents/     market-brief · flow-analyst · position-monitor
.claude/skills/     open-desk · desk-monitor · close-desk
                    pm-open · pm-window · pm-review · print-open · print-check · print-review
schemas/            the artifact contracts — read these first
examples/           worked watchlist, playbooks and tickets, for reference
bin/uw              UW REST wrapper; captures raw responses for replay
bin/pm              15-minute desk: Kalshi data, pricer, tickets, ledger, replay
bin/prints          print desk: Kalshi ladders, FRED nowcasts, tickets, ledger, replay
bin/validate        schema check; agents run it before writing any artifact
tests/              offline tests for the pricers and the decision rules
state/              briefs · flow · watchlist · alerts · positions · pm · pm/prints · raw · cache
docs/               ARCHITECTURE · UW_ENDPOINTS · RUNBOOK · PREDICTION_MARKETS · ECONOMIC_PRINTS
CLAUDE.md           the desk's operating rules and risk envelope
```

`docs/ARCHITECTURE.md` explains why it is shaped this way, and what would justify
outgrowing it.

## What this is not

No execution. No validated edge — nothing here has been tested out of sample, and
the desk is instructed never to state a probability it has not measured. No
composite conviction score, because a 0–100 number on an unvalidated model implies
a precision it has not earned. No backtest engine until `outcomes.jsonl` has
accumulated honest records, including the honest ones that say a thesis was never
tested.

The judgement is yours. This makes it cheaper to exercise.
