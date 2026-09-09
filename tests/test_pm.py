"""
Offline sanity tests for bin/pm — the pricer, the fee model, the edge arithmetic
and the decision rules. No network. Run with:

    python3 -m unittest tests/test_pm.py
"""

import importlib.util
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# bin/pm has no .py suffix, so name the loader explicitly
_loader = SourceFileLoader("pm", str(ROOT / "bin" / "pm"))
spec = importlib.util.spec_from_loader("pm", _loader)
pm = importlib.util.module_from_spec(spec)
_loader.exec_module(pm)


class Pricer(unittest.TestCase):
    def test_at_the_strike_is_a_coin_flip(self):
        p, z, tau = pm.model_p_up(100.0, 100.0, 0.0003, 600)
        self.assertAlmostEqual(p, 0.5, places=6)
        self.assertAlmostEqual(z, 0.0)
        self.assertAlmostEqual(tau, 600 - 40)

    def test_monotone_in_spot(self):
        ps = [pm.model_p_up(s, 100.0, 0.0003, 600)[0] for s in (99.0, 99.9, 100.1, 101.0)]
        self.assertEqual(ps, sorted(ps))
        self.assertLess(ps[0], 0.5)
        self.assertGreater(ps[-1], 0.5)

    def test_converges_as_time_runs_out(self):
        early = pm.model_p_up(100.2, 100.0, 0.0003, 800)[0]
        late = pm.model_p_up(100.2, 100.0, 0.0003, 100)[0]
        self.assertGreater(late, early)

    def test_missing_inputs_stay_missing(self):
        for args in ((None, 100.0, 0.0003, 600), (100.0, None, 0.0003, 600),
                     (100.0, 100.0, None, 600), (100.0, 100.0, 0.0, 600)):
            self.assertEqual(pm.model_p_up(*args), (None, None, None))

    def test_realized_vol_needs_enough_bars(self):
        # 10 bars is not a vol estimate
        candles = {t * 60: (1, 1, 1, 100 + (t % 2), 1) for t in range(10)}
        sigma, n = pm.realized_vol(candles, 600, 120)
        self.assertIsNone(sigma)
        # a full lookback of alternating closes has a well-defined stdev
        candles = {t * 60: (1, 1, 1, 100 + (t % 2), 1) for t in range(121)}
        sigma, n = pm.realized_vol(candles, 120 * 60, 120)
        self.assertIsNotNone(sigma)
        self.assertEqual(n, 119)


class Fees(unittest.TestCase):
    def test_robinhood_flat(self):
        fees = {"model": "robinhood_flat", "commission_per_contract": 0.01, "exchange_fee_per_contract": 0.01}
        self.assertAlmostEqual(pm.fee_per_contract(fees, 0.10), 0.02)
        self.assertAlmostEqual(pm.fee_per_contract(fees, 0.90), 0.02)

    def test_kalshi_quadratic_is_symmetric(self):
        fees = {"model": "kalshi_quadratic", "rate": 0.07}
        self.assertAlmostEqual(pm.fee_per_contract(fees, 0.30), pm.fee_per_contract(fees, 0.70))
        self.assertAlmostEqual(pm.fee_per_contract(fees, 0.50), 0.0175)


class Edge(unittest.TestCase):
    fees = {"model": "robinhood_flat", "commission_per_contract": 0.01, "exchange_fee_per_contract": 0.01}

    def test_ev_is_p_minus_cost(self):
        e = pm.edge_for(0.40, 0.30, self.fees)
        self.assertAlmostEqual(e["cost"], 0.32)
        self.assertAlmostEqual(e["ev_per_contract"], 0.08)
        self.assertAlmostEqual(e["breakeven_p"], 0.32)

    def test_no_ask_means_no_edge_not_zero_edge(self):
        e = pm.edge_for(0.40, None, self.fees)
        self.assertIsNone(e["ev_per_contract"])
        self.assertIsNone(e["cost"])

    def test_pnl_per_contract(self):
        self.assertAlmostEqual(pm.pnl_per_contract("up", 0.30, 0.02, "up"), 0.68)
        self.assertAlmostEqual(pm.pnl_per_contract("up", 0.30, 0.02, "down"), -0.32)
        self.assertIsNone(pm.pnl_per_contract(None, 0.30, 0.02, "up"))


