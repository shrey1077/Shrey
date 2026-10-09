"""Spending totals by day, month, year, category and merchant."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta

from .categorize import NOT_SPENDING


def spend_value(t: dict) -> float:
    """What a transaction adds to spending: purchases count, refunds subtract, transfers don't count."""
    if t.get("excluded") or t.get("category") in NOT_SPENDING:
        return 0.0
    if t.get("kind") == "expense":
        return float(t["amount"])
    if t.get("kind") == "refund":
        return -float(t["amount"])
    return 0.0


def _d(value: str) -> date:
    return date.fromisoformat(value)


def in_range(txns: list[dict], start: date, end: date) -> list[dict]:
    lo, hi = start.isoformat(), end.isoformat()
    return [t for t in txns if lo <= t["date"] <= hi]


def total(txns: list[dict], start: date, end: date) -> float:
    return round(sum(spend_value(t) for t in in_range(txns, start, end)), 2)


def daily(txns: list[dict], start: date, end: date) -> list[dict]:
    sums: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for t in in_range(txns, start, end):
        v = spend_value(t)
        if v:
            sums[t["date"]] += v
            counts[t["date"]] += 1
    out, day = [], start
    while day <= end:
        key = day.isoformat()
        out.append({"date": key, "total": round(sums[key], 2), "count": counts[key]})
        day += timedelta(days=1)
    return out


def by_category(txns: list[dict], start: date, end: date) -> list[dict]:
    sums: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for t in in_range(txns, start, end):
        v = spend_value(t)
        if v:
            sums[t["category"]] += v
            counts[t["category"]] += 1
    rows = [{"category": c, "total": round(v, 2), "count": counts[c]} for c, v in sums.items() if round(v, 2)]
    return sorted(rows, key=lambda r: -r["total"])


def top_merchants(txns: list[dict], start: date, end: date, n: int = 6) -> list[dict]:
    sums: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for t in in_range(txns, start, end):
        v = spend_value(t)
        if v > 0:
            sums[t["merchant"]] += v
            counts[t["merchant"]] += 1
    rows = [{"merchant": m, "total": round(v, 2), "count": counts[m]} for m, v in sums.items()]
    return sorted(rows, key=lambda r: -r["total"])[:n]


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def monthly(txns: list[dict], year: int) -> list[dict]:
    out = []
    for m in range(1, 13):
        start, end = month_bounds(year, m)
        out.append({"month": f"{year}-{m:02d}", "total": total(txns, start, end)})
    return out


def income(txns: list[dict], start: date, end: date) -> float:
    return round(sum(float(t["amount"]) for t in in_range(txns, start, end)
                     if t.get("kind") == "income" and t.get("category") not in NOT_SPENDING and not t.get("excluded")), 2)


# The monthly spending budget covers everyday spending, not these commitments.
OUTSIDE_BUDGET = {"Rent", "EMI & loans", "Insurance"}

# Paid once a month or so: forecast them at their usual monthly level, not at a daily pace.
FIXED_CATEGORIES = {"Rent", "EMI & loans", "Insurance", "Bills & utilities", "Subscriptions", "Cash withdrawal"}


def project_month(txns: list[dict], today: date) -> dict[str, float]:
    """Expected month-end spending per category for the month containing `today`."""
    start, end = month_bounds(today.year, today.month)
    remaining = (end - today).days
    so_far = {c["category"]: c["total"] for c in by_category(txns, start, today)}
    usual: dict[str, list[float]] = defaultdict(list)
    for back in (1, 2, 3):
        y, m = shift_month(today.year, today.month, -back)
        for row in by_category(txns, *month_bounds(y, m)):
            usual[row["category"]].append(row["total"])
    rate = _daily_rates(txns, today)
    out = {}
    for category in set(so_far) | set(usual) | set(rate):
        done = so_far.get(category, 0.0)
        if category in FIXED_CATEGORIES:
            history = usual.get(category, [])
            out[category] = round(max(done, sum(history) / len(history) if history else 0.0), 2)
        else:
            out[category] = round(done + max(0.0, rate.get(category, 0.0)) * remaining, 2)
    return out


