# Print desk — first replay, 2026-09-09

Run before any playbook exists. Files: `state/pm/prints/replay/*-2026-09-09.json`.

## Is each distribution honest? (FRED history, model only)

| Print | Periods | MAE model | MAE naive | 1σ cover | 2σ cover | z stdev | Verdict |
|---|---|---|---|---|---|---|---|
| CLAIMS | 156 wk | 7.2k | 7.6k | 0.71 | 0.94 | 1.00 | sigma honest; skill over naive is small |
| CPI | 60 mo | 0.156 | 0.217 | 0.68 | 0.88 | 1.24 | real skill over naive; tails fatter than sigma (2σ cover 0.88) |
| CPIYOY | 59 mo | 0.178 | 0.333 | 0.61 | 0.93 | 1.30 | inherits CPI; sigma about 25% too small |
| CPICORE | 60 mo | 0.116 | 0.105 | 0.87 | 0.97 | 0.74 | worse than last value; sigma too wide |
| U3 | 60 mo | 0.105 | 0.102 | 0.95 | 1.00 | 0.58 | is the naive model; sigma far too wide |
| PAYROLLS | 48 mo (ALFRED) | 104k | 106k | 0.96 | 1.00 | 0.48 | no skill; sigma far too wide |

## Is it better than the ladder? (settled Kalshi events, very few)

| Print | Events | Ladder Brier model | market | Model beats? |
|---|---|---|---|---|
| CLAIMS | 8 | 0.109 | 0.089 | **no** — the market is better; two large misses (Jul 16, Jul 23) look like holiday-week seasonals the market anticipated |
| CPI | 2 | 0.103 | 0.145 | yes, on two events; both hypothetical trades lost (tail YES buys) |
| PAYROLLS | 2 | 0.332 | 0.352 | yes, on two events; noise given the sigma |
| U3 | 2 | 0.033 | 0.082 | yes, on two events; noise |

## What this means for the playbook

- **CPI and CLAIMS are the only prints with defensible sigmas.** They are the
  defaults. Neither has shown an edge over the ladder; CLAIMS has shown the
  opposite on eight events.
- **CPICORE, U3, PAYROLLS stay out** until their sigmas are rescaled. Their
  z stdevs (0.74, 0.58, 0.48) mean every edge they report is inflated by the
  sigma being too wide: they will look "uncertain" and buy tails that are not
  cheap. Fix is a shorter error window (36 months) — a v2 model with its own
  replay, not a tweak.
- **CPI's tails are fatter than normal** (2σ coverage 0.88). The
  `max_model_confidence` cap at 0.90 is doing real work here; do not raise it.
- **The hypothetical trades in the market replay are mostly tail buys that
  lost.** That is the pattern to watch in the live ledger: if the desk's calls
  cluster at asks under 0.20, the edge is sigma, not information.

## One change

None yet. The gate is `paper` and stays there. The next thing that would
change a decision is CLAIMS over 20 live events, or a v2 sigma for U3.
