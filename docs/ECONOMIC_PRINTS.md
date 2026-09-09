# The economic-print desk

The second prediction-market product, on the same machinery as the 15-minute
desk (`docs/PREDICTION_MARKETS.md`): scheduled economic releases, traded as
Kalshi strike ladders through Robinhood. This is where a research edge can
actually exist, because the window is days rather than minutes and the
counterparty is a crowd reading headlines rather than a bot reading a feed.

## 1. The contracts

Kalshi lists a ladder of yes/no contracts per release. Every strike is a
separate market; every ladder is one event.

| Print | Series | Ladder | Resolves yes when |
|---|---|---|---|
| CPI, headline MoM | `KXCPI` | 0.1-point strikes | printed value is **more than** the strike (so ≥ strike + 0.1) |
| Core CPI MoM | `KXCPICORE` | 0.1 | more than |
| CPI YoY | `KXCPIYOY` | 0.1 | more than |
| Nonfarm payrolls | `KXPAYROLLS` | 10k–25k steps | more than |
| Unemployment (U-3) | `KXU3` | 0.1 | more than |
| Initial claims | `KXJOBLESSCLAIMS` | 5,000 steps | **at least** the strike |

The rounding rule matters. "More than 0.3" on a one-decimal print is the same
contract as "at least 0.4", and the model prices it that way: a strike at k with
rule "greater" is a bet that the continuous value lands at or above k + step/2.

Kalshi closes the ladder five minutes before the release and settles on the
official number (`expiration_value`). Robinhood's fees apply per contract; see
the 15-minute doc for why flat fees punish cheap strikes.

## 2. The models

Every model uses only public FRED series and is deliberately simple enough to
be graded. Each is labeled modeled on the ticket, with its inputs.

| Print | Model | What it does |
|---|---|---|
| CPI | `cpi_gas_core_v1` | trailing-3-month core trend + a + c × gasoline price MoM, with a and c fit by OLS on the last 120 months; sigma is the residual stdev. Gasoline is the monthly average of weekly retail prices, partial-month when incomplete. |
| Core CPI | `core_trend_v1` | mean of the last 3 core prints; sigma from that rule's errors over 60 months |
| CPI YoY | `cpi_yoy_v1` | the headline MoM nowcast applied to the NSA index with the month's average seasonal difference; rounded like the BLS |
| Payrolls | `payrolls_trend_v1` | mean of the last 3 changes as they stood at the time; sigma from that rule's errors, 2020 excluded |
| U-3 | `u3_rw_v1` | last month's rate; sigma from monthly changes |
| Claims | `claims_ar_v1` | w × last week + (1−w) × 4-week mean, w fit on 3 years; sigma from residuals over 2 years |

None of these knows what the market knows: no ADP, no JOLTS, no rent trackers,
no tariff pass-through. That is by design. The first question is whether an
honest, simple distribution is already better than the ladder's price at some
strikes. If it is not, a cleverer model would be tuned to the same small sample
and prove nothing. If it is, each added input gets its own replay before it
touches a decision.

**Where the model is likely worst.** Payrolls and U-3: the market has private
nowcasts and the trend model has nothing. Expect the market to win there; the
replay says so or it does not. **Where it may be adequate.** Claims, because the
series is autocorrelated and the market is thin; and headline CPI in months
where gasoline moved and the crowd anchors on last month's print.

## 3. Grading before trading

Two replays, run before the first ticket and weekly thereafter:

**`prints replay <PRINT>`** walks decades of FRED history, forecasting each
period from data before it. It reports mean absolute error against a naive
baseline, coverage of the 1σ and 2σ bands (honest sigmas give 0.68 and 0.95),
the mean and stdev of the standardized error z, a PIT histogram, and a Brier on
a synthetic ladder around the mean. It answers "is the distribution honest?"
with hundreds of samples. Payrolls uses ALFRED vintages so the inputs are what
was actually known on the eve of each release; the others use the current
vintage, which flatters seasonal factors slightly.

**`prints replay-market <PRINT>`** grades the model against the Kalshi ladder on
every settled event Kalshi still exposes, using the hourly quote on the eve of
release. It answers "is it better than the price?" with very few samples — weeks
of claims, a couple of months of the rest. Treat it as a sanity check.

Only the live ledger moves the gate.

## 4. The shape of a week

```
/print-open   ──→  state/pm/prints/playbook/<date>.json   (FROZEN for the week: prints, rules, fees, capital)
                                 │
                                 │  /print-check, daily (or /loop 6h)
                                 ▼
                 prints settle              ← released events → ledger, gate
                 prints ticket <PRINT>      ← one frozen ticket per event per day inside the horizon
                                 │
                                 ▼
                 state/pm/prints/tickets/<PRINT>-<EVENT>-<YYYYMMDD>.json   (play | paper | pass | ...)
                                 │
                   client fills by hand on Robinhood → prints record
                                 │
/print-review ──→  after each release: settle, grade, calibrate
```

**One ticket per event per day.** A print is re-evaluated daily as the nowcast
inputs arrive (a new weekly gasoline print, last week's claims). Each ticket is
frozen. The gate counts one sample per event — the last ticket before release —
so daily re-evaluation cannot inflate the sample.

**The horizon rule.** Only events releasing within `max_horizon_days` (default
10) are evaluated. Further out, the model's sigma is scaled by the square root
of the horizon, which is an assumption, not a measurement, and the ladders are
thin anyway.

**Capital.** Stake is the max loss. Defaults: $50 per event, $150 weekly loss
limit, 3 open events, $10 paper stake. The gate holds real stake at zero until
20 settled events show the model's ladder Brier beating the market's; full size
needs 60 events and 20 net-positive decisions. Twenty events is five months of
CPI or five weeks of claims. That is the honest cost of trading slow markets.

## 5. What the ticket carries

The whole ladder: for every strike, the model's probability, the market's bid,
ask and mid, the spread, and the edge after fees on each side. The market's
implied median (where its mids cross 0.5) sits next to the model's mean so the
disagreement is visible in the print's own units, not just in cents. The
decision names one strike, one side, one limit and one count, or says why not.

`no_model` and `no_quote` are statuses of their own. A FRED outage is a gap in
the desk's sight, not a pass.

## 6. Deliberately not built

- **No Fed-decision model.** The honest input is fed funds futures, which have
  no public feed here. Fed ladders are visible in `prints calendar` for context
  and get no ticket.
- **No consensus feed.** Analyst consensus would be a useful input and a
  legitimate one. It is not free. When the Unusual Whales calendar carries it,
  it becomes a ticket field with its own replay.
- **No cross-strike arbitrage.** A ladder whose yes prices are not monotone in
  the strike is a free trade in theory and a stale quote in practice.
- **No intraday reaction.** The desk does not trade the release itself. The
  ladder closes five minutes before, and the number is public two seconds after.

## 7. Cadence

Daily is enough. `/print-check` can run by hand each morning, under
`/loop 6h` in a live session, or as a fresh-session Routine (it is hourly-legal,
unlike the 15-minute desk). Whatever fires it, the check settles first, then
tickets, then commits.