def _daily_rates(txns: list[dict], today: date, days: int = 60) -> dict[str, float]:
    """Everyday spending per day by category, ignoring one-off big purchases (over 3x the usual amount)."""
    amounts: dict[str, list[float]] = defaultdict(list)
    for t in in_range(txns, today - timedelta(days=days - 1), today):
        v = spend_value(t)
        if v > 0:
            amounts[t["category"]].append(v)
    rates = {}
    for category, values in amounts.items():
        typical = sorted(values)[len(values) // 2]
        rates[category] = sum(v for v in values if v <= 3 * typical) / days
    return rates


def budget_rows(budgets: dict, cats: list[dict], projected: dict[str, float]) -> list[dict]:
    spent = {c["category"]: c["total"] for c in cats}
    rows = []
    for category, limit in budgets.items():
        limit = float(limit or 0)
        if limit <= 0:
            continue
        used = spent.get(category, 0.0)
        pace = max(used, projected.get(category, used))
        status = "over" if used > limit else "at-risk" if pace > limit * 1.05 else "ok"
        rows.append({"category": category, "limit": limit, "spent": round(used, 2), "projected": round(pace, 2),
                     "status": status})
    return sorted(rows, key=lambda r: -(r["spent"] / r["limit"]))


def overview(data: dict, today: date) -> dict:
    txns = data.get("transactions", [])
    start, end = month_bounds(today.year, today.month)
    spent = total(txns, start, today)
    cats = by_category(txns, start, today)
    py, pm = shift_month(today.year, today.month, -1)
    prev_start, prev_end = month_bounds(py, pm)
    prev_same_point = total(txns, prev_start, min(prev_end, prev_start + timedelta(days=today.day - 1)))
    budgets = data.get("budgets", {})
    monthly_budget = float(data.get("profile", {}).get("monthly_budget") or sum(float(v or 0) for v in budgets.values()) or 0)
    projections = project_month(txns, today)
    projected = max(spent, sum(projections.values()))
    budget_spent = round(sum(c["total"] for c in cats if c["category"] not in OUTSIDE_BUDGET), 2)
    take_home = float(data.get("profile", {}).get("monthly_take_home") or 0)
    recent = sorted(txns, key=lambda t: (t["date"], t.get("time") or ""), reverse=True)[:8]
    return {
        "today": today.isoformat(),
        "spent_today": total(txns, today, today),
        "spent_week": total(txns, today - timedelta(days=6), today),
        "spent_month": spent,
        "prev_month_same_point": prev_same_point,
        "projected_month": round(projected, 2),
        "monthly_budget": monthly_budget,
        "budget_spent": budget_spent,
        "budget_used": round(budget_spent / monthly_budget, 4) if monthly_budget else None,
        "take_home": take_home,
        "projected_savings": round(take_home - projected, 2) if take_home else None,
        "last_30_days": daily(txns, today - timedelta(days=29), today),
        "categories": cats,
        "budgets": budget_rows(budgets, cats, projections),
        "recent": recent,
        "transaction_count": len(txns),
    }


def view(data: dict, mode: str, anchor: date, today: date) -> dict:
    txns = data.get("transactions", [])
    if mode == "day":
        start = anchor - timedelta(days=29)
        day_txns = sorted(in_range(txns, anchor, anchor), key=lambda t: t.get("time") or "")
        return {
            "mode": "day", "anchor": anchor.isoformat(), "total": total(txns, anchor, anchor),
            "series": daily(txns, start, anchor), "categories": by_category(txns, anchor, anchor),
            "transactions": day_txns,
        }
    if mode == "month":
        start, end = month_bounds(anchor.year, anchor.month)
        py, pm = shift_month(anchor.year, anchor.month, -1)
        ps, pe = month_bounds(py, pm)
        month_txns = sorted(in_range(txns, start, end), key=lambda t: (t["date"], t.get("time") or ""), reverse=True)
        current = start <= today <= end
        # For the month in progress, compare with the same days of last month.
        prev_end = min(pe, ps + timedelta(days=today.day - 1)) if current else pe
        return {
            "mode": "month", "anchor": anchor.isoformat(), "label": anchor.strftime("%B %Y"), "in_progress": current,
            "total": total(txns, start, end), "previous_total": total(txns, ps, prev_end), "income": income(txns, start, end),
            "series": daily(txns, start, end), "categories": by_category(txns, start, end),
            "merchants": top_merchants(txns, start, end), "transactions": month_txns,
            "budgets": budget_rows(data.get("budgets", {}), by_category(txns, start, end),
                                   project_month(txns, today) if start <= today <= end else {}),
        }
    if mode == "year":
        start, end = date(anchor.year, 1, 1), date(anchor.year, 12, 31)
        return {
            "mode": "year", "anchor": anchor.isoformat(), "label": str(anchor.year),
            "total": total(txns, start, end), "previous_total": total(txns, date(anchor.year - 1, 1, 1), date(anchor.year - 1, 12, 31)),
            "income": income(txns, start, end), "series": monthly(txns, anchor.year),
            "categories": by_category(txns, start, end), "merchants": top_merchants(txns, start, end, 8),
        }
    raise ValueError("mode must be day, month or year")
