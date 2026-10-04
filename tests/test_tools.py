"""Tests for the calculators. Run: python3 -m unittest discover -s tests

Expected figures are worked out by hand from the slab tables.
"""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from advance_tax import schedule  # noqa: E402
from capital_gains import analyse  # noqa: E402
from fmt import inr  # noqa: E402
from income_tax import TaxInput, breakeven_extra_deductions, compare, compute, hra_exemption, round_tax  # noqa: E402
from planner import emi_plan, real_return, sip_future_value, xirr  # noqa: E402


def tax(regime, **kw):
    return compute(TaxInput(**kw), regime)["total_tax"]


class NewRegime(unittest.TestCase):
    def test_zero_tax_up_to_12_75_lakh_salary(self):
        self.assertEqual(tax("new", salary=1_275_000), 0)

    def test_marginal_relief_above_rebate_limit(self):
        # Total income 12.15L: tax capped at the 15,000 earned above 12L, plus cess.
        self.assertEqual(tax("new", salary=1_290_000), 15_600)

    def test_slabs(self):
        # 17.25L: 20k + 40k + 60k + 25k = 1,45,000 + 4% cess.
        self.assertEqual(tax("new", salary=1_800_000), 150_800)

    def test_rebate_does_not_cover_special_rate_gains(self):
        # Slab income 8L is fully rebated; 20% on 2L STCG is not.
        self.assertEqual(tax("new", salary=875_000, stcg_111a=200_000), 41_600)

    def test_unused_basic_exemption_absorbs_ltcg(self):
        # 6L LTCG: 1.25L exempt, 4L basic exemption used, 75k taxed at 12.5%.
        self.assertEqual(tax("new", ltcg_112a=600_000), 9_750)

    def test_surcharge_marginal_relief(self):
        # Total income 50.1L. Tax may exceed tax at 50L only by the 10k earned above it.
        result = compute(TaxInput(salary=5_085_000), "new")
        self.assertEqual(result["total_income"], 5_010_000)
        self.assertAlmostEqual(result["surcharge"], 7_000)
        self.assertEqual(result["total_tax"], 1_133_600)

    def test_self_occupied_home_loan_interest_ignored(self):
        self.assertEqual(tax("new", salary=1_800_000, home_loan_interest_self=200_000), 150_800)


class OldRegime(unittest.TestCase):
    def test_full_rebate_at_5_lakh(self):
        self.assertEqual(tax("old", salary=550_000), 0)

    def test_hra_and_deductions(self):
        kw = dict(salary=1_800_000, basic_da=720_000, hra_received=288_000, rent_paid=300_000,
                  metro=True, d80c=150_000, d80d_self=25_000)
        result = compute(TaxInput(**kw), "old")
        self.assertEqual(result["salary_exemptions"], 228_000)
        self.assertEqual(result["total_income"], 1_347_000)
        self.assertEqual(result["total_tax"], 225_260)

    def test_senior_citizen_slabs(self):
        # 5.5L at age 65: 5% on 3-5L + 20% on 5-5.5L = 20,000 + cess.
        self.assertEqual(tax("old", age=65, salary=600_000), 20_800)

    def test_caps(self):
        result = compute(TaxInput(salary=2_000_000, home_loan_interest_self=300_000, d80c=300_000,
                                  d80d_self=40_000), "old")
        self.assertEqual(result["income_from_house_property"], -200_000)
        self.assertEqual(result["deductions"]["80C"], 150_000)
        self.assertEqual(result["deductions"]["80D health insurance"], 25_000)

    def test_rounding_288b(self):
        self.assertEqual(round_tax(225265.0), 225270)  # 5 rounds up, not to even
        self.assertEqual(round_tax(225264.99), 225260)  # paise are dropped first
        self.assertEqual(round_tax(225255.4), 225260)

    def test_hra_formula(self):
        self.assertEqual(hra_exemption(600_000, 240_000, 180_000, metro=False), 120_000)
        self.assertEqual(hra_exemption(600_000, 240_000, 0, metro=True), 0)


