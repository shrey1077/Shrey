"""Ways to cut spending, worked out from Shrey's own transactions.

Each suggestion carries an estimated monthly saving in rupees and the assumption behind it, so it
can be checked rather than taken on trust.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, timedelta

from . import analytics
from .categorize import merchant_key
from .money import inr as _inr

_STREAMING = ("netflix", "prime", "hotstar", "disney", "sonyliv", "zee5", "youtube")


def _expenses(txns: list[dict], start: date, end: date) -> list[dict]:
    return [t for t in analytics.in_range(txns, start, end) if analytics.spend_value(t) > 0]


def _s(title: str, detail: str, monthly: float, category: str, kind: str, basis: str, one_time: bool = False) -> dict:
    monthly = max(0.0, round(monthly / 10) * 10)
    return {"title": title, "detail": detail, "monthly_saving": monthly, "yearly_saving": monthly if one_time else monthly * 12,
            "category": category, "kind": kind, "basis": basis, "one_time": one_time}


def recurring(txns: list[dict], today: date) -> list[dict]:
    """Merchants charged in at least two different months at a steady amount: likely subscriptions."""
    by_merchant: dict[str, list[dict]] = defaultdict(list)
    for t in _expenses(txns, today - timedelta(days=125), today):
        by_merchant[merchant_key(t["merchant"])].append(t)
    out = []
    for key, items in by_merchant.items():
        months = {t["date"][:7] for t in items}
        amounts = [float(t["amount"]) for t in items]
        typical = statistics.median(amounts)
        steady = all(abs(a - typical) <= 0.15 * typical for a in amounts)
        days = [int(t["date"][8:]) for t in items]
        same_day = max(days) - min(days) <= 6
        is_sub = any(t["category"] == "Subscriptions" for t in items)
        once_a_month = len(items) <= len(months) + 1
        if steady and once_a_month and same_day and len(months) >= (2 if is_sub else 3):
            out.append({"merchant": items[-1]["merchant"], "monthly": round(typical, 2), "months_seen": len(months),
                        "category": items[-1]["category"], "last": max(t["date"] for t in items)})
    return sorted(out, key=lambda r: -r["monthly"])


def suggestions(data: dict, today: date) -> dict:
    txns = data.get("transactions", [])
    profile = data.get("profile", {})
    out: list[dict] = []
    q_start = today - timedelta(days=89)
    quarter = _expenses(txns, q_start, today)
    if not quarter:
        return {"items": [], "total_monthly": 0, "subscriptions": []}
    months_of_data = max(1.0, min(3.0, (today - min(date.fromisoformat(t["date"]) for t in quarter)).days / 30))
    quarter_total = sum(analytics.spend_value(t) for t in quarter)

    # Subscriptions
    # Bills, rent and EMIs recur too, but they aren't optional, so only these are worth cancelling.
    subs = [r for r in recurring(txns, today) if r["category"] in ("Subscriptions", "Entertainment", "Other", "Personal care", "Health")]
    if subs:
        total_subs = sum(r["monthly"] for r in subs)
        cheapest = min(r["monthly"] for r in subs)
        names = ", ".join(r["merchant"] for r in subs[:5])
        out.append(_s(
            f"{len(subs)} recurring charges cost {_inr(total_subs)} a month",
            f"{names}{'…' if len(subs) > 5 else ''}. Cancel any you haven't used in the last 30 days, and move the ones "
            "you keep to annual plans, which usually cost 15–20% less.",
            max(cheapest, 0.15 * total_subs), "Subscriptions", "subscriptions",
            "Assumes you drop the cheapest one or save 15% by switching to annual billing, whichever is larger."))
        streaming = [r for r in subs if any(s in r["merchant"].lower() for s in _STREAMING)]
        if len(streaming) >= 3:
            keep = max(r["monthly"] for r in streaming)
            out.append(_s(
                f"{len(streaming)} streaming services at once",
                "Rotate them: keep one for a month, finish what you want to watch, then switch.",
                sum(r["monthly"] for r in streaming) - keep, "Subscriptions", "streaming",
                "Assumes you keep only the most expensive service at any one time."))

    # Food delivery and dining
    for category, share_floor, floor in (("Food delivery", 0.08, 2000), ("Dining out", 0.12, 3000)):
        items = [t for t in quarter if t["category"] == category]
        if not items:
            continue
        monthly = sum(analytics.spend_value(t) for t in items) / months_of_data
        share = monthly * months_of_data / quarter_total if quarter_total else 0
        if monthly >= floor and share >= share_floor:
            avg_order = sum(float(t["amount"]) for t in items) / len(items)
            orders = len(items) / months_of_data
            detail = (f"About {orders:.0f} orders a month at {_inr(avg_order)} each, {share:.0%} of your spending. "
                      + ("Delivery, packaging and platform fees add roughly ₹40–80 to every order. Cooking two of "
                         "every three of those meals at home saves the most." if category == "Food delivery" else
                         "Set a monthly dining allowance and move what's left to savings."))
            out.append(_s(f"{category}: {_inr(monthly)} a month", detail, monthly / 3, category, "habit",
                          "Assumes one in three orders is replaced."))

    # Small, frequent payments
    month_ago = _expenses(txns, today - timedelta(days=29), today)
    small = [t for t in month_ago if float(t["amount"]) < 300]
    if len(small) >= 25:
        small_total = sum(float(t["amount"]) for t in small)
        out.append(_s(f"{len(small)} small payments added up to {_inr(small_total)}",
                      "Payments under ₹300 in the last 30 days: snacks, chai, rides, top-ups. A weekly cash-style cap "
                      f"of {_inr(small_total / 4.3 * 0.7)} keeps them in check.",
                      small_total * 0.3, "Several", "small-spends", "Assumes a 30% cut."))

    # Category spikes: this month so far against the same days of earlier months
    month_start, month_end = analytics.month_bounds(today.year, today.month)
    this_month = analytics.by_category(txns, month_start, today)
    earliest = min(t["date"] for t in txns)
    for row in this_month:
        if row["category"] in analytics.FIXED_CATEGORIES or today.day < 5:
            continue
        history = []
        for back in (1, 2, 3):
            y, m = analytics.shift_month(today.year, today.month, -back)
            s, e = analytics.month_bounds(y, m)
            if s.isoformat() < earliest:
                continue
            upto = min(e, s + timedelta(days=today.day - 1))
            history.append(sum(analytics.spend_value(t) for t in analytics.in_range(txns, s, upto) if t["category"] == row["category"]))
        if len(history) < 2:
            continue
        usual = sum(history) / len(history)
        if row["total"] > 1.4 * usual and row["total"] - usual > 1500:
            how_much = f"{row['total'] / usual - 1:.0%} above" if usual >= 500 else "well above"
            out.append(_s(f"{row['category']} is {how_much} your usual by this date",
                          f"{_inr(row['total'])} so far this month, against a usual {_inr(usual)} by day {today.day}. "
                          "Look at the biggest items and hold off on anything that can wait until next month.",
                          row["total"] - usual, row["category"], "spike",
                          "This month's spending so far minus your usual by the same date. A one-off, not counted in the monthly total.",
                          one_time=True))

    # Fees, penalties and interest
    fees = [t for t in quarter if t["category"] == "Fees & charges"]
    if fees:
        fee_total = sum(float(t["amount"]) for t in fees)
        out.append(_s(f"{_inr(fee_total)} lost to fees and charges in 90 days",
                      "Late fees, interest and penalties are fully avoidable: put card bills on auto-pay for the full "
                      "amount, keep the minimum balance, and pay utility bills before the due date.",
                      fee_total / months_of_data, "Fees & charges", "fees", "All of it is avoidable."))

    # Late-night impulse buys
    late = [t for t in _expenses(txns, today - timedelta(days=59), today)
            if t["category"] in ("Shopping", "Food delivery", "Entertainment") and t.get("time")
            and (t["time"] >= "23:00" or t["time"] < "04:00")]
    if len(late) >= 4:
        late_total = sum(float(t["amount"]) for t in late)
        out.append(_s(f"{len(late)} late-night purchases worth {_inr(late_total)}",
                      "Bought between 11 pm and 4 am over the last 60 days. Try a 24-hour rule: add it to the cart and "
                      "decide in the morning.", late_total / 2 * 0.25, "Shopping", "impulse",
                      "Assumes a quarter of late-night buys would be skipped."))

    # Weekends
    recent = _expenses(txns, today - timedelta(days=55), today)
    if recent:
        weekend = sum(analytics.spend_value(t) for t in recent if date.fromisoformat(t["date"]).weekday() >= 5) / 16
        weekday = sum(analytics.spend_value(t) for t in recent if date.fromisoformat(t["date"]).weekday() < 5) / 40
        if weekday > 0 and weekend > 1.6 * weekday and (weekend - weekday) * 8.6 > 2000:
            out.append(_s(f"Weekends cost {weekend / weekday:.1f}× a weekday",
                          f"About {_inr(weekend)} a day on weekends against {_inr(weekday)} on weekdays. Plan one "
                          "low-cost weekend a month.", (weekend - weekday) * 8.6 * 0.2, "Several", "weekends",
                          "Assumes you trim 20% of the weekend premium."))

    # Cash
    cash = sum(analytics.spend_value(t) for t in quarter if t["category"] == "Cash withdrawal")
    if quarter_total and cash / quarter_total > 0.15:
        out.append(_s(f"{cash / quarter_total:.0%} of spending is cash",
                      "Andy can't see what cash buys. Paying by UPI or card makes every rupee show up here.",
                      0, "Cash withdrawal", "visibility", "No direct saving; it makes the rest of the advice sharper."))

    # Budgets
    projections = analytics.project_month(txns, today)
    for row in analytics.budget_rows(data.get("budgets", {}), this_month, projections):
        if row["status"] in ("over", "at-risk"):
            days_left = month_end.day - today.day
            still_to_spend = max(0.0, row["projected"] - row["spent"])
            out.append(_s(f"{row['category']} budget: {_inr(row['spent'])} of {_inr(row['limit'])}",
                          (f"Already over, with {days_left} days left. Pausing {row['category'].lower()} until next month "
                           f"avoids about {_inr(still_to_spend)} more." if row["status"] == "over" else
                           f"On pace to cross it with {days_left} days left. Keeping the rest of the month to "
                           f"{_inr(max(0, row['limit'] - row['spent']))} holds the line."),
                          min(still_to_spend, max(0.0, row["projected"] - row["limit"])), row["category"], "budget",
                          "What this month's pace would add beyond the budget, counting only spending still to come."))

    # Savings rate
    take_home = float(profile.get("monthly_take_home") or 0)
    if take_home:
        projected = max(analytics.total(txns, month_start, today), sum(projections.values()))
        rate = 1 - projected / take_home
        if today.day >= 7 and rate < 0.2:
            out.append(_s(f"On track to save {max(rate, 0):.0%} of your pay this month",
                          "Aim for at least 20%. Pay yourself first: set an auto-SIP or transfer for the day after "
                          "salary lands, and spend what's left.", max(0.0, (0.2 - rate) * take_home),
                          "Savings", "savings-rate", "The gap between this month's pace and a 20% savings rate."))

    out = _dedupe(out)
    out.sort(key=lambda s: -s["monthly_saving"])
    return {"items": out, "total_monthly": round(sum(s["monthly_saving"] for s in out if not s["one_time"]), 2),
            "subscriptions": subs}


def _dedupe(items: list[dict]) -> list[dict]:
    """One budget or spike warning per category, and none where a more specific suggestion exists."""
    specific = {i["category"] for i in items if i["kind"] in ("habit", "subscriptions", "streaming")}
    best: dict[str, dict] = {}
    for item in items:
        if item["kind"] in ("budget", "spike"):
            if item["category"] in specific:
                continue
            current = best.get(item["category"])
            if current is None or item["monthly_saving"] > current["monthly_saving"]:
                best[item["category"]] = item
    return [i for i in items if i["kind"] not in ("budget", "spike")] + list(best.values())
