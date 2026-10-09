"""Everything Andy does, independent of the window. The UI calls these through app.Api."""

from __future__ import annotations

import re
import sys
import threading
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from . import analytics, donna, gmail, insights, paths
from .categorize import CATEGORIES, categorize, merchant_key
from .parser import parse_alert
from .vault import Vault, VaultError, WrongSecret, normalize_recovery_code

_TOOLS = Path(__file__).resolve().parent.parent / "tools"

# What the first-run interview asks, and what My Info shows. (kind, limit or choices)
PROFILE_FIELDS: dict[str, tuple] = {
    "name": ("text", 60), "age": ("int", (16, 100)), "city": ("text", 60), "metro": ("bool", None),
    "employment": ("choice", ("salaried", "freelancer", "business", "mixed")), "dependents": ("int", (0, 15)),
    "monthly_take_home": ("money", None), "annual_gross_salary": ("money", None), "basic_da": ("money", None),
    "other_income_annual": ("money", None), "monthly_rent": ("money", None), "monthly_emis": ("money", None),
    "monthly_investments": ("money", None), "insurance_premiums_annual": ("money", None),
    "emergency_fund": ("money", None), "total_investments": ("money", None), "monthly_budget": ("money", None),
    "tax_regime": ("choice", ("new", "old")), "itr_filed_fy_2025_26": ("bool", None),
    "itr_form": ("choice", ("", "ITR-1", "ITR-2", "ITR-3", "ITR-4")), "itr_filed_on": ("date", None),
    "itr_outcome": ("choice", ("", "refund received", "refund pending", "tax paid", "nil", "not sure")),
    "goals": ("text", 500),
}
SPENDING_CATEGORIES = [c for c in CATEGORIES if c not in ("Investments", "Transfers")]


class ServiceError(Exception):
    """A problem to show Shrey as-is."""


def _money(value) -> float:
    try:
        number = float(str(value).replace(",", "").replace("₹", "").strip() or 0)
    except ValueError:
        raise ServiceError("Amounts must be numbers.") from None
    if not 0 <= number <= 1e10:
        raise ServiceError("Amounts must be between 0 and ₹1,000 crore.")
    return round(number, 2)


def _clean_text(value, limit: int) -> str:
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(value or "")).strip()[:limit]


def clean_profile(raw: dict) -> dict:
    out = {}
    for key, (kind, rule) in PROFILE_FIELDS.items():
        if key not in raw:
            continue
        value = raw[key]
        if kind == "text":
            out[key] = _clean_text(value, rule)
        elif kind == "int":
            if value in ("", None):
                continue
            try:
                number = int(value)
            except (TypeError, ValueError):
                raise ServiceError(f"{key.replace('_', ' ').capitalize()} must be a whole number.") from None
            if not rule[0] <= number <= rule[1]:
                raise ServiceError(f"{key.replace('_', ' ').capitalize()} must be between {rule[0]} and {rule[1]}.")
            out[key] = number
        elif kind == "bool":
            out[key] = bool(value)
        elif kind == "choice":
            if value not in rule:
                raise ServiceError(f"Pick a valid option for {key.replace('_', ' ')}.")
            out[key] = value
        elif kind == "money":
            out[key] = _money(value)
        elif kind == "date":
            if value:
                try:
                    out[key] = date.fromisoformat(str(value)).isoformat()
                except ValueError:
                    raise ServiceError("Dates must look like 2026-07-28.") from None
            else:
                out[key] = ""
    return out


