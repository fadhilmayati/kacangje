#!/usr/bin/env python3
"""
Regression tests for invoice.py and quotation.py — input validation guards.

Run: python3 -m unittest discover -s tests -v
"""
import importlib.util, os, unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("KACANGJE_DIR", str(REPO_ROOT))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "actions" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


invoice = _load("invoice")
quotation = _load("quotation")

GOOD_ITEMS = [["Servis A", 2, 100], ["Servis B", 1, 250]]


class TestInvoiceValidation(unittest.TestCase):
    def test_happy_path(self):
        r = invoice.generate({"client": "Ali Sdn Bhd", "items": GOOD_ITEMS})
        self.assertTrue(r["success"])
        self.assertAlmostEqual(r["total"], 486.0)  # (200+250)*1.08

    def test_empty_items(self):
        r = invoice.generate({"items": []})
        self.assertFalse(r["success"])
        self.assertIn("item", r["error"].lower())

    def test_negative_tax_rate(self):
        r = invoice.generate({"items": GOOD_ITEMS, "tax_rate": -5})
        self.assertFalse(r["success"])
        self.assertIn("cukai", r["error"])

    def test_tax_rate_over_100(self):
        r = invoice.generate({"items": GOOD_ITEMS, "tax_rate": 150})
        self.assertFalse(r["success"])

    def test_negative_discount(self):
        r = invoice.generate({"items": GOOD_ITEMS, "discount": -50})
        self.assertFalse(r["success"])
        self.assertIn("diskaun", r["error"].lower())

    def test_negative_item_price(self):
        r = invoice.generate({"items": [["Servis A", 1, -100]]})
        self.assertFalse(r["success"])
        self.assertIn("negatif", r["error"])

    def test_negative_item_qty(self):
        r = invoice.generate({"items": [["Servis A", -1, 100]]})
        self.assertFalse(r["success"])

    def test_zero_tax_allowed(self):
        r = invoice.generate({"items": GOOD_ITEMS, "tax_rate": 0})
        self.assertTrue(r["success"])
        self.assertAlmostEqual(r["total"], 450.0)


class TestQuotationValidation(unittest.TestCase):
    def test_happy_path(self):
        r = quotation.generate({"client": "Kedai Ali", "items": GOOD_ITEMS})
        self.assertTrue(r["success"])

    def test_empty_items(self):
        r = quotation.generate({"items": []})
        self.assertFalse(r["success"])

    def test_negative_tax_rate(self):
        r = quotation.generate({"items": GOOD_ITEMS, "tax_rate": -1})
        self.assertFalse(r["success"])

    def test_negative_discount(self):
        r = quotation.generate({"items": GOOD_ITEMS, "discount": -10})
        self.assertFalse(r["success"])

    def test_negative_item_price(self):
        r = quotation.generate({"items": [["Kerja A", 1, -50]]})
        self.assertFalse(r["success"])

    def test_negative_item_qty(self):
        r = quotation.generate({"items": [["Kerja A", -2, 50]]})
        self.assertFalse(r["success"])

    def test_zero_tax_allowed(self):
        r = quotation.generate({"items": GOOD_ITEMS, "tax_rate": 0})
        self.assertTrue(r["success"])


if __name__ == "__main__":
    unittest.main()
