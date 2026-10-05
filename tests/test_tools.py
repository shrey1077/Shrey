"""Tests for the tools and the privacy hook. Run: python3 -m unittest discover -s tests

Expected figures are worked out by hand from the slab tables.
"""

import os
import sys
import unittest
from datetime import date, time, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from advance_tax import schedule  # noqa: E402
from capital_gains import analyse  # noqa: E402
from fmt import inr  # noqa: E402
from income_tax import TaxInput, breakeven_extra_deductions, compare, compute, hra_exemption  # noqa: E402
from planner import emi_plan, real_return, sip_future_value, xirr  # noqa: E402
from health import needs  # noqa: E402
from sessions import EXAMPLE, plan, widget_feed  # noqa: E402
from when import clock_change, parse_moment, shared_hours, shift, zone  # noqa: E402
from whatsapp import config, screen, template_payload, text_payload  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".claude", "hooks"))

from guard_private_data import SECRET_FILES, check, problems_in_diff  # noqa: E402


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


class When(unittest.TestCase):
    def test_workdays_skip_weekends(self):
        self.assertEqual(shift(date(2026, 10, 4), workdays=5), date(2026, 10, 9))  # Sun -> Fri
        self.assertEqual(shift(date(2026, 10, 9), workdays=1), date(2026, 10, 12))  # Fri -> Mon
        self.assertEqual(shift(date(2026, 10, 12), workdays=-1), date(2026, 10, 9))

    def test_months_clamp_to_month_end(self):
        self.assertEqual(shift(date(2027, 1, 31), months=1), date(2027, 2, 28))
        self.assertEqual(shift(date(2026, 10, 4), months=-12), date(2025, 10, 4))

    def test_conversion_follows_us_daylight_saving(self):
        # New York is UTC-4 until 1 Nov 2026, then UTC-5. India has no daylight saving.
        ny, ist = zone("new york"), zone("IST")
        before = parse_moment("2026-10-14 9:00 am", ny, date(2026, 10, 4)).astimezone(ist)
        after = parse_moment("2026-11-04 09:00", ny, date(2026, 10, 4)).astimezone(ist)
        self.assertEqual((before.hour, before.minute), (18, 30))
        self.assertEqual((after.hour, after.minute), (19, 30))

    def test_clock_changes_flagged(self):
        ny = zone("America/New_York")
        self.assertIn("doesn't exist", clock_change(parse_moment("2026-03-08 02:30", ny, date(2026, 1, 1))))
        self.assertIn("twice", clock_change(parse_moment("2026-11-01 01:30", ny, date(2026, 1, 1))))
        self.assertIsNone(clock_change(parse_moment("2026-11-01 12:00", ny, date(2026, 1, 1))))

    def test_shared_hours_india_new_york(self):
        ist, ny = zone("Asia/Kolkata"), zone("America/New_York")
        nine, six, seven = time(9), time(18), time(19)
        self.assertEqual(shared_hours(date(2026, 10, 14), [(ist, nine, six), (ny, nine, six)]), [])
        [(start, end)] = shared_hours(date(2026, 10, 14), [(ist, nine, seven), (ny, nine, seven)])
        self.assertEqual(start.astimezone(ist).strftime("%H:%M"), "18:30")
        self.assertEqual(end - start, timedelta(minutes=30))

    def test_shared_hours_across_the_date_line(self):
        # Sydney's Wednesday morning is California's Tuesday afternoon.
        syd, sf = zone("sydney"), zone("san francisco")
        [(start, end)] = shared_hours(date(2026, 10, 14), [(syd, time(9), time(18)), (sf, time(9), time(18))])
        self.assertEqual(start.astimezone(sf).strftime("%a %H:%M"), "Tue 15:00")
        self.assertEqual(end - start, timedelta(hours=3))

    def test_unknown_zone_suggests(self):
        with self.assertRaisesRegex(ValueError, "America/New_York"):
            zone("york")


def _day(**over):
    spec = {"date": "2026-10-05", "day_start": "07:00", "day_end": "22:00", "anchors": [], "fixed": [],
            "tasks": [], "settings": {"focus_hours": ["09:00-18:00"], "peak_hours": ["10:00-12:00"]}}
    spec.update(over)
    return plan(spec)