class Decision(unittest.TestCase):
    def setUp(self):
        import json
        self.pb = json.loads(json.dumps(pm.DEFAULT_PLAYBOOK))
        self.quote = {"yes_bid": 0.29, "yes_ask": 0.30, "no_bid": 0.70, "no_ask": 0.71,
                      "yes_ask_size": 500, "no_ask_size": 500, "mid_up": 0.295}
        self.spot = {"price": 100.0}
        # stub the gate and the exposure so the test is offline and deterministic
        pm.gate_stage = lambda playbook: "paper"
        pm.open_exposure = lambda playbook: (0.0, 0, 0.0)

    def decide(self, p_up, remaining=600, quote=None, ref="state/pm/playbook/x.json", strike=100.0):
        q = quote or self.quote
        eu = pm.edge_for(p_up, q["yes_ask"], self.pb["fees"])
        ed = pm.edge_for(1 - p_up, q["no_ask"], self.pb["fees"])
        return pm.decide(self.pb, ref, remaining, 0, 900, q, p_up, eu, ed, strike, self.spot, 0.0003)

    def test_time_band(self):
        self.assertEqual(self.decide(0.5, remaining=100)["status"], "too_late")
        self.assertEqual(self.decide(0.5, remaining=850)["status"], "too_early")

    def test_no_quote_is_not_a_pass(self):
        q = dict(self.quote, yes_ask=None)
        self.assertEqual(self.decide(0.5, quote=q)["status"], "no_quote")

    def test_no_model_is_not_a_pass(self):
        d = pm.decide(self.pb, "x", 600, 0, 900, self.quote, None, pm.edge_for(None, 0.3, self.pb["fees"]),
                      pm.edge_for(None, 0.7, self.pb["fees"]), 100.0, self.spot, 0.0003)
        self.assertEqual(d["status"], "no_model")

    def test_pass_when_edge_is_thin(self):
        # market 0.30 ask, model 0.33: ev 0.01 < 0.05 min
        self.assertEqual(self.decide(0.33)["status"], "pass")

    def test_paper_when_gate_is_paper(self):
        d = self.decide(0.45)  # ev up = 0.45 - 0.32 = 0.13
        self.assertEqual(d["status"], "paper")
        self.assertEqual(d["side"], "up")
        self.assertEqual(d["limit_price"], 0.30)
        self.assertGreater(d["contracts"], 0)
        self.assertAlmostEqual(d["stake"], d["contracts"] * 0.32, places=2)

    def test_play_at_full_gate_is_capped_by_stake(self):
        pm.gate_stage = lambda playbook: "full"
        d = self.decide(0.45)
        self.assertEqual(d["status"], "play")
        self.assertLessEqual(d["max_loss"], self.pb["capital"]["max_stake_per_window"] + 0.01)

    def test_tail_confidence_is_refused(self):
        pm.gate_stage = lambda playbook: "full"
        q = dict(self.quote, yes_ask=0.80, no_ask=0.21)
        d = self.decide(0.97, quote=q)
        self.assertEqual(d["status"], "pass")
        self.assertIn("tail", d["reason"])

    def test_no_playbook_means_paper_only(self):
        pm.gate_stage = lambda playbook: "full"
        d = self.decide(0.45, ref=None)
        self.assertEqual(d["status"], "paper")

    def test_session_loss_limit_halts(self):
        pm.gate_stage = lambda playbook: "full"
        pm.open_exposure = lambda playbook: (0.0, 0, -140.0)
        self.assertEqual(self.decide(0.45)["status"], "halted")

    def test_blackout(self):
        self.pb["rules"]["blackouts"] = [{"from": "1970-01-01T00:05:00Z", "to": "1970-01-01T00:20:00Z", "reason": "CPI"}]
        self.assertEqual(self.decide(0.45)["status"], "blackout")


if __name__ == "__main__":
    unittest.main()
