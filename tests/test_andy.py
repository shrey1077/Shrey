"""Tests for Andy. Run: python3 -m unittest discover -s tests

They use development mode (ANDY_DEV=1) and a throwaway data folder, never a real vault.
"""

import email
import email.policy
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["ANDY_DEV"] = "1"
_HOME = tempfile.mkdtemp(prefix="andy-test-")
os.environ["ANDY_HOME"] = _HOME

from andy import donna, gmail, vault  # noqa: E402
from andy.categorize import categorize  # noqa: E402
from andy.gmail import Alert  # noqa: E402
from andy.parser import parse_alert  # noqa: E402
from andy.service import AndyService, ServiceError  # noqa: E402

vault.SCRYPT_PARAMS = {"n": 2**12, "r": 8, "p": 1}  # fast for tests; real vaults use 2**17
PASS = "Correct-Horse-42-Battery"
R = datetime(2026, 10, 8, 20, 15)


def fresh_service() -> AndyService:
    path = Path(tempfile.mkdtemp(dir=_HOME)) / "vault.andy"
    return AndyService(vault.Vault(path))


class VaultTests(unittest.TestCase):
    def test_round_trip_and_wrong_passphrase(self):
        svc = fresh_service()
        code = svc.create(PASS, PASS)["recovery_code"]
        self.assertRegex(code, r"^([A-Z2-9]{5}-){7}[A-Z2-9]{5}$")
        svc.save_profile({"name": "Shrey", "monthly_take_home": "1,20,000"})
        svc.lock()
        with self.assertRaises(ServiceError):
            svc.unlock("wrong passphrase 123!")
        svc.unlock(PASS)
        self.assertEqual(svc.get_profile()["profile"]["monthly_take_home"], 120000)

    def test_file_never_contains_plaintext(self):
        svc = fresh_service()
        svc.create(PASS, PASS)
        svc.save_profile({"name": "Zebrafinch", "city": "Pune"})
        raw = svc.vault.path.read_text()
        self.assertNotIn("Zebrafinch", raw)
        self.assertNotIn("Pune", raw)
        self.assertNotIn(PASS, raw)

    def test_tampering_is_detected(self):
        svc = fresh_service()
        svc.create(PASS, PASS)
        svc.lock()
        header = json.loads(svc.vault.path.read_text())
        ct = bytearray(vault._unb64(header["data"]["ct"]))
        ct[5] ^= 0x01
        header["data"]["ct"] = vault._b64(bytes(ct))
        svc.vault.path.write_text(json.dumps(header))
        with self.assertRaises(ServiceError) as ctx:
            svc.unlock(PASS)
        self.assertIn("integrity", str(ctx.exception))

    def test_recovery_code_sets_new_passphrase(self):
        svc = fresh_service()
        code = svc.create(PASS, PASS)["recovery_code"]
        svc.lock()
        new = "Another-Long-Pass-77"
        svc.recover(code.lower().replace("-", " "), new, new)
        svc.lock()
        with self.assertRaises(ServiceError):
            svc.unlock(PASS)
        svc.unlock(new)

    def test_weak_passphrases_rejected(self):
        for weak in ("short1!", "alllowercaseletters", "password"):
            with self.assertRaises(ServiceError):
                fresh_service().create(weak, weak)

    def test_confirm_recovery_needs_last_group(self):
        svc = fresh_service()
        code = svc.create(PASS, PASS)["recovery_code"]
        with self.assertRaises(ServiceError):
            svc.confirm_recovery("AAAAA")
        svc.confirm_recovery(code[-5:].lower())
        self.assertTrue(svc.status()["recovery_confirmed"])

    def test_locked_service_refuses_data(self):
        svc = fresh_service()
        svc.create(PASS, PASS)
        svc.lock()
        with self.assertRaises(ServiceError):
            svc.get_profile()


