#!/usr/bin/env python3
"""Advance-tax schedule and interest under sections 234B / 234C (India).

Get the year's total tax from income_tax.py first, then:

  python3 tools/advance_tax.py --tax 320000 --tds 180000
  python3 tools/advance_tax.py --tax 320000 --tds 180000 --paid-jun 0 --paid-sep 50000 \
      --paid-dec 40000 --paid-mar 50000 --filing-date 2027-07-20
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from fmt import inr
from tax_rules import DEFAULT_FY

THRESHOLD = 10_000
# (label, month, day, cumulative share due, share below which 234C applies, months of interest)
INSTALMENTS = [
    ("15 Jun", 6, 15, 0.15, 0.12, 3),
    ("15 Sep", 9, 15, 0.45, 0.36, 3),
    ("15 Dec", 12, 15, 0.75, 0.75, 3),
    ("15 Mar", 3, 15, 1.00, 1.00, 1),
]


def _floor100(x: float) -> float:
    return max(0.0, x // 100 * 100)


def schedule(tax: float, tds: float = 0.0, fy: str = DEFAULT_FY, paid=None, presumptive: bool = False,
             senior_without_business: bool = False, filing_date: date | None = None) -> dict:
    start = int(fy[:4])
    net = max(0.0, tax - tds)
    result = {"fy": fy, "net_tax_after_tds": net, "instalments": [], "interest_234c": 0.0, "interest_234b": 0.0}

    if senior_without_business:
        result["required"] = False
        result["reason"] = "Resident seniors (60+) without business income need not pay advance tax."
        return result
    if net < THRESHOLD:
        result["required"] = False
        result["reason"] = f"Tax after TDS is below {inr(THRESHOLD)}, so no advance tax is due."
        return result
    result["required"] = True

    paid = list(paid or [None] * 4)
    cumulative_paid = 0.0
    previous_due = 0.0
    for (label, month, day, share, tolerance, months), amount in zip(INSTALMENTS, paid):
        due_date = date(start + (1 if month == 3 else 0), month, day)
        if presumptive and month != 3:
            share, tolerance = 0.0, 0.0
        cumulative_due = net * share
        row = {"due_date": due_date.isoformat(), "label": label,
               "cumulative_due": cumulative_due, "pay_now": cumulative_due - previous_due}
        previous_due = cumulative_due
        if amount is not None:
            cumulative_paid += amount
            row["cumulative_paid"] = cumulative_paid
            if share and cumulative_paid < net * tolerance:
                interest = _floor100(cumulative_due - cumulative_paid) * 0.01 * months
                row["interest_234c"] = interest
                result["interest_234c"] += interest
        result["instalments"].append(row)

    if filing_date and any(p is not None for p in paid):
        if cumulative_paid < 0.90 * net:
            months = max(1, (filing_date.year - (start + 1)) * 12 + filing_date.month - 4 + 1)
            result["interest_234b"] = _floor100(net - cumulative_paid) * 0.01 * months
            result["months_234b"] = months
    return result


def render(r: dict) -> str:
    lines = [f"Advance tax - FY {r['fy']}", f"Tax after TDS: {inr(r['net_tax_after_tds'])}"]
    if not r["required"]:
        return "\n".join(lines + [r["reason"]])
    lines.append("")
    for row in r["instalments"]:
        line = f"{row['due_date']}  pay {inr(row['pay_now']):>12}  (cumulative {inr(row['cumulative_due'])})"
        if "cumulative_paid" in row:
            line += f"  paid so far {inr(row['cumulative_paid'])}"
        if row.get("interest_234c"):
            line += f"  234C interest {inr(row['interest_234c'])}"
        lines.append(line)
    if r["interest_234c"] or r["interest_234b"]:
        lines.append("")
        lines.append(f"Interest u/s 234C: {inr(r['interest_234c'])}")
        if r["interest_234b"]:
            lines.append(f"Interest u/s 234B: {inr(r['interest_234b'])} ({r['months_234b']} months)")
    lines += ["", "Pay via the e-Pay Tax service on the income-tax portal (challan ITNS 280, minor head 100)."]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tax", type=float, required=True, help="estimated total tax for the year, incl. cess")
    ap.add_argument("--tds", type=float, default=0.0, help="TDS/TCS expected for the year")
    ap.add_argument("--fy", default=DEFAULT_FY)
    for label in ("jun", "sep", "dec", "mar"):
        ap.add_argument(f"--paid-{label}", type=float, help=f"advance tax paid in the instalment ending 15 {label.title()}")
    ap.add_argument("--presumptive", action="store_true", help="44AD/44ADA: everything is due by 15 Mar")
    ap.add_argument("--senior-without-business", action="store_true")
    ap.add_argument("--filing-date", type=date.fromisoformat, help="return filing date, for 234B")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    paid = [a.paid_jun, a.paid_sep, a.paid_dec, a.paid_mar]
    r = schedule(a.tax, a.tds, a.fy, paid, a.presumptive, a.senior_without_business, a.filing_date)
    print(json.dumps(r, indent=2) if a.json else render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
