"""
Offline sanity tests for bin/prints — strike probabilities under the print's
rounding rule, period parsing, the regression helper and the decision rules.
No network. Run with:

    python3 -m unittest tests/test_prints.py
"""

import importlib.util
import json
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_loader = SourceFileLoader("prints", str(ROOT / "bin" / "prints"))
spec = importlib.util.spec_from_loader("prints", _loader)
prints = importlib.util.module_from_spec(spec)
_loader.exec_module(prints)
pm = prints.pm


class StrikeProbability(unittest.TestCase):
    def test_greater_uses_next_rounded_value(self):
        # CPI 'more than 0.3' resolves yes when the printed value is >= 0.4, i.e. X >= 0.35
        p = prints.strike_p(0.35, 0.1, 0.3, "greater", 0.1)
        self.assertAlmostEqual(p, 0.5, places=6)
        self.assertGreater(prints.strike_p(0.40, 0.1, 0.3, "greater", 0.1), 0.5)

    def test_greater_or_equal_uses_half_step_below(self):
        # claims 'at least 205000' resolves yes when printed >= 205000, i.e. X >= 204500
        p = prints.strike_p(204500, 5000, 205000, "greater_or_equal", 1000)
        self.assertAlmostEqual(p, 0.5, places=6)

    def test_monotone_in_strike(self):
        ps = [prints.strike_p(0.3, 0.1, k / 10, "greater", 0.1) for k in range(-2, 8)]
        self.assertEqual(ps, sorted(ps, reverse=True))

    def test_missing_sigma_is_none(self):
        self.assertIsNone(prints.strike_p(0.3, None, 0.3, "greater", 0.1))
        self.assertIsNone(prints.strike_p(0.3, 0.0, 0.3, "greater", 0.1))


class Periods(unittest.TestCase):
    def test_monthly_event(self):
        self.assertEqual(prints.target_period("CPI", "KXCPI-26AUG"), "2026-08")
        self.assertEqual(prints.target_period("PAYROLLS", "KXPAYROLLS-27JAN"), "2027-01")

    def test_claims_event_is_week_ending_prior_saturday(self):
        # released Thursday Sep 10 for the week ending Saturday Sep 5
        self.assertEqual(prints.target_period("CLAIMS", "KXJOBLESSCLAIMS-26SEP10"), "2026-09-05")

    def test_month_arithmetic(self):
        self.assertEqual(prints.add_months("2026-01", -1), "2025-12")
        self.assertEqual(prints.add_months("2026-11", 3), "2027-02")
        self.assertEqual(prints.months_between("2026-07", "2026-09"), 2)


class Regression(unittest.TestCase):
    def test_ols_recovers_line(self):
        xs = [0, 1, 2, 3, 4, 5]
        ys = [0.1 + 0.03 * x for x in xs]
        a, c, sd = prints.ols2(xs, ys)
        self.assertAlmostEqual(a, 0.1)
        self.assertAlmostEqual(c, 0.03)
        self.assertAlmostEqual(sd, 0.0, places=9)


class ImpliedMedian(unittest.TestCase):
    def test_interpolates_across_half(self):
        rows = [{"strike": 0.2, "mid": 0.9}, {"strike": 0.3, "mid": 0.6}, {"strike": 0.4, "mid": 0.12}]
        self.assertAlmostEqual(prints.implied_median(rows), 0.3 + (0.6 - 0.5) / (0.6 - 0.12) * 0.1, places=4)

    def test_null_when_not_bracketed(self):
        self.assertIsNone(prints.implied_median([{"strike": 0.2, "mid": 0.9}, {"strike": 0.3, "mid": 0.8}]))