SAMPLES = [
    ("HDFC", "Rs.250.00 has been debited from account **4321 to VPA swiggy.stores@axb SWIGGY on 08-10-26. "
             "Your UPI transaction reference number is 112233445566.", (250.0, "expense", "SWIGGY", "Food delivery", "XX4321", "2026-10-08")),
    ("ICICI", "INR 1,249.00 spent on ICICI Bank Credit Card XX9876 on 07-Oct-26 at AMAZON PAY INDIA. Avl Limit: INR 1,85,200.50.",
     (1249.0, "expense", "AMAZON PAY INDIA", "Shopping", "XX9876", "2026-10-07")),
    ("UPI", "Rs.649.00 has been debited from account **4321 to VPA netflixupi.payu@hdfcbank on 05-10-26.",
     (649.0, "expense", "Netflix", "Subscriptions", "XX4321", "2026-10-05")),
    ("Salary", "Rs. 85,000.00 credited to your A/c XX4321 on 01-10-2026 by NEFT from ACME TECHNOLOGIES PVT LTD. Avl Bal Rs 1,23,456.00",
     (85000.0, "income", "ACME TECHNOLOGIES PVT LTD", None, "XX4321", "2026-10-01")),
    ("ATM", "Rs 5,000.00 withdrawn from A/c XX4321 at ATM on 06/10/26 10:42 AM. Avl Bal Rs 1,18,456.00",
     (5000.0, "expense", "ATM cash withdrawal", "Cash withdrawal", "XX4321", "2026-10-06")),
    ("SBI Card", "Rs.3,450.00 spent on your SBI Credit Card ending 5566 at ZOMATO on 04/10/26. Trxn. not done by you? Report it.",
     (3450.0, "expense", "ZOMATO", "Food delivery", "XX5566", "2026-10-04")),
    ("Axis", "INR 1,200.00 debited A/c no. XX4321 08-10-26, 09:15:20 UPI/P2M/101234567890/BLINKIT Not you? Call us.",
     (1200.0, "expense", "BLINKIT", "Groceries", "XX4321", "2026-10-08")),
    ("Refund", "Refund of Rs. 349.00 has been credited to your card XX9876 from MYNTRA on 06-Oct-26.",
     (349.0, "refund", "MYNTRA", "Shopping", "XX9876", "2026-10-06")),
]


class ParserTests(unittest.TestCase):
    def test_bank_formats(self):
        for subject, body, (amount, kind, merchant, category, account, when) in SAMPLES:
            with self.subTest(subject):
                p = parse_alert(subject, body, R)
                self.assertIsNotNone(p)
                self.assertEqual((p.amount, p.kind, p.merchant, p.account, p.date), (amount, kind, merchant, account, when))
                if category:
                    self.assertEqual(categorize(p.merchant, p.context), category)

    def test_ignores_non_transactions(self):
        for subject, body in [
            ("OTP", "Your OTP for transaction of Rs 499 at Myntra is 123456. Do not share it."),
            ("Declined", "Your transaction of INR 2,000 at FLIPKART was declined due to insufficient funds."),
            ("Offer", "Get cashback of up to Rs 500 on your next spend. Offer valid till Sunday."),
            ("Request", "Zomato has sent you a payment request of Rs 300 on your UPI app."),
        ]:
            with self.subTest(subject):
                self.assertIsNone(parse_alert(subject, body, R))

    def test_long_numbers_are_masked(self):
        p = parse_alert("UPI", "Sent Rs.120.00 from AC X4321 to 9876501234@ybl on 08-10-26. UPI Ref 101122334455.", R)
        self.assertEqual(p.merchant, "UPI transfer to a phone number")
        self.assertNotRegex(p.context, r"\d{6,}")


def gmail_message(sender: str, auth: str, body: str) -> email.message.Message:
    raw = (f"From: Alerts <{sender}>\r\nAuthentication-Results: {auth}\r\nSubject: Alert\r\n"
           f"Date: Thu, 08 Oct 2026 20:15:00 +0530\r\nMessage-ID: <x@y>\r\n\r\n{body}\r\n")
    return email.message_from_string(raw, policy=email.policy.default)


class GmailTrustTests(unittest.TestCase):
    def test_requires_trusted_authenticated_sender(self):
        good = gmail_message("alerts@hdfcbank.net", "mx.google.com; dkim=pass header.i=@hdfcbank.net; spf=pass; "
                             "dmarc=pass (p=REJECT) header.from=hdfcbank.net", "x")
        spoof = gmail_message("alerts@hdfcbank.net", "mx.google.com; dkim=fail; spf=fail; dmarc=fail header.from=hdfcbank.net", "x")
        stranger = gmail_message("deals@shop.example", "mx.google.com; dkim=pass header.i=@shop.example; dmarc=pass header.from=shop.example", "x")
        injected = gmail_message("alerts@hdfcbank.net", "attacker.example; dkim=pass header.i=@hdfcbank.net; dmarc=pass header.from=hdfcbank.net", "x")
        self.assertEqual(gmail.authenticated_domain(good, gmail.TRUSTED_DOMAINS), "hdfcbank.net")
        self.assertIsNone(gmail.authenticated_domain(spoof, gmail.TRUSTED_DOMAINS))
        self.assertIsNone(gmail.authenticated_domain(stranger, gmail.TRUSTED_DOMAINS))
        self.assertIsNone(gmail.authenticated_domain(injected, gmail.TRUSTED_DOMAINS))


