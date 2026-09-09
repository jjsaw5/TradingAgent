# The prediction-market desk

Fifteen-minute crypto up/down contracts, traded by the client on Robinhood,
researched and graded here. This document is the architecture and, more
importantly, the honest account of where an edge could and could not come from.
Read the second part before trusting anything the first part produces.

---

## 1. What the contract actually is

Robinhood's prediction-market hub routes event contracts to Kalshi. The contract
you hold in Robinhood **is** the Kalshi contract, ticker and all
(`KXBTC15M-26SEP081945-45` is "BTC price up in next 15 mins?" for the window
closing 19:45 ET on Sep 8). That matters because Kalshi publishes everything about
it through a public API that needs no credentials:

| Fact | Where it comes from |
|---|---|
| The strike ("price to beat") | `floor_strike` — the 60-second average of the CF Benchmarks real-time index in the minute before the window opened. Published at the open, exact. |
| Settlement | The same 60-second average in the minute before the close. `Yes` if it is at least the strike. |
| The quote | Order book, bids on each side; the ask is 1 minus the other side's best bid. |
| The result | `result` and `expiration_value` on the settled market. |
| History | Every settled window, with strike and result, pageable. Per-minute market candles for each. |

Windows sit on UTC quarter-hours. Kalshi runs the same series for ETH, SOL, XRP,
DOGE, ADA, BCH and a few assets Coinbase does not quote (BNB, HYPE, ZEC, TON,
NEAR). The desk supports only assets with a Coinbase spot feed, because without a
spot feed there is no model input and "no model" must stay "no model".

**Fees.** Robinhood charges a flat per-contract commission plus an exchange fee it
passes through. The desk carries these in the playbook as `fees`, defaulting to one
cent each. **This could not be verified against Robinhood's published schedule when
the desk was built** — the playbook says `verified: false` until you confirm it in
the app, and every edge number depends on it. Flat fees are brutal on cheap
contracts: two cents on a 10-cent contract is 20% of stake, on a 50-cent contract
4%. A Kalshi-direct account pays a different, quadratic fee (7% of p(1-p) per
contract); the playbook supports that model too.

**Polymarket** runs the same product on a different index (Chainlink 60s TWAP). The
desk pulls its price as a cross-reference — a second market's opinion on a
correlated question — and never as a venue.

## 2. Where the edge would have to come from

Be clear-eyed. This is a 15-minute binary on a random walk, with fees. The market
opens near 50/50 and then reprices continuously as spot moves against the strike
and time runs out. There are exactly three places an edge could live:

**A better probability than the market's, mid-window.** Given spot, strike, time
remaining and a vol estimate, the fair price of `Up` is a closed-form number. If
the market is quoting 0.30 when the fair number is 0.40, and the gap exceeds fees,
that is a trade. This is the only research that can matter inside 15 minutes, and
it is what `bin/pm` computes. The catch: the market's participants are running the
same arithmetic with faster feeds. When the model disagrees with the market, the
base rate is that the model is wrong — the replay's reliability table shows this
directly. The desk's job is to find out *whether there are windows where that base
rate does not hold*, not to assume it.

**Speed.** The market reprices in seconds when spot jumps. A loop that runs every
five minutes cannot compete on speed and does not try. Anything that looks like
"the price hasn't caught up yet" at a 5-minute cadence is a stale candle, not an
opportunity.

**Fee structure.** Flat per-contract fees make contracts near 0.50 cheap to trade
and contracts near 0.10 expensive. The playbook's `max_model_confidence` rule
refuses tail trades for a related reason: at p = 0.95 the apparent edge is
dominated by model error in the tail, and one miss costs twenty wins.

Everything else — "momentum", "the last three windows went up", Polymarket
disagreeing with Kalshi — is a hypothesis. Hypotheses go in the ledger as paper
decisions until the numbers say otherwise.

## 3. The honesty rules, applied to probabilities

The options desk is told never to state a probability it has not measured. A
prediction-market desk trades probabilities, so the rule becomes:

