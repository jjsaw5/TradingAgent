# Runbook

## First-time setup

**1. Credentials and tooling**
```bash
cp .env.example .env
# put your UW token in .env — never anywhere else
chmod +x bin/uw bin/validate
pip install jsonschema                 # bin/validate needs it
bin/uw ping                            # must print "ok: credentials accepted"
bin/validate examples/watchlist.example.json --schema watchlist
```

**2. Brokerage (optional, read-only)**
The desk works without it — you lose position monitoring, not watchlist
monitoring. If you connect Robinhood, verify the deny-list in
`.claude/settings.json` is in force. **No order tool should ever be callable.**

**3. Dry run, in this order**
```
/open-desk        # confirm watchlist written + committed
/desk-monitor     # confirm it reads state and dedupes
/close-desk       # confirm outcomes.jsonl appends
```
Run all three manually for at least three sessions before you schedule anything.
The trigger design needs tuning against real days, and you want to be watching
when it is wrong.

---

## Scheduling

Routines fire in **UTC**. The desk runs on **ET**. You must convert, and you must
re-check twice a year at DST boundaries.

### Cron — Eastern Daylight Time (Mar–Nov, UTC−4)

| Stage | ET | UTC cron |
|---|---|---|
| Market brief | 08:30 | `30 12 * * 1-5` |
| Flow analysis | 08:45 | `45 12 * * 1-5` |
| Open desk | 09:00 | `0 13 * * 1-5` |
| Monitor | :00/:15/:30/:45, 09:45–15:45 | see below |
| Close desk | 16:15 | `15 20 * * 1-5` |

### Cron — Eastern Standard Time (Nov–Mar, UTC−5)

Add one hour to every UTC value above: `30 13`, `45 13`, `0 14`, `15 21`.

> Set a calendar reminder for both DST changeovers. A desk that briefs an hour
> after the open is worse than no desk, and the failure is silent.

### The monitor cadence problem

**Claude Code Routines have a minimum interval of one hour.** A `*/15` cron will
be rejected. This is a real constraint on the pure-Claude-Code substrate and there
are three honest options:

**Option A — hourly (simplest).** One Routine, `0 14-20 * * 1-5`. Seven cycles a
day. Adequate for swing-ish short-duration positions; too slow for 0DTE.

**Option B — four offset Routines (recommended).** Each is individually hourly,
which is legal, and together they give a 15-minute effective cadence:
```
0  14-19 * * 1-5     # :00
15 13-19 * * 1-5     # :15  (starts 09:45 ET)
30 13-19 * * 1-5     # :30
45 13-19 * * 1-5     # :45
```
Four separate Routines, all pointing at `/desk-monitor`, all creating fresh
sessions. They do not share memory — which is fine, because all state is on disk.

**Option C — a live `/loop` session.** Tightest cadence, but it needs a session
alive all day and dies with the container. Use it when you are actively at the
desk, not as the standing arrangement.

Start with Option A. Move to B once you trust the trigger design and know the
noise level. If you find yourself wanting sub-minute reaction, that is the signal
to move the monitor off this substrate entirely — see
`docs/ARCHITECTURE.md` § When to outgrow this.

### The skill guards its own hours

Cron is coarse; the skill is smart. `/desk-monitor` checks whether the market is
open and whether a watchlist exists for today, and exits quietly if not. So an
over-broad cron window is harmless — it is better to fire and no-op than to miss
a cycle. Do not try to encode market holidays in cron.

### Creating the Routines

Each Routine should create a **fresh session** (not bind to a persistent one) and
carry a standalone prompt, since it starts with no context:

| Routine | Prompt |
|---|---|
| Brief + flow + open | `Run /open-desk for today's session.` |
| Monitor | `Run /desk-monitor. If the market is closed or no watchlist exists for today, exit quietly without messaging.` |
| Close | `Run /close-desk for today's session.` |

Turn **completion notifications on** for the open and close Routines, **off** for
the monitor — the monitor decides for itself when to interrupt, and a per-fire
notification would defeat the entire dedup design.

---

## Daily operation

**Morning.** The briefing arrives around 09:00 ET. Read the gaps section — it
tells you where the desk is blind today.

**Intraday.** Silence is the expected state and it means "checked, nothing fired",
not "not checked" — the coverage record is in `state/alerts/<date>.json` under
`cycles`. `risk` items interrupt. `action` items batch.

**Close.** The review grades names, triggers, and the names you rejected.

**Friday.** Ask for the weekly review. Change **one thing at a time** — at this
sample size, three simultaneous filter changes teach you nothing about any of them.

---

## Troubleshooting

**`bin/uw: UW_API_TOKEN is not set`** — `.env` missing or not readable. It is
gitignored by design, so a fresh clone never has it. This is expected on every new
container; re-create it from your secret store.

**`HTTP 429 — daily request quota exhausted`** — check `bin/uw budget`. A full day
should land near 1,200. If you are far above, the monitor is likely pulling
endpoints its triggers do not reference.

**`HTTP 403`** — either the token is wrong or the endpoint is not in your plan
tier. `bin/uw ping` distinguishes these.

**Monitor says "no watchlist for today"** — `/open-desk` did not run, or ran and
did not commit. Check `git log -- state/watchlist/`. Uncommitted state does not
survive to the next fire; this is the most common failure in this design.

**`watchlist_ref` mismatch, monitor halts** — someone re-ran `/open-desk` mid-session
and the dedup ledger no longer matches the watchlist. Halting is correct. Decide
deliberately: keep the original watchlist, or accept a re-alert storm and re-init
`state/alerts/<date>.json`.

**Duplicate alerts** — the dedup ledger is not persisting. Confirm the monitor
commits `state/` at the end of every cycle, and that trigger `id` values are stable
(they must not embed a timestamp or a live price).

**Desk went quiet all afternoon** — check `cycles` in the alert state. If cycles
are recorded and `not_evaluated` is empty, the desk really was quiet. If cycles
stop, the Routine stopped firing; if `not_evaluated` is filling up, the desk was
blind and should have told you.