class Comparison(unittest.TestCase):
    def test_breakeven_makes_old_no_worse(self):
        inp = TaxInput(salary=2_400_000, d80c=150_000)
        result = compare(inp)
        self.assertEqual(result["recommended"], "new")
        extra = breakeven_extra_deductions(inp, result["new"]["total_tax"])
        trial = TaxInput(salary=2_400_000, d80c=150_000, other_deductions=extra)
        self.assertLessEqual(compute(trial, "old")["total_tax"], result["new"]["total_tax"])


class CapitalGains(unittest.TestCase):
    def test_equity_holding_boundary(self):
        short = analyse("equity", date(2025, 1, 15), date(2026, 1, 15), 100, 200)
        long = analyse("equity", date(2025, 1, 15), date(2026, 1, 16), 100, 200)
        self.assertFalse(short["long_term"])
        self.assertEqual(short["section"], "111A")
        self.assertTrue(long["long_term"])
        self.assertEqual(long["section"], "112A")

    def test_debt_fund_dates(self):
        self.assertEqual(analyse("debt_mf", date(2023, 6, 1), date(2026, 6, 1), 100, 130)["section"], "50AA")
        old_fund = analyse("debt_mf", date(2022, 6, 1), date(2026, 6, 1), 100, 130)
        self.assertTrue(old_fund["long_term"])
        self.assertEqual(old_fund["section"], "112")

    def test_property_picks_cheaper_option(self):
        r = analyse("property", date(2015, 6, 1), date(2026, 9, 15), 4_500_000, 9_500_000, expenses=150_000)
        self.assertAlmostEqual(r["indexed_cost"], 4_500_000 * 384 / 254)
        self.assertEqual(r["income_tax_flag"], "--ltcg-112-indexed")
        self.assertLess(r["tax_with_indexation"], r["tax_without_indexation"])

    def test_grandfathering(self):
        r = analyse("equity", date(2017, 1, 1), date(2026, 1, 1), 100_000, 300_000, fmv_2018=180_000)
        self.assertEqual(r["gain"], 120_000)

    def test_old_sales_rejected(self):
        with self.assertRaises(ValueError):
            analyse("equity", date(2020, 1, 1), date(2024, 7, 1), 100, 200)


class AdvanceTax(unittest.TestCase):
    def test_schedule_and_234c(self):
        r = schedule(320_000, 180_000, "2026-27", [0, 50_000, 40_000, 50_000])
        self.assertEqual([row["cumulative_due"] for row in r["instalments"]], [21_000, 63_000, 105_000, 140_000])
        # 3% on 21,000 + 3% on 13,000 + 3% on 15,000.
        self.assertAlmostEqual(r["interest_234c"], 1_470)

    def test_not_required_below_threshold(self):
        self.assertFalse(schedule(50_000, 45_000)["required"])

    def test_234b(self):
        r = schedule(200_000, 0, "2026-27", [0, 0, 0, 0], filing_date=date(2027, 7, 20))
        self.assertEqual(r["months_234b"], 4)
        self.assertAlmostEqual(r["interest_234b"], 8_000)


class Planner(unittest.TestCase):
    def test_emi(self):
        self.assertAlmostEqual(emi_plan(5_000_000, 8.5, 20)["emi"], 43_391, delta=1)

    def test_sip_matches_closed_form(self):
        i = (1.12) ** (1 / 12) - 1
        expected = 10_000 * ((1 + i) ** 120 - 1) / i * (1 + i)
        self.assertAlmostEqual(sip_future_value(10_000, 12, 10)["future_value"], expected, places=2)

    def test_real_return(self):
        self.assertAlmostEqual(real_return(6, 6)["real_return"], 0.0)

    def test_xirr(self):
        self.assertAlmostEqual(xirr([(date(2025, 1, 1), -100), (date(2026, 1, 1), 200)]), 1.0, places=4)


class Formatting(unittest.TestCase):
    def test_indian_grouping(self):
        self.assertEqual(inr(1_234_567), "₹12,34,567")
        self.assertEqual(inr(999), "₹999")
        self.assertEqual(inr(-150_000), "-₹1,50,000")


if __name__ == "__main__":
    unittest.main()
