# Unusual Whales endpoint map

Curated from the live OpenAPI spec at `https://api.unusualwhales.com/api/openapi`
(200+ paths; this is the subset the desk actually uses). Verified 2026-08-16.

Base: `https://api.unusualwhales.com` · Auth: `Authorization: Bearer <token>` ·
**All endpoints are GET.** Never POST/PUT/DELETE.

Call everything through `bin/uw get <path> [key=value ...]` — the leading `/api`
is optional. The wrapper captures raw responses to `state/raw/<date>/`, counts
quota, and fails loudly rather than returning empty.

```bash
bin/uw ping
bin/uw get market/market-tide
bin/uw get option-activity/unusual min_premium=100000 max_dte=14 limit=200
bin/uw get stock/NVDA/flow-alerts
bin/uw budget
```

---

## Market brief (08:30) — target < 25 requests

| Path | Returns |
|---|---|
| `market/market-tide` | Aggregate net premium flow. The best single read on whether the day is being bought or sold. |
| `volatility/vix-term-structure` | VIX curve. Contango vs backwardation → buy or sell premium. |
| `market/total-options-volume` | Participation context. |
| `market/economic-calendar` | Scheduled macro prints. |
| `earnings/premarket`, `earnings/afterhours` | Today's reporters. |
| `market/fda-calendar` | Biotech catalysts. |
| `market/sector-etfs` | Sector tone. |
| `market/{sector}/sector-tide` | Net premium within one sector. |
| `market/top-net-impact` | Which names are actually moving the index. |
| `market/movers` | Gappers. |
| `news/headlines` | Overnight news. |
| `stock/{t}/gex-levels` | Gamma flip level. **An inference from OI, not traded support.** |
| `stock/{t}/max-pain` | Max pain. Also modeled. |
| `stock/{t}/spot-exposures` | Spot GEX per minute. |

## Flow analysis (08:45) — target < 120 requests

**Broad sweep**

| Path | Returns | Key params |
|---|---|---|
| `option-activity/unusual` | Unusual options activity screener. | `min_premium`, `max_dte`, `ticker_symbol` (prefix `-` to exclude), `sectors[]`, `issue_types[]`, `limit` (max 200), `date` |
| `option-trades/flow-alerts` | UW's own flow alerts. | `limit` |
| `option-trades/multi-leg` | Multi-leg trades. **Check this before calling a lone block directional** — you may be seeing one leg of a spread. |
| `darkpool/recent` | Recent dark pool prints. |
| `market/oi-change` | Open interest changes. The route to `repeat_days`. |
| `screener/option-contracts` | Hottest chains. |
| `screener/stocks` | Stock screener. |
| `volatility/anomaly/top` | Vol anomalies. |

**Corroborating datasets** — independent confirmation is what separates signal
from a single suggestive print.

| Path | Returns |
|---|---|
| `congress/recent-trades` | Congressional trading. |
| `congress/unusual-trades` | Anomalous congressional activity. |
| `insider/transactions` | Insider buys/sells. |
| `institutions/latest_filings` | Recent 13F filings. |
| `institution/{ticker}/ownership` | Institutional ownership of a name. |
| `shorts/{t}/interest-float/v2` | Short interest as % float. |

**Per-candidate deep dive** — 8 calls per name, shortlist only

| Path | Returns |
|---|---|
| `stock/{t}/flow-alerts` | This name's flow alerts. |
| `stock/{t}/net-prem-ticks` | Per-minute net call/put premium. Cumulative — sum forward for a daily curve. Shows accumulation shape. |
| `stock/{t}/iv-rank` | IV rank. Are you buying or selling expensive premium? |
| `stock/{t}/volatility/term-structure` | Per-name IV term structure. |
| `stock/{t}/greek-exposure` | Dealer greek exposure. |
| `stock/{t}/max-pain` | Max pain. |
| `stock/{t}/option-chains` | **Liquidity gate.** Spread and OI. |
| `darkpool/{t}` | This name's dark pool prints. |
| `stock/{t}/oi-change` | OI build/decay. |
| `stock/{t}/option-stance` | Aggregate positioning stance. |

## Monitoring (intraday) — target < 40 requests per cycle

| Trigger type | Path | Notes |
|---|---|---|
| `price_cross`, `price_reject` | `stock/{t}/stock-state` | Cheapest price read. Use `--no-capture`. |
| — | `stock/{t}/quote` | Fuller quote when you need the detail. |
| `flow_surge`, `flow_reversal` | `stock/{t}/flow-alerts` | |
| `net_premium_divergence` | `stock/{t}/net-prem-ticks` | |
| `darkpool_print` | `darkpool/{t}` | |
| `iv_shift` | `stock/{t}/iv-rank` | |
| `gex_level` | `stock/{t}/gex-levels`, `stock/{t}/spot-exposures` | |
| `volume_pace` | `stock/{t}/options-volume` | |
| `regime_break` | `market/market-tide` + the named index | |

## Close (16:15)

| Path | Returns |
|---|---|
| `stock/{t}/ohlc/{candle_size}` | Bars for grading. **Bar extremes have no intra-bar ordering** — if one bar spans both target and stop you cannot say which came first. |
| `stock/{t}/net-prem-ticks` | Full-day flow curve, for grading whether flow led price. |
| `option-contract/{id}/historic` | Per-contract history. |

---

## Rate limits

| Tier | Daily requests | Historical lookback |
|---|---|---|
| API Trial – Basic | 30,000 | 90 days |
| API Basic ($150/mo) | 40,000 | 2 years |
| API Advanced ($375/mo) | Unlimited | 2 years |

A full desk day: ~25 (brief) + ~120 (flow) + ~40 × 26 cycles (monitor) ≈ **1,200
requests**. Comfortable on every tier, including trial. Check with `bin/uw budget`.

## MCP server

`https://api.unusualwhales.com/api/mcp` — 50+ native tools, included on all paid
tiers. Wired up in `.mcp.json`, authenticated with the same `UW_API_TOKEN`.

Use it for **interactive exploration** while sitting with the desk. Scheduled
stages use `bin/uw` instead, because MCP calls leave no raw capture and no quota
accounting, and without captures the day is not replayable.

## WebSockets — not used, worth knowing

`/api/socket/*` carries live streams: `flow_alerts`, `option_trades`, `gex`,
`market_tide`, `price`, `news`, `trading_halts`, `custom_alerts`. They need a
persistent connection, which this architecture cannot hold — each stage is a fresh
short-lived session. If you outgrow 15-minute polling, these are the reason to move
the monitor to a real service. See `docs/ARCHITECTURE.md` § When to outgrow this.