class ServiceFlowTests(unittest.TestCase):
    def setUp(self):
        self.svc = fresh_service()
        self.svc.create(PASS, PASS)
        self.svc.save_profile({"name": "Shrey", "monthly_take_home": 120000, "annual_gross_salary": 1800000,
                               "basic_da": 720000, "monthly_rent": 25000, "metro": True})

    def test_gmail_sync_ingests_and_dedupes(self):
        self.svc.vault.data["gmail"].update(address="me@gmail.com", app_password="abcdabcdabcdabcd")
        alerts = [Alert(f"h{i}", "hdfcbank.net", s, b, R) for i, (s, b, _) in enumerate(SAMPLES)]

        def fake_fetch(address, password, since, seen, trusted):
            return [a for a in alerts if a.uid_hash not in seen], {"found": len(alerts), "new": len(alerts)}

        first = self.svc.gmail_sync(fetcher=fake_fetch, today=date(2026, 10, 8))
        self.assertEqual(first["added"], len(SAMPLES))
        again = self.svc.gmail_sync(fetcher=fake_fetch, today=date(2026, 10, 8))
        self.assertEqual(again["added"], 0)
        # The same purchase reported again by a different email is not counted twice.
        dup = [Alert("other", "hdfcbank.net", SAMPLES[0][0], SAMPLES[0][1], R)]
        self.assertEqual(self.svc.gmail_sync(fetcher=lambda *a: (dup, {"found": 1, "new": 1}), today=date(2026, 10, 8))["added"], 0)

        view = self.svc.view("month", "2026-10-01", today=date(2026, 10, 8))
        # Expenses minus the Myntra refund; salary is income, not spending.
        expected = 250 + 1249 + 649 + 5000 + 3450 + 1200 - 349
        self.assertAlmostEqual(view["total"], expected)
        self.assertAlmostEqual(view["income"], 85000)
        day = self.svc.view("day", "2026-10-08", today=date(2026, 10, 8))
        self.assertAlmostEqual(day["total"], 250 + 1200)
        year = self.svc.view("year", "2026-06-01", today=date(2026, 10, 8))
        self.assertAlmostEqual(year["series"][9]["total"], expected)

    def test_remembered_category_applies_to_merchant(self):
        a = self.svc.add_transaction({"amount": 400, "date": "2026-10-02", "merchant": "Ravi Stores"})
        b = self.svc.add_transaction({"amount": 600, "date": "2026-10-03", "merchant": "Ravi Stores"})
        self.svc.update_transaction(a["id"], {"category": "Groceries", "remember": True})
        txns = {t["id"]: t for t in self.svc.vault.data["transactions"]}
        self.assertEqual(txns[b["id"]]["category"], "Groceries")
        c = self.svc.add_transaction({"amount": 50, "date": "2026-10-04", "merchant": "RAVI STORES"})
        self.assertEqual(c["category"], "Groceries")

    def test_insights_find_subscriptions_and_food(self):
        today = date(2026, 10, 20)
        for months_back in range(3):
            d = (today.replace(day=5) - timedelta(days=31 * months_back)).replace(day=5)
            self.svc.add_transaction({"amount": 649, "date": d.isoformat(), "merchant": "Netflix", "category": "Subscriptions"})
            self.svc.add_transaction({"amount": 119, "date": d.isoformat(), "merchant": "Spotify", "category": "Subscriptions"})
        for i in range(36):
            self.svc.add_transaction({"amount": 450, "date": (today - timedelta(days=i * 2)).isoformat(), "merchant": "Swiggy"})
        result = self.svc.insights(today=today)
        kinds = {item["kind"] for item in result["items"]}
        self.assertIn("subscriptions", kinds)
        self.assertIn("habit", kinds)
        self.assertGreater(result["total_monthly"], 0)
        food = next(i for i in result["items"] if i["category"] == "Food delivery")
        self.assertGreater(food["monthly_saving"], 2000)

    def test_tax_overview_uses_shared_engine(self):
        t = self.svc.tax_overview()
        self.assertIsNotNone(t["comparison"])
        self.assertIn(t["comparison"]["recommended"], ("old", "new"))

    def test_profile_validation(self):
        with self.assertRaises(ServiceError):
            self.svc.save_profile({"age": 7})
        with self.assertRaises(ServiceError):
            self.svc.save_profile({"employment": "astronaut"})
        saved = self.svc.save_profile({"name": "  Shrey\x00<script>  ", "unknown_field": "ignored"})
        self.assertEqual(saved["profile"]["name"], "Shrey <script>")
        self.assertNotIn("unknown_field", saved["profile"])