class Decision(unittest.TestCase):
    def setUp(self):
        self.pb = json.loads(json.dumps(prints.DEFAULT_PLAYBOOK))
        self.now = 1_000_000
        self.event = {"event_ticker": "KXCPI-26AUG", "close_unix": self.now + 48 * 3600, "markets": []}
        self.dist = {"mean": 0.35, "sigma": 0.1}
        prints.gate_stage = lambda: "paper"
        prints.open_exposure = lambda: (0.0, 0, 0.0)
        pm.kalshi_orderbook = lambda ticker, depth=5: {"yes_dollars": [["0.30", "500"]], "no_dollars": [["0.60", "500"]]}

    def rows(self, yes_bid, yes_ask, p_model=0.62):
        q = {"yes_bid": yes_bid, "yes_ask": yes_ask, "no_bid": round(1 - yes_ask, 2), "no_ask": round(1 - yes_bid, 2)}
        return [{
            "ticker": "KXCPI-26AUG-T0.3", "strike": 0.3, "rule": "greater", "p_model": p_model,
            **q, "mid": (yes_bid + yes_ask) / 2, "spread": round(yes_ask - yes_bid, 2), "volume": 1, "open_interest": 1,
            "edge_yes": pm.edge_for(p_model, yes_ask, self.pb["fees"]),
            "edge_no": pm.edge_for(1 - p_model, q["no_ask"], self.pb["fees"]),
        }]

    def test_too_far_and_too_late(self):
        far = dict(self.event, close_unix=self.now + 40 * 86400)
        self.assertEqual(prints.decide(self.pb, "x", self.rows(0.3, 0.4), far, self.dist, self.now)["status"], "too_far")
        late = dict(self.event, close_unix=self.now + 600)
        self.assertEqual(prints.decide(self.pb, "x", self.rows(0.3, 0.4), late, self.dist, self.now)["status"], "too_late")

    def test_no_model_is_a_gap(self):
        self.assertEqual(prints.decide(self.pb, "x", self.rows(0.3, 0.4), self.event, None, self.now)["status"], "no_model")

    def test_wide_spread_is_not_a_candidate(self):
        d = prints.decide(self.pb, "x", self.rows(0.20, 0.45), self.event, self.dist, self.now)
        self.assertEqual(d["status"], "pass")
        self.assertIn("max_spread", d["reason"])

    def test_paper_when_edge_clears_and_gate_is_paper(self):
        # model 0.62 vs ask 0.40 (+0.02 fee) -> ev 0.20
        d = prints.decide(self.pb, "x", self.rows(0.38, 0.40), self.event, self.dist, self.now)
        self.assertEqual(d["status"], "paper")
        self.assertEqual(d["side"], "yes")
        self.assertEqual(d["limit_price"], 0.40)
        self.assertGreater(d["contracts"], 0)

    def test_play_uses_gate_stake(self):
        prints.gate_stage = lambda: "minimum"
        d = prints.decide(self.pb, "x", self.rows(0.38, 0.40), self.event, self.dist, self.now)
        self.assertEqual(d["status"], "play")
        self.assertLessEqual(d["stake"], self.pb["gate"]["minimum_stake"] + 0.01)

    def test_tail_refused(self):
        d = prints.decide(self.pb, "x", self.rows(0.80, 0.82, p_model=0.97), self.event, self.dist, self.now)
        self.assertEqual(d["status"], "pass")
        self.assertIn("tail", d["reason"])

    def test_thin_edge_passes(self):
        d = prints.decide(self.pb, "x", self.rows(0.58, 0.60), self.event, self.dist, self.now)
        self.assertEqual(d["status"], "pass")


class Settlement(unittest.TestCase):
    """Settle the worked example ticket against a stubbed Kalshi result and check
    the ledger line validates. The desk's call on that ticket is NO on
    'more than 0.3'; a print of 0.3 makes that NO a winner, a print of 0.4 a loser."""

    def setUp(self):
        self.ticket = json.loads((ROOT / "examples" / "print_ticket.example.json").read_text())
        from jsonschema import Draft202012Validator
        self.validator = Draft202012Validator(json.loads((ROOT / "schemas" / "print_ledger_entry.schema.json").read_text()))

    def settle_with(self, printed):
        pm.kalshi_market = lambda ticker: {"result": "yes" if printed > 0.3 else "no", "expiration_value": str(printed), "status": "finalized"}
        return prints.settle_ticket(self.ticket)

    def test_desk_no_wins_on_a_low_print(self):
        outcome, entry = self.settle_with(0.3)
        self.assertEqual(outcome["chosen_result"], "no")
        self.assertGreater(entry["pnl_paper_per_contract"], 0)
        self.assertEqual(sorted(e.message for e in self.validator.iter_errors(entry)), [])

    def test_desk_no_loses_on_a_high_print(self):
        outcome, entry = self.settle_with(0.4)
        self.assertEqual(outcome["chosen_result"], "yes")
        self.assertLess(entry["pnl_paper_per_contract"], 0)
        self.assertIsNone(entry["pnl_real"])

    def test_ladder_brier_is_computed_for_model_and_market(self):
        _, entry = self.settle_with(0.3)
        self.assertIsNotNone(entry["brier_ladder_model"])
        self.assertIsNotNone(entry["brier_ladder_market"])
        self.assertIsNotNone(entry["z"])

    def test_unsettled_market_returns_none(self):
        pm.kalshi_market = lambda ticker: {"result": "", "expiration_value": None}
        self.assertIsNone(prints.settle_ticket(self.ticket))


class NoLookahead(unittest.TestCase):
    """A model forecasting period T must not see period T. FRED stamps a month's
    print on the first of that month, so a release-date cutoff alone leaks it."""

    def tearDown(self):
        prints._FRED_CACHE.clear()

    def test_monthly_target_is_excluded(self):
        months = [f"{2018 + i // 12:04d}-{i % 12 + 1:02d}-01" for i in range(108)]  # 2018-01 .. 2026-12
        series = [(d, 4.0 + 0.01 * i) for i, d in enumerate(months)]
        prints.fred = lambda sid, vintage=None: series
        dist = prints.model_u3("2026-08", "2026-09-10")
        self.assertAlmostEqual(dist["mean"], dict(series)["2026-07-01"])
        self.assertEqual(dist["inputs"]["last_month"], "2026-07")
        self.assertEqual(dist["horizon"], 1)

    def test_weekly_target_is_excluded(self):
        import datetime, math
        start = datetime.date(2020, 1, 4)
        weeks = [(start + datetime.timedelta(weeks=i)).isoformat() for i in range(350)]
        series = [(d, 200000 + 5000 * math.sin(i / 3)) for i, d in enumerate(weeks)]
        prints.fred = lambda sid, vintage=None: series
        target = weeks[-1]
        dist = prints.model_claims(target, (datetime.date.fromisoformat(target) + datetime.timedelta(days=5)).isoformat())
        self.assertEqual(dist["inputs"]["last_week"], weeks[-2])
        self.assertEqual(dist["horizon"], 1)


if __name__ == "__main__":
    unittest.main()