class Sessions(unittest.TestCase):
    def test_long_task_is_split_with_breaks(self):
        r = _day(tasks=[{"id": "t", "title": "Deck", "minutes": 120, "priority": 1}])
        focus = [b for b in r["blocks"] if b["kind"] == "focus"]
        self.assertEqual([b["end"] - b["start"] for b in focus], [45, 45, 30])
        self.assertEqual(focus[0]["start"], 9 * 60)  # not before focus hours
        self.assertEqual(focus[1]["start"] - focus[0]["end"], 10)  # a break in between
        self.assertEqual(focus[0]["title"], "Deck (1/3)")

    def test_no_scrap_sessions(self):
        r = _day(tasks=[{"title": "Report", "minutes": 50}])
        self.assertEqual([b["end"] - b["start"] for b in r["blocks"] if b["kind"] == "focus"], [50])

    def test_meeting_gets_buffer_and_reset(self):
        r = _day(fixed=[{"title": "Call", "start": "11:00", "end": "11:30", "kind": "meeting"}])
        kinds = {b["kind"]: (b["start"], b["end"]) for b in r["blocks"]}
        self.assertEqual(kinds["buffer"], (10 * 60 + 50, 11 * 60))
        self.assertEqual(kinds["reset"], (11 * 60 + 30, 11 * 60 + 35))

    def test_high_energy_waits_for_peak_but_priority_wins(self):
        r = _day(tasks=[{"title": "Hard", "minutes": 40, "priority": 2, "energy": "high"},
                        {"title": "Easy", "minutes": 40, "priority": 2, "energy": "low"}])
        first = min((b for b in r["blocks"] if b["kind"] == "focus"), key=lambda b: b["start"])
        self.assertEqual(first["title"], "Easy")
        r = _day(tasks=[{"title": "Hard", "minutes": 40, "priority": 1, "energy": "high"},
                        {"title": "Chore", "minutes": 40, "priority": 4, "energy": "low"}])
        first = min((b for b in r["blocks"] if b["kind"] == "focus"), key=lambda b: b["start"])
        self.assertEqual(first["title"], "Hard")

    def test_focus_cap_reports_what_did_not_fit(self):
        r = _day(tasks=[{"id": "a", "title": "A", "minutes": 200}, {"id": "b", "title": "B", "minutes": 200}],
                 settings={"focus_hours": ["09:00-18:00"], "peak_hours": [], "max_focus_minutes": 240})
        self.assertEqual(r["focus_minutes"], 240)
        self.assertEqual(sum(t["minutes"] for t in r["unscheduled"]), 160)

    def test_task_window_and_clashes(self):
        r = _day(tasks=[{"title": "Chess", "minutes": 30, "window": "18:00-21:00"}],
                 anchors=[{"title": "Lunch", "start": "13:00", "minutes": 45, "kind": "meal"}],
                 fixed=[{"title": "Dentist", "start": "13:30", "end": "14:00", "kind": "event"}])
        chess = next(b for b in r["blocks"] if b["kind"] == "focus")
        self.assertEqual(chess["start"], 18 * 60)
        self.assertEqual(len(r["clashes"]), 1)

    def test_widget_feed_shape(self):
        feed = widget_feed(EXAMPLE, plan(EXAMPLE))
        self.assertEqual(feed["version"], 1)
        self.assertTrue(all({"id", "start", "end", "kind", "title"} <= set(b) for b in feed["blocks"]))
        self.assertRegex(feed["blocks"][0]["start"], r"^\d\d:\d\d$")


class WhatsApp(unittest.TestCase):
    def test_screen_blocks_secrets_and_identifiers(self):
        self.assertTrue(screen("Your OTP is 482913"))
        # Built from pieces so this file doesn't trip the commit hook it is testing alongside.
        self.assertTrue(screen("PAN " + "ABCPE" + "1234F on file"))
        self.assertTrue(screen("Card 4111 1111 " + "1111 1111"))
        self.assertTrue(screen("A/c 123456789012 credited"))
        self.assertTrue(screen("x" * 1200))
        self.assertEqual(screen("Breakfast. Now. Poha or eggs, your call."), [])
        self.assertEqual(screen("Session 2 at 10:30: Q3 deck, 45 min"), [])

    def test_config_requires_env_and_pins_recipient(self):
        with self.assertRaisesRegex(RuntimeError, "WHATSAPP_TOKEN"):
            config({})
        env = {"WHATSAPP_TOKEN": "t", "WHATSAPP_PHONE_NUMBER_ID": "123456789", "WHATSAPP_TO": "+15550001111"}
        cfg = config(env)
        self.assertEqual(cfg["to"], "15550001111")
        self.assertIn("/v26.0/123456789/messages", cfg["url"])
        with self.assertRaises(RuntimeError):
            config({**env, "WHATSAPP_TO": "not-a-number"})

    def test_payloads(self):
        self.assertEqual(text_payload("91", "hi")["text"]["body"], "hi")
        t = template_payload("91", "donna_nudge", ["Deck at 10"])
        self.assertEqual(t["template"]["components"][0]["parameters"][0]["text"], "Deck at 10")
        with self.assertRaises(ValueError):
            template_payload("91", "Bad Name", [])


class Health(unittest.TestCase):
    def test_mifflin_st_jeor_and_asian_bmi(self):
        # 10*78 + 6.25*175 - 5*30 + 5 = 1728.75; x1.375 = 2377; BMI 25.5 is obese on Asian cut-offs.
        r = needs("male", 30, 175, 78, "light", "maintain")
        self.assertEqual((r["bmr_kcal"], r["tdee_kcal"]), (1729, 2377))
        self.assertEqual((r["bmi"], r["bmi_band_asian"]), (25.5, "obese"))

    def test_loss_target_never_below_bmr(self):
        r = needs("female", 28, 160, 55, "sedentary", "lose")
        self.assertGreaterEqual(r["target_kcal"], r["bmr_kcal"] - 5)


class PrivacyHook(unittest.TestCase):
    def test_force_adding_private_folders_is_blocked(self):
        self.assertTrue(check("git add -f finance/private/profile.yaml"))
        self.assertTrue(check("git add --force secretary/private/tasks.md"))
        self.assertFalse(check("git add tools/when.py"))

    def test_tokens_and_keys_in_diffs_are_caught(self):
        fakes = ["EAA" + "B" * 40, "AKIA" + "ABCDEFGHIJKLMNOP", "ghp_" + "a" * 36,
                 "-----BEGIN " + "OPENSSH PRIVATE KEY-----", 'api_key = "' + "z" * 20 + '"']
        for fake in fakes:
            self.assertTrue(problems_in_diff(f"+++ b/x.py\n+token = {fake}\n"), fake)
        self.assertEqual(problems_in_diff("+++ b/x.py\n+WHATSAPP_TOKEN = os.environ['WHATSAPP_TOKEN']\n"), [])

    def test_credential_files(self):
        for path in [".env", "widget/.env.local", "keys/donna.pem", "client_secret_123.json", "token.json"]:
            self.assertTrue(SECRET_FILES.search(path), path)
        for path in ["tools/whatsapp.py", "secretary/whatsapp-setup.md", "widget/package.json"]:
            self.assertFalse(SECRET_FILES.search(path), path)


if __name__ == "__main__":
    unittest.main()