class DonnaTests(unittest.TestCase):
    def setUp(self):
        self.svc = fresh_service()
        self.svc.create(PASS, PASS)
        self.pair = self.svc.donna_pair(PASS)
        self.key = donna.parse_pairing_string(self.pair["pairing_key"])
        self.inbox, self.outbox = Path(self.pair["inbox"]), Path(self.pair["outbox"])
        for folder in (self.inbox, self.outbox):
            for f in folder.glob("*"):
                f.unlink()

    def send(self, body, key=None):
        return donna.write_message(self.inbox, key or self.key, donna.TO_ANDY, body)

    def test_pairing_needs_passphrase(self):
        with self.assertRaises(ServiceError):
            self.svc.donna_pair("not my passphrase 1!")

    def test_request_needs_approval_and_passphrase_above_threshold(self):
        self.send({"type": "expense_request", "amount": 12000, "payee": "Croma", "purpose": "New phone"})
        self.send({"type": "expense_request", "amount": 499, "payee": "Cult.fit", "purpose": "Gym"})
        self.assertEqual(self.svc.donna_check()["new"], 2)
        reqs = {r["payee"]: r for r in self.svc.donna_requests()["requests"]}
        self.assertTrue(reqs["Croma"]["needs_passphrase"])
        with self.assertRaises(ServiceError):
            self.svc.donna_decide(reqs["Croma"]["id"], "approved")
        self.svc.donna_decide(reqs["Croma"]["id"], "approved", passphrase=PASS)
        self.svc.donna_decide(reqs["Cult.fit"]["id"], "rejected", note="Not this month")
        replies = [donna.open_envelope(self.key, donna.TO_DONNA, json.loads(p.read_text())) for p in self.outbox.glob("*.json")]
        self.assertEqual(sorted(r["decision"] for r in replies), ["approved", "rejected"])
        with self.assertRaises(ServiceError):
            self.svc.donna_decide(reqs["Croma"]["id"], "rejected")

    def test_forged_replayed_stale_and_reflected_messages_rejected(self):
        body = {"type": "expense_request", "amount": 100, "payee": "X", "purpose": "Y"}
        self.send(body, key=os.urandom(32))  # wrong key
        path = self.send(body)
        copy = path.read_text()
        stale = donna.seal(self.key, donna.TO_ANDY, body)
        stale["ts"] -= donna.MAX_AGE_SECONDS + 10
        (self.inbox / "stale.json").write_text(json.dumps(stale))
        reflected = donna.seal(self.key, donna.TO_DONNA, body)  # Andy's own direction key
        (self.inbox / "reflected.json").write_text(json.dumps(reflected))
        (self.inbox / "big.json").write_text("x" * (donna.MAX_FILE_BYTES + 1))
        result = self.svc.donna_check()
        self.assertEqual(result["new"], 1)
        self.assertEqual(len(result["rejected"]), 4)
        (self.inbox / "replay.json").write_text(copy)
        result = self.svc.donna_check()
        self.assertEqual(result["new"], 0)
        self.assertIn("Replayed", result["rejected"][0])

    def test_only_allowed_request_types(self):
        for body in ({"type": "pay_now", "amount": 10}, {"type": "expense_request", "amount": -5, "payee": "a", "purpose": "b"},
                     {"type": "expense_request", "amount": 10_00_001, "payee": "a", "purpose": "b"},
                     {"type": "summary_request", "period": "all_time"}):
            with self.subTest(body=body), self.assertRaises(donna.DonnaError):
                donna.validate_request(body)

    def test_summary_shared_only_after_approval(self):
        self.svc.add_transaction({"amount": 300, "merchant": "Blinkit"})
        self.send({"type": "summary_request", "period": "this_month", "reason": "Weekend plan"})
        self.svc.donna_check()
        req = self.svc.donna_requests()["requests"][0]
        self.assertIn("share_preview", req)
        self.assertEqual(list(self.outbox.glob("*.json")), [])
        self.svc.donna_decide(req["id"], "approved")
        reply = donna.open_envelope(self.key, donna.TO_DONNA, json.loads(next(self.outbox.glob("*.json")).read_text()))
        self.assertEqual(reply["summary"]["total_spent"], 300)
        self.assertNotIn("transactions", json.dumps(reply))


class UiSafetyTests(unittest.TestCase):
    def test_no_html_injection_sinks(self):
        code = (ROOT / "andy" / "ui" / "app.js").read_text()
        code = re.sub(r"//.*", "", code)
        for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            self.assertNotIn(sink, code)

    def test_page_has_strict_csp(self):
        from andy.app import build_page
        page = build_page("NONCE123")
        self.assertIn("script-src 'nonce-NONCE123'", page)
        self.assertIn("connect-src 'none'", page)
        self.assertIn("default-src 'none'", page)
        self.assertEqual(page.count('<script nonce="NONCE123">'), 1)


if __name__ == "__main__":
    unittest.main()
