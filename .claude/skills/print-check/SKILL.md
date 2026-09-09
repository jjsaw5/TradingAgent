---
name: print-check
description: One cycle of the economic-print desk — settle released events, write a frozen ticket for every playbook print with an event inside the horizon, and tell the client only what is actionable. Use when the daily check fires, or when the user asks "anything on CPI", "what's the claims call", or reports a fill on a print contract.
---

# One print-desk cycle

You are the portfolio manager reading mechanical tickets. Silence is the
default; a `play` is the exception.

## 1. Settle

```bash
bin/prints settle
```

Released events land in the ledger and the gate refreshes. `pending_result`
more than an hour after a release is a gap; `errors` are reported if they
persist.

## 2. Ticket every playbook print

For each print in the playbook in force (`state/pm/prints/playbook/`):

```bash
bin/prints ticket <PRINT>
```

- Exit 3: today's ticket for that event already exists. Read it; never
  regenerate.
- `too_far`: the nearest event is outside the horizon. Normal; nothing to say.
- No playbook in force: paper only. Say so once and point at `/print-open`.

The ticket carries the whole ladder. Read it before you speak: where the
market's implied median sits against the model's mean, in the print's units,
tells you whether the desk's edge is a real disagreement or a thin ladder.

## 3. What reaches the client

**`play`** — a message:

```
August CPI (KXCPI-26AUG), releases Fri 08:30 ET, ladder closes 08:25
BUY NO on "more than 0.4%" (KXCPI-26AUG-T0.4) at 0.87 or better, 55 contracts, max loss $48.95 incl. fees
Model: 0.29 ± 0.12 (core trend 0.26 + gasoline −0.9% MoM). Market median 0.32.
Model has ≥0.5 at 0.04; market asks 0.13 for YES, so NO at 0.87 pays 0.11 against a 0.09 cost of fees+spread... edge 0.09/contract.
Wrong if: gasoline's August drop did not pass through, or shelter re-accelerated — a 0.5 print is a 1.7σ miss for this model, and it has missed by that much in 1 of 12 months.
Tell me the fill and I'll record it.
```

The strike in the market's own words, the side in both vocabularies, limit,
count, dollar max loss with fees, the model's numbers labeled as the model's,
the market's, and the one thing that makes it wrong, taken from the replay's
coverage rather than from feel.

**`paper`** — silent unless asked; then the same message prefixed "PAPER —
gate is <stage>".

**`pass`, `too_far`, `too_late`** — silent.

**`no_model`, `no_quote`** — the desk is blind on that print. Say so once per
day with what is missing.

**`halted`, `at_capacity`** — once, with the numbers.

## 4. Fills

```bash
bin/prints record <TICKET_ID> --side yes|no --price 0.87 --contracts 55 [--market KXCPI-26AUG-T0.4]
```

Record what the client reports, on the strike they actually traded. Against
the desk's call is fine and is flagged; it settles on its own strike.

## 5. Commit

```bash
git add state/pm/prints && git commit -m "prints: check <date>" && git push
```

## Rules

- **Could-not-evaluate is not a pass.**
- **One ticket per event per day, frozen.** The gate counts one per event.
- **Never loosen a rule mid-week** because a ladder looks tempting. Append a
  revision with a reason or leave it.
- **Never place, cancel or modify an order, on any venue.**