- **Every probability is labeled modeled, at the point it is reported.** The
  ticket's `model.note` travels with the number. The desk says "the model has this
  at 0.38" — never "there's a 38% chance".
- **Every probability is graded.** A ticket is written for *every evaluated
  window*, passes included, and settles into `state/pm/ledger.jsonl`. Calibration
  measured only on the windows you liked is not calibration.
- **Real size is earned, not granted.** The calibration gate (§5) holds stake at
  zero until the model has measurably beaten the market it is trading against.
- **The band is the "where I'd be wrong".** `p_up_band_vol_pm25pct` shows the
  probability at vol 25% higher and lower. If the band straddles the market price,
  there is no edge, whatever the point estimate says.
- **Could-not-evaluate is a status, not a pass.** `no_model` and `no_quote` are
  distinct decision statuses. They are gaps, they are reported as gaps, and a
  session full of them is a blind session, not a quiet one.

## 4. The shape of a session

```
/pm-open   ──→  state/pm/playbook/<date>.json   (FROZEN: assets, rules, fees, capital, blackouts)
                              │
                              │  /loop 5m /pm-window
                              ▼
               bin/pm settle          ← yesterday's and this morning's closed windows → ledger
               bin/pm ticket <ASSET>  ← one frozen ticket per asset per window, at 3–13 min remaining
                              │
                              ▼
               state/pm/tickets/<ASSET>-<start>.json   (decision: play | paper | pass | ...)
                              │
                 client fills by hand on Robinhood → bin/pm record
                              │
/pm-review ──→  bin/pm calibrate  → state/pm/calibration.json → the GATE for tomorrow
```

**The playbook is the watchlist.** It is written once, calmly, before the loop
starts, and the loop applies it mechanically. Assets, entry rules, fee model,
stake, loss limit and blackout windows all live there. Intraday changes are
appended to `revisions` with a reason; nothing is overwritten.

**The ticket is the contract for one window.** `bin/pm ticket` gathers strike,
spot, vol, quote and cross-reference, computes the model and the edge, applies the
playbook rules and writes the decision — then never touches it again. Two fields
are appended later: `execution` (the fill the client reports) and `outcome` (how
the window settled). A ticket that exists is not regenerated; if the desk wants a
second look it reads the ticket it already wrote.

**The ledger is the track record.** Append-only. One line per settled ticket, with
the model's number, the market's number, the decision, the fill and the result.
`bin/pm calibrate` reads nothing else.

**The clock.** Windows are 15 minutes; the loop runs every 5. Each window gets
looked at roughly three times and gets one ticket, on the first look that falls
inside the playbook's `[min_seconds_remaining, max_seconds_remaining]` band
(default 3 to 13 minutes left). Before 13 minutes the strike is fresh and the
quote thin; inside 3 minutes the outcome is a coin toss on the 60-second
settlement average and no model helps. Claude Code Routines cannot run at this
cadence — this desk needs a live `/loop` session, and it stops when the session
does. That is a real constraint, stated in `docs/RUNBOOK.md`.

**Execution is the client's, by hand, on Robinhood.** The desk is read-only on
every venue by design, and the Robinhood tools available to it do not expose
event-contract positions at all. So fills are recorded with `bin/pm record` when
the client reports them, and the ledger keeps the desk's decision and the client's
fill as two separate records with two separate P/Ls. A fill on a window the desk
did not call is flagged `against_desk: true` — their capital, their call, but the
two track records must not blur.

## 5. The model and the gate

**Model** — `driftless_lognormal_v1`:

```
sigma     = stdev of 1-minute log returns on Coinbase closes over the lookback (default 120 min)
tau_eff   = seconds remaining − 40      (the settlement is a 60s average: Var of the mean of a
                                         Brownian path over the last a seconds is sigma²(tau − 2a/3))
P(up)     = Φ( ln(spot / strike) / (sigma_per_second · √tau_eff) )
```

