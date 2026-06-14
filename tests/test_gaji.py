#!/usr/bin/env python3
"""
Golden-fixture regression tests for the payroll calculation (actions/gaji.py).

This is the *trust layer's* safety net: payroll/tax numbers are the thing SME owners
rely on, so they must never drift silently. Two kinds of guard here:

1. RATE GUARD — pins the statutory values in rates/<year>.json that the fixtures below
   assume. If a rate changes, this fails first with a clear message, forcing whoever
   changed the rate to consciously update the expected payroll figures too.
2. GOLDEN FIXTURES — exact expected outputs for fixed inputs under those rates. If the
   gaji.py math changes accidentally, these fail.

Stdlib-only (unittest), no deps — runs anywhere, including CI.
Run: python3 -m unittest discover -s tests -v
"""
import importlib.util
import json
import os
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("KACANGJE_DIR", str(REPO_ROOT))

# Import actions/gaji.py by path (it isn't an installable package).
_spec = importlib.util.spec_from_file_location("gaji", REPO_ROOT / "actions" / "gaji.py")
gaji = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gaji)

RATES = json.loads((REPO_ROOT / "rates" / "2026.json").read_text(encoding="utf-8"))


class TestRateGuard(unittest.TestCase):
    """If any of these fail, rates/2026.json changed — update the golden fixtures
    below to match the new official figures, then update this guard."""

    def test_statutory_rates_unchanged(self):
        msg = "rates/2026.json changed — review and update the gaji golden fixtures."
        self.assertEqual(RATES["epf"]["employee_rate_pct"], 11.0, msg)
        self.assertEqual(RATES["epf"]["employer_rate_pct_below_5000"], 13.0, msg)
        self.assertEqual(RATES["epf"]["employer_rate_pct_above_5000"], 12.0, msg)
        self.assertEqual(RATES["epf"]["wage_threshold"], 5000, msg)
        self.assertEqual(RATES["socso"]["employee_rate_pct"], 0.5, msg)
        self.assertEqual(RATES["socso"]["wage_ceiling"], 6000, msg)
        self.assertEqual(RATES["eis"]["employee_rate_pct"], 0.2, msg)
        self.assertEqual(RATES["eis"]["wage_ceiling"], 6000, msg)
        self.assertEqual(RATES["pcb"]["rough_estimate_pct"], 3.0, msg)
        self.assertEqual(RATES["pcb"]["estimate_threshold"], 3000, msg)
        self.assertEqual(RATES["minimum_wage"]["monthly"], 1700, msg)


class TestGajiGoldenFixtures(unittest.TestCase):
    def _assert_worker(self, result, expected):
        self.assertTrue(result["success"], result.get("error"))
        pw = result["per_worker"]
        for key, val in expected.items():
            self.assertAlmostEqual(
                pw[key], val, places=2,
                msg=f"per_worker[{key}] = {pw[key]}, expected {val}",
            )

    def test_basic_below_thresholds(self):
        # RM2000: no OT, below EPF 5000 threshold, below PCB 3000 threshold.
        r = gaji.calculate({"workers": 1, "gaji_pokok": 2000})
        self._assert_worker(r, {
            "gaji_kasar": 2000.00,
            "epf_employee": 220.00,   # 11%
            "epf_employer": 260.00,   # 13% (<=5000)
            "socso": 10.00,           # 0.5%
            "eis": 4.00,              # 0.2%
            "pcb": 0,                 # 2000 not > 3000
            "total_potongan": 234.00,
            "gaji_bersih": 1766.00,
        })

    def test_above_thresholds_with_pcb(self):
        # RM8000: above EPF 5000 (employer 12%), SOCSO/EIS capped at 6000, PCB applies.
        r = gaji.calculate({"workers": 1, "gaji_pokok": 8000})
        self._assert_worker(r, {
            "gaji_kasar": 8000.00,
            "epf_employee": 880.00,   # 11%
            "epf_employer": 960.00,   # 12% (>5000)
            "socso": 30.00,           # 0.5% of 6000 ceiling
            "eis": 12.00,             # 0.2% of 6000 ceiling
            "pcb": 240.00,            # 3% of 8000
            "total_potongan": 1162.00,
            "gaji_bersih": 6838.00,
        })

    def test_overtime(self):
        # RM2080 -> hourly = 2080/26/8 = 10.00 exactly; 10h OT @1.5 = RM150.00.
        r = gaji.calculate({"workers": 1, "gaji_pokok": 2080, "ot_hours": 10, "ot_rate": 1.5})
        self._assert_worker(r, {
            "ot_pay": 150.00,
            "gaji_kasar": 2230.00,
            "epf_employee": 245.30,
            "epf_employer": 289.90,   # 13% (<=5000)
            "socso": 11.15,
            "eis": 4.46,
            "pcb": 0,                 # 2230 not > 3000
            "gaji_bersih": 1969.09,
        })

    def test_workers_multiplier(self):
        # Totals are per-worker * N.
        r = gaji.calculate({"workers": 3, "gaji_pokok": 2000})
        total = r["total"]
        self.assertEqual(total["workers"], 3)
        self.assertAlmostEqual(total["gaji_bersih"], 5298.00, places=2)  # 1766 * 3
        self.assertAlmostEqual(total["epf_employee"], 660.00, places=2)  # 220 * 3

    def test_minimum_wage_warning(self):
        # Below RM1700 minimum wage -> a warning must be surfaced (trust layer).
        r = gaji.calculate({"workers": 1, "gaji_pokok": 1500})
        self.assertTrue(r["warnings"], "expected a minimum-wage warning")
        self.assertTrue(any("minimum" in w.lower() for w in r["warnings"]))

    def test_no_warning_above_minimum(self):
        r = gaji.calculate({"workers": 1, "gaji_pokok": 2000})
        self.assertFalse(
            any("minimum" in w.lower() for w in r["warnings"]),
            "should not warn when above minimum wage",
        )

    def test_rates_used_reported(self):
        # The result must always report which rates/year it used (auditability).
        r = gaji.calculate({"workers": 1, "gaji_pokok": 3000})
        self.assertEqual(r["rates_used"]["year"], 2026)
        self.assertEqual(r["rates_used"]["epf_employee_pct"], 11.0)


if __name__ == "__main__":
    unittest.main()