class AndyService:
    def __init__(self, vault: Vault | None = None):
        self.vault = vault or Vault(paths.vault_path())
        self._lock = threading.RLock()
        self._last_activity = time.monotonic()
        self._pending_recovery: str | None = None

    # ------------------------------------------------------------------ state
    def touch(self) -> None:
        self._last_activity = time.monotonic()

    def idle_seconds(self) -> float:
        return time.monotonic() - self._last_activity

    def _data(self) -> dict:
        if not self.vault.unlocked:
            raise ServiceError("Andy is locked.")
        return self.vault.data

    def status(self) -> dict:
        unlocked = self.vault.unlocked
        data = self.vault.data if unlocked else {}
        return {
            "exists": self.vault.exists(), "unlocked": unlocked, "onboarded": bool(data.get("onboarded")),
            "recovery_confirmed": bool(data.get("recovery_confirmed")), "dev_mode": paths.dev_mode(),
            "name": data.get("profile", {}).get("name", ""),
            "auto_lock_minutes": data.get("settings", {}).get("auto_lock_minutes", 5),
        }

    # ------------------------------------------------------------- vault ops
    def create(self, passphrase: str, confirm: str) -> dict:
        if passphrase != confirm:
            raise ServiceError("The two passphrases don't match.")
        with self._lock:
            try:
                code = self.vault.create(passphrase)
            except VaultError as exc:
                raise ServiceError(str(exc)) from None
            self._pending_recovery = code
            self.vault.audit("vault created", "")
            self.vault.save()
            self.touch()
            return {"recovery_code": code}

    def confirm_recovery(self, last_group: str) -> dict:
        with self._lock:
            data = self._data()
            if not self._pending_recovery:
                raise ServiceError("There is no recovery code waiting to be confirmed.")
            if normalize_recovery_code(last_group) != normalize_recovery_code(self._pending_recovery)[-5:]:
                raise ServiceError("That doesn't match the last group of your recovery code.")
            self._pending_recovery = None
            data["recovery_confirmed"] = True
            self.vault.save()
            return {"ok": True}

    def unlock(self, passphrase: str) -> dict:
        with self._lock:
            try:
                self.vault.unlock(passphrase)
            except WrongSecret as exc:
                raise ServiceError(str(exc)) from None
            except VaultError as exc:
                raise ServiceError(str(exc)) from None
            except Exception as exc:  # device binding problems
                raise ServiceError(str(exc)) from None
            self.touch()
            return self.status()

    def recover(self, code: str, new_passphrase: str, confirm: str) -> dict:
        if new_passphrase != confirm:
            raise ServiceError("The two passphrases don't match.")
        with self._lock:
            try:
                self.vault.recover(code, new_passphrase)
            except VaultError as exc:
                raise ServiceError(str(exc)) from None
            self.touch()
            return self.status()

    def lock(self) -> dict:
        with self._lock:
            self._pending_recovery = None
            self.vault.lock()
            return self.status()

    def _step_up(self, passphrase: str | None, action: str) -> None:
        if not passphrase or not self.vault.verify_passphrase(passphrase):
            raise ServiceError(f"Enter your passphrase to {action}.")

    # --------------------------------------------------------------- profile
    def get_profile(self) -> dict:
        data = self._data()
        g = data["gmail"]
        return {
            "profile": data.get("profile", {}), "budgets": data.get("budgets", {}), "settings": data["settings"],
            "gmail": {"address": g.get("address", ""), "connected": bool(g.get("app_password")), "last_sync": g.get("last_sync")},
            "donna": {"paired": bool(data["donna"].get("key")), "paired_at": data["donna"].get("paired_at")},
            "categories": SPENDING_CATEGORIES, "fields": list(PROFILE_FIELDS),
        }

    def save_profile(self, raw: dict) -> dict:
        with self._lock:
            data = self._data()
            if not isinstance(raw, dict):
                raise ServiceError("Nothing to save.")
            cleaned = clean_profile(raw)
            data["profile"].update(cleaned)
            self.vault.audit("profile updated", ", ".join(sorted(cleaned))[:200])
            self.vault.save()
            return self.get_profile()

    def suggested_budgets(self) -> dict:
        """A 50/30/20-style starting point from take-home pay, rounded to ₹500."""
        take_home = float(self._data()["profile"].get("monthly_take_home") or 0)
        if not take_home:
            return {}
        shares = {"Groceries": 0.08, "Food delivery": 0.04, "Dining out": 0.04, "Shopping": 0.06, "Transport": 0.04,
                  "Bills & utilities": 0.05, "Subscriptions": 0.015, "Entertainment": 0.025, "Health": 0.02,
                  "Personal care": 0.015}
        return {k: max(500, round(take_home * v / 500) * 500) for k, v in shares.items()}

    def save_budgets(self, budgets: dict) -> dict:
        if not isinstance(budgets, dict):
            raise ServiceError("Nothing to save.")
        with self._lock:
            data = self._data()
            cleaned = {}
            for category, value in (budgets or {}).items():
                if category not in SPENDING_CATEGORIES:
                    raise ServiceError(f"Unknown category: {category}.")
                amount = _money(value)
                if amount:
                    cleaned[category] = amount
            data["budgets"] = cleaned
            self.vault.save()
            return {"budgets": cleaned}

    def finish_onboarding(self) -> dict:
        with self._lock:
            data = self._data()
            data["onboarded"] = True
            self.vault.audit("onboarding finished", "")
            self.vault.save()
            return self.status()

    # -------------------------------------------------------------- expenses
    def overview(self, today: date | None = None) -> dict:
        data = self._data()
        today = today or date.today()
        result = analytics.overview(data, today)
        result["insights"] = insights.suggestions(data, today)
        result["donna_pending"] = sum(1 for r in data["donna"]["requests"] if r["status"] == "pending")
        result["gmail"] = {"connected": bool(data["gmail"].get("app_password")), "last_sync": data["gmail"].get("last_sync")}
        return result

    def view(self, mode: str, anchor: str | None = None, today: date | None = None) -> dict:
        today = today or date.today()
        try:
            when = date.fromisoformat(anchor) if anchor else today
        except ValueError:
            raise ServiceError("Pick a valid date.") from None
        try:
            return analytics.view(self._data(), mode, when, today)
        except ValueError as exc:
            raise ServiceError(str(exc)) from None

    def insights(self, today: date | None = None) -> dict:
        return insights.suggestions(self._data(), today or date.today())

    def add_transaction(self, fields: dict) -> dict:
        if not isinstance(fields, dict):
            raise ServiceError("Nothing to add.")
        with self._lock:
            data = self._data()
            amount = _money(fields.get("amount"))
            if amount <= 0:
                raise ServiceError("Enter an amount above zero.")
            try:
                when = date.fromisoformat(str(fields.get("date") or date.today().isoformat()))
            except ValueError:
                raise ServiceError("Pick a valid date.") from None
            merchant = _clean_text(fields.get("merchant"), 60) or "Cash purchase"
            category = fields.get("category") or categorize(merchant, "", data["rules"])
            if category not in CATEGORIES:
                raise ServiceError("Pick a category from the list.")
            tx = {"id": uuid.uuid4().hex[:12], "date": when.isoformat(), "time": _clean_text(fields.get("time"), 5) or None,
                  "amount": amount, "direction": "debit", "kind": "expense", "merchant": merchant, "category": category,
                  "mode": _clean_text(fields.get("mode"), 20) or "Cash", "account": "", "source": "manual",
                  "context": "", "fingerprint": "", "note": _clean_text(fields.get("note"), 200), "excluded": False}
            data["transactions"].append(tx)
            self.vault.save()
            return tx

    def update_transaction(self, tx_id: str, changes: dict) -> dict:
        if not isinstance(changes, dict):
            raise ServiceError("Nothing to change.")
        with self._lock:
            data = self._data()
            tx = next((t for t in data["transactions"] if t["id"] == tx_id), None)
            if tx is None:
                raise ServiceError("That transaction no longer exists.")
            if "category" in changes:
                if changes["category"] not in CATEGORIES:
                    raise ServiceError("Pick a category from the list.")
                tx["category"] = changes["category"]
                if changes.get("remember"):
                    key = merchant_key(tx["merchant"])
                    data["rules"][key] = tx["category"]
                    for other in data["transactions"]:
                        if merchant_key(other["merchant"]) == key:
                            other["category"] = tx["category"]
            if "note" in changes:
                tx["note"] = _clean_text(changes["note"], 200)
            if "excluded" in changes:
                tx["excluded"] = bool(changes["excluded"])
            self.vault.save()
            return tx

    def delete_transaction(self, tx_id: str) -> dict:
        with self._lock:
            data = self._data()
            before = len(data["transactions"])
            data["transactions"] = [t for t in data["transactions"] if t["id"] != tx_id]
            if len(data["transactions"]) == before:
                raise ServiceError("That transaction no longer exists.")
            self.vault.save()
            return {"ok": True}

    # ----------------------------------------------------------------- gmail
    def gmail_connect(self, address: str, app_password: str, tester=gmail.test_login) -> dict:
        address, app_password = _clean_text(address, 120), re.sub(r"\s+", "", str(app_password or ""))
        if not re.fullmatch(r"[a-z]{16}", app_password.lower()):
            raise ServiceError("A Google app password is 16 letters. Create one at myaccount.google.com/apppasswords.")
        try:
            tester(address, app_password)
        except gmail.GmailError as exc:
            raise ServiceError(str(exc)) from None
        with self._lock:
            data = self._data()
            data["gmail"].update({"address": address, "app_password": app_password})
            self.vault.audit("gmail connected", address)
            self.vault.save()
            return self.get_profile()["gmail"]

    def gmail_disconnect(self) -> dict:
        with self._lock:
            data = self._data()
            data["gmail"].update({"app_password": ""})
            self.vault.audit("gmail disconnected", "")
            self.vault.save()
            return self.get_profile()["gmail"]

    def gmail_sync(self, fetcher=gmail.fetch_alerts, today: date | None = None) -> dict:
        today = today or date.today()
        with self._lock:
            data = self._data()
            g = data["gmail"]
            if not g.get("app_password"):
                raise ServiceError("Connect Gmail first, in My Info.")
            since = date.fromisoformat(g["last_sync"]) - timedelta(days=2) if g.get("last_sync") else today - timedelta(days=90)
            seen = set(g.get("seen", []))
            address, password = g["address"], g["app_password"]
            trusted = gmail.TRUSTED_DOMAINS + tuple(data["settings"].get("extra_bank_domains", []))
        try:
            alerts, counts = fetcher(address, password, since, seen, trusted)
        except gmail.GmailError as exc:
            raise ServiceError(str(exc)) from None
        with self._lock:
            data = self._data()
            added = self._ingest(data, alerts)
            data["gmail"]["seen"] = (data["gmail"].get("seen", []) + [a.uid_hash for a in alerts])[-5000:]
            data["gmail"]["last_sync"] = today.isoformat()
            counts.update(added=added, not_transactions=len(alerts) - added - counts.get("duplicates", 0))
            self.vault.audit("gmail sync", f"{added} new transaction(s) from {counts['new']} alert email(s)")
            self.vault.save()
            return counts

    def _ingest(self, data: dict, alerts: list) -> int:
        existing = {t["fingerprint"] for t in data["transactions"] if t.get("fingerprint")}
        loose = {(t["date"], t["amount"], t["direction"], merchant_key(t["merchant"])) for t in data["transactions"]}
        added = 0
        for alert in alerts:
            parsed = parse_alert(alert.subject, alert.body, alert.received)
            if parsed is None:
                continue
            key = (parsed.date, parsed.amount, parsed.direction, merchant_key(parsed.merchant))
            if parsed.fingerprint in existing or key in loose:
                continue
            existing.add(parsed.fingerprint)
            loose.add(key)
            tx = parsed.to_dict()
            tx.update(id=uuid.uuid4().hex[:12], category=categorize(parsed.merchant, parsed.context, data["rules"]),
                      source=f"gmail:{alert.sender_domain}", note="", excluded=False)
            data["transactions"].append(tx)
            added += 1
        return added

    # ----------------------------------------------------------------- donna
    def donna_pair(self, passphrase: str) -> dict:
        with self._lock:
            self._step_up(passphrase, "pair with Donna")
            data = self._data()
            key = donna.new_pairing_key()
            data["donna"].update(key=donna.pairing_string(key), paired_at=datetime.now().isoformat(timespec="seconds"), seen={})
            self.vault.audit("donna paired", "New pairing key issued; any previous key stops working")
            self.vault.save()
            inbox, outbox = paths.donna_dirs()
            return {"pairing_key": data["donna"]["key"], "inbox": str(inbox), "outbox": str(outbox)}

    def donna_unpair(self, passphrase: str) -> dict:
        with self._lock:
            self._step_up(passphrase, "disconnect Donna")
            data = self._data()
            data["donna"].update(key="", paired_at=None, seen={})
            self.vault.audit("donna unpaired", "")
            self.vault.save()
            return {"paired": False}

    def donna_check(self) -> dict:
        with self._lock:
            data = self._data()
            if not data["donna"].get("key"):
                return {"new": 0, "rejected": []}
            inbox, _ = paths.donna_dirs()
            accepted, rejected = donna.read_inbox(inbox, donna.parse_pairing_string(data["donna"]["key"]),
                                                  data["donna"].setdefault("seen", {}))
            data["donna"]["requests"].extend(accepted)
            data["donna"]["requests"] = data["donna"]["requests"][-300:]
            if accepted or rejected:
                self.vault.audit("donna inbox", f"{len(accepted)} accepted, {len(rejected)} rejected")
                self.vault.save()
            return {"new": len(accepted), "rejected": rejected}

    def donna_requests(self) -> dict:
        data = self._data()
        threshold = float(data["settings"].get("approval_passphrase_above", 5000))
        items = []
        for r in reversed(data["donna"]["requests"]):
            item = dict(r)
            if r["type"] == "expense_request":
                item["needs_passphrase"] = r["amount"] > threshold
            elif r["status"] == "pending":
                item["share_preview"] = self._summary(r["period"])
            items.append(item)
        return {"paired": bool(data["donna"].get("key")), "requests": items, "threshold": threshold}

    def _summary(self, period: str, today: date | None = None) -> dict:
        today = today or date.today()
        if period == "this_month":
            start, end = analytics.month_bounds(today.year, today.month)
        elif period == "last_month":
            y, m = analytics.shift_month(today.year, today.month, -1)
            start, end = analytics.month_bounds(y, m)
        else:
            start, end = date(today.year, 1, 1), date(today.year, 12, 31)
        txns = self._data()["transactions"]
        return {"period": period, "from": start.isoformat(), "to": min(end, today).isoformat(),
                "total_spent": analytics.total(txns, start, end),
                "by_category": [{"category": c["category"], "total": c["total"]} for c in analytics.by_category(txns, start, end)]}

    def donna_decide(self, request_id: str, decision: str, note: str = "", passphrase: str | None = None) -> dict:
        if decision not in ("approved", "rejected"):
            raise ServiceError("Choose approve or reject.")
        with self._lock:
            data = self._data()
            req = next((r for r in data["donna"]["requests"] if r["id"] == request_id), None)
            if req is None or req["status"] != "pending":
                raise ServiceError("That request is no longer waiting for a decision.")
            threshold = float(data["settings"].get("approval_passphrase_above", 5000))
            if decision == "approved" and req["type"] == "expense_request" and req["amount"] > threshold:
                self._step_up(passphrase, "approve an expense this large")
            reply = {"type": "decision", "ref": request_id, "decision": decision, "note": _clean_text(note, 200)}
            if decision == "approved" and req["type"] == "summary_request":
                reply["summary"] = self._summary(req["period"])
            if data["donna"].get("key"):
                _, outbox = paths.donna_dirs()
                donna.write_message(outbox, donna.parse_pairing_string(data["donna"]["key"]), donna.TO_DONNA, reply)
            req.update(status=decision, decided_at=datetime.now().isoformat(timespec="seconds"), note=reply["note"])
            what = f"₹{req['amount']:,.0f} to {req['payee']}" if req["type"] == "expense_request" else f"summary ({req['period']})"
            self.vault.audit(f"donna request {decision}", what)
            self.vault.save()
            return req

    # ------------------------------------------------------------------- tax
    def tax_overview(self) -> dict:
        profile = self._data()["profile"]
        out = {"itr": {k: profile.get(k) for k in ("itr_filed_fy_2025_26", "itr_form", "itr_filed_on", "itr_outcome")},
               "regime": profile.get("tax_regime", "new"), "comparison": None}
        salary = float(profile.get("annual_gross_salary") or 0)
        if salary:
            if str(_TOOLS) not in sys.path:
                sys.path.insert(0, str(_TOOLS))
            from income_tax import TaxInput, compare  # noqa: PLC0415 - the shared tax engine in tools/

            inp = TaxInput(fy="2026-27", age=int(profile.get("age") or 30), salary=salary,
                           basic_da=float(profile.get("basic_da") or 0), rent_paid=float(profile.get("monthly_rent") or 0) * 12,
                           metro=bool(profile.get("metro")), other_income=float(profile.get("other_income_annual") or 0))
            result = compare(inp)
            out["comparison"] = {
                "old": result["old"]["total_tax"], "new": result["new"]["total_tax"],
                "recommended": result["recommended"], "saving": result["saving"],
                "breakeven": result.get("old_needs_extra_deductions"),
                "note": "HRA is not counted because HRA received isn't in My Info; old-regime deductions are taken as nil.",
            }
        return out

    # -------------------------------------------------------------- security
    def save_settings(self, settings: dict) -> dict:
        if not isinstance(settings, dict):
            raise ServiceError("Nothing to save.")
        with self._lock:
            data = self._data()
            minutes = int(settings.get("auto_lock_minutes", data["settings"]["auto_lock_minutes"]))
            if not 1 <= minutes <= 60:
                raise ServiceError("Auto-lock must be between 1 and 60 minutes.")
            threshold = _money(settings.get("approval_passphrase_above", data["settings"]["approval_passphrase_above"]))
            domains = settings.get("extra_bank_domains", data["settings"].get("extra_bank_domains", []))
            if isinstance(domains, str):
                domains = [d.strip().lower() for d in domains.split(",") if d.strip()]
            for d in domains:
                if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", d):
                    raise ServiceError(f"'{d}' is not a valid email domain.")
            data["settings"].update(auto_lock_minutes=minutes, approval_passphrase_above=threshold,
                                    extra_bank_domains=domains[:20])
            self.vault.audit("settings changed", f"auto-lock {minutes} min, passphrase above ₹{threshold:,.0f}")
            self.vault.save()
            return data["settings"]

    def change_passphrase(self, old: str, new: str, confirm: str) -> dict:
        if new != confirm:
            raise ServiceError("The two new passphrases don't match.")
        try:
            self.vault.change_passphrase(old, new)
        except VaultError as exc:
            raise ServiceError(str(exc)) from None
        return {"ok": True}

    def audit_log(self) -> dict:
        return {"events": list(reversed(self._data().get("audit", [])))[:200]}