Zero drift. Constant vol. Coinbase spot standing in for the CF Benchmarks index.
Each assumption fails sometimes; the ±25% vol band is the cheapest honest
statement of how much the number moves when one does. It is deliberately the
simplest model that is not wrong on its face, so that when it is graded, what is
being graded is clear.

**Edge** per $1 contract, held to settlement:

```
cost = ask + fee(ask)
EV   = P(side) − cost
```

A quarter-Kelly fraction is reported on the ticket for information. Sizing is the
playbook's fixed stake. Kelly on an unvalidated model is a way to lose money
quickly, and a fixed stake produces cleaner data about whether the model works.

**Gate** — computed by `bin/pm calibrate` from the ledger, recorded in the playbook
at `/pm-open`, enforced by `bin/pm ticket` on every window:

| Stage | Requires | Stake |
|---|---|---|
| `paper` | fewer than 100 settled windows, **or** model Brier not better than market Brier | 0 — decisions are logged as `paper` |
| `minimum` | ≥100 settled, model Brier < market Brier | `gate.minimum_stake` (default $10) |
| `full` | ≥300 settled, ≥50 paper/real decisions net positive | `capital.max_stake_per_window` (default $50) |

Brier is the mean squared error of a probability; 0.25 is a coin flip, lower is
better. The market's Brier uses the Kalshi mid at decision time. The bar is not
"the model is good"; it is "the model is better than the price it is betting
against". If it never clears that bar, the correct output of this desk is a ledger
proving it, and no trades. That is a successful outcome.

**Replay.** `bin/pm replay BTC --windows 400` grades the model against several
hundred already-settled windows using Kalshi's own strike, result and per-minute
quotes, with Coinbase candles as spot. It runs in minutes and needs no capital. It
answers the calibration question before a single live ticket exists. It does
**not** answer the execution question — fills are assumed at the displayed ask,
which is the best case — and it says nothing about regime change. Re-run it weekly
and compare; do not extrapolate.

## 6. Capital

The options desk's envelope does not map cleanly onto binaries — on a binary the
stake *is* the maximum loss — so the playbook carries its own:

| Limit | Default |
|---|---|
| Max stake per window | $50 |
| Max session loss (realized + open stake) | $150 |
| Max concurrent open windows | 2 |
| Paper stake (for comparable paper P/L) | $10 |

These are enforced by `bin/pm ticket` from the ledger and the open tickets, not by
the desk remembering. The client can override for a session; the change is stated
and written into the playbook so the number in force is the number enforced.

## 7. Deliberately not built

- **No sub-agent.** The options desk uses agents because gathering flow data takes
  judgement. Here the gathering is deterministic arithmetic on four public
  endpoints, and an agent hop costs a minute on a fifteen-minute clock. `bin/pm`
  computes; the desk reads the ticket and talks.
- **No execution, on any venue.** No credentials, no order code, nothing to deny
  at the tool level because nothing exists. If a Robinhood or Kalshi order tool
  ever appears in this environment, it goes in `.claude/settings.json` deny
  before it is used once.
- **No features beyond the base model** until the base model has been graded. A
  momentum term, a Polymarket-disagreement term, a vol-of-vol term — each is a
  hypothesis that gets its own ledger column and its own replay before it touches
  a decision. One change at a time; the sample is small.
- **No Polymarket trading.** Different index, different jurisdiction, different
  fee model. Cross-reference only.
- **No automatic gate promotion.** `calibrate` reports the stage; the desk writes
  it into the next playbook at `/pm-open` and says so to the client.

## 8. When to outgrow this

The same signals as the options desk, arriving sooner:

- The playbook's `min_seconds_remaining` keeps drifting down because the
  interesting edges are in the last two minutes. That is a speed game and this is
  not a speed tool.
- The replay shows edge at minute 3 that the 5-minute loop keeps missing.
- You want Kalshi's WebSocket feed or Robinhood's own position data.

`bin/pm`, the schemas and the ledger port unchanged. The loop is what gets replaced.
