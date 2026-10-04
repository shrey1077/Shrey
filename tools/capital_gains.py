#!/usr/bin/env python3
"""Classify a sale as short- or long-term and work out the taxable gain (India).

Uses the regime that applies to transfers on or after 23 July 2024.

Asset types:
  equity       listed shares (STT paid), equity mutual funds, equity ETFs, REIT/InvIT units
  listed_other other listed securities: listed bonds, gold ETFs, SGBs sold on the exchange
  debt_mf      debt mutual funds (and other specified MFs), market-linked debentures, unlisted bonds
  property     land or building
  other        physical gold, unlisted or foreign shares, gold/international fund-of-funds, etc.

Examples:
  python3 tools/capital_gains.py --asset equity --buy-date 2023-05-10 --sell-date 2026-08-01 \
      --buy-price 400000 --sell-price 700000
  python3 tools/capital_gains.py --asset property --buy-date 2015-06-01 --sell-date 2026-09-15 \
      --buy-price 4500000 --sell-price 9500000 --expenses 150000
"""

from __future__ import annotations

import argparse
import calendar
import json
import sys
from datetime import date

from fmt import inr
from tax_rules import COST_INFLATION_INDEX, DEFAULT_FY, rules_for

NEW_REGIME_START = date(2024, 7, 23)
SPECIFIED_MF_CUTOFF = date(2023, 4, 1)
GRANDFATHER_DATE = date(2018, 2, 1)
ASSETS = ["equity", "listed_other", "debt_mf", "property", "other"]


def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def fy_start_year(d: date) -> int:
    return d.year if d.month >= 4 else d.year - 1


def cii(d: date) -> int:
    year = max(2001, fy_start_year(d))
    if year not in COST_INFLATION_INDEX:
        raise ValueError(f"No Cost Inflation Index for FY {year}-{(year + 1) % 100:02d}; add it to tools/tax_rules.py.")
    return COST_INFLATION_INDEX[year]


def analyse(asset: str, buy_date: date, sell_date: date, buy_price: float, sell_price: float,
            expenses: float = 0.0, improvement: float = 0.0, fmv_2001: float | None = None,
            fmv_2018: float | None = None, resident: bool = True) -> dict:
    if asset not in ASSETS:
        raise ValueError(f"asset must be one of {', '.join(ASSETS)}")
    if sell_date < buy_date:
        raise ValueError("sell date is before buy date")
    if sell_date < NEW_REGIME_START:
        raise ValueError("Sales before 23 Jul 2024 used the older rates (15% STCG, 10% LTCG); this tool does not cover them.")

    rules = rules_for(DEFAULT_FY)
    notes: list[str] = []
    effective = asset
    if asset == "debt_mf" and buy_date < SPECIFIED_MF_CUTOFF:
        effective = "other"
        notes.append("Debt fund bought before 1 Apr 2023: taxed as an ordinary capital asset, not under section 50AA.")

    months = {"equity": 12, "listed_other": 12, "property": 24, "other": 24, "debt_mf": None}[effective]
    long_term = months is not None and sell_date > add_months(buy_date, months)

    cost = buy_price
    if fmv_2001 is not None and buy_date < date(2001, 4, 1) and effective in ("property", "other"):
        cost = fmv_2001
        notes.append("Bought before 1 Apr 2001: cost taken as fair market value on 1 Apr 2001.")
    if effective == "equity" and long_term and buy_date < GRANDFATHER_DATE:
        if fmv_2018 is None:
            notes.append("Bought before 1 Feb 2018: pass --fmv-2018 (31 Jan 2018 price x quantity) for grandfathering.")
        else:
            cost = max(buy_price, min(fmv_2018, sell_price))
            notes.append("Grandfathered cost: higher of actual cost and min(31 Jan 2018 FMV, sale value).")

    gain = sell_price - expenses - cost - improvement
    result = {
        "asset": asset,
        "holding_days": (sell_date - buy_date).days,
        "long_term": long_term,
        "gain": gain,
        "notes": notes,
    }

    if effective == "debt_mf":
        result.update(treatment="Always short-term (section 50AA); taxed at your slab rate.",
                      section="50AA", rate=None, income_tax_flag="--stcg-slab")
    elif effective == "equity" and not long_term:
        result.update(treatment="Short-term gain on listed equity, 20%.", section="111A",
                      rate=rules["stcg_111a_rate"], income_tax_flag="--stcg-111a")
    elif effective == "equity":
        result.update(
            treatment=f"Long-term gain on listed equity, 12.5% on total such gains above "
                      f"{inr(rules['ltcg_112a_exemption'])} a year.",
            section="112A", rate=rules["ltcg_112a_rate"], income_tax_flag="--ltcg-112a")
    elif not long_term:
        result.update(treatment="Short-term gain taxed at your slab rate.", section="slab",
                      rate=None, income_tax_flag="--stcg-slab")
    else:
        result.update(treatment="Long-term gain, 12.5% without indexation.", section="112",
                      rate=rules["ltcg_112_rate"], income_tax_flag="--ltcg-112")
        result["tax_without_indexation"] = max(0.0, gain) * rules["ltcg_112_rate"]
        if effective == "property" and resident and buy_date < NEW_REGIME_START:
            indexed_cost = (cost + improvement) * cii(sell_date) / cii(buy_date)
            indexed_gain = sell_price - expenses - indexed_cost
            indexed_tax = max(0.0, indexed_gain) * rules["ltcg_112_indexed_rate"]
            result.update(indexed_cost=indexed_cost, indexed_gain=indexed_gain, tax_with_indexation=indexed_tax)
            if improvement:
                notes.append("Improvement cost was indexed from the purchase year; index it from its own year if it differs.")
            if indexed_tax < result["tax_without_indexation"]:
                result.update(treatment="Long-term gain: 20% with indexation is cheaper than 12.5% without.",
                              rate=rules["ltcg_112_indexed_rate"], income_tax_flag="--ltcg-112-indexed",
                              taxable_gain=max(0.0, indexed_gain))
            else:
                notes.append("12.5% without indexation is cheaper than 20% with indexation.")
            notes.append("A loss worked out with indexation cannot be claimed; only the unindexed computation counts for losses.")
        if effective == "property":
            notes.append("Exemptions to consider: section 54 (buy/build a house), 54EC bonds (up to 50 lakh, within 6 months), "
                         "or the Capital Gains Account Scheme until reinvested.")
        else:
            notes.append("Section 54F may exempt the gain if the full sale proceeds go into one residential house.")

    result.setdefault("taxable_gain", max(0.0, gain))
    if result["rate"] and effective != "equity":
        result["estimated_tax_before_cess"] = result["taxable_gain"] * result["rate"]
    if gain < 0:
        notes.append("This is a capital loss. Short-term losses offset any gains; long-term losses offset only "
                     "long-term gains. Unused losses carry forward 8 years if the return is filed on time.")
    return result


def render(r: dict) -> str:
    years, days = divmod(r["holding_days"], 365)
    lines = [
        f"Held {years}y {days}d -> {'LONG-TERM' if r['long_term'] else 'SHORT-TERM'} ({r['section']})",
        f"Gain: {inr(r['gain'])}",
        f"Treatment: {r['treatment']}",
    ]
    if "tax_with_indexation" in r:
        lines.append(f"  12.5% without indexation: tax {inr(r['tax_without_indexation'])}")
        lines.append(f"  20% with indexation:      tax {inr(r['tax_with_indexation'])} "
                     f"(indexed cost {inr(r['indexed_cost'])}, gain {inr(r['indexed_gain'])})")
    if "estimated_tax_before_cess" in r:
        lines.append(f"Estimated tax before surcharge and cess: {inr(r['estimated_tax_before_cess'])}")
    lines.append(f"For the full-year computation: income_tax.py {r['income_tax_flag']} {round(r['taxable_gain'])}")
    if r["notes"]:
        lines += ["", "Notes:"] + [f"- {n}" for n in r["notes"]]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--asset", required=True, choices=ASSETS)
    ap.add_argument("--buy-date", required=True, type=date.fromisoformat, help="YYYY-MM-DD")
    ap.add_argument("--sell-date", required=True, type=date.fromisoformat, help="YYYY-MM-DD")
    ap.add_argument("--buy-price", required=True, type=float, help="total purchase cost")
    ap.add_argument("--sell-price", required=True, type=float, help="total sale value")
    ap.add_argument("--expenses", type=float, default=0.0, help="brokerage, stamp duty on sale, etc.")
    ap.add_argument("--improvement", type=float, default=0.0, help="cost of improvement")
    ap.add_argument("--fmv-2001", type=float, help="fair market value on 1 Apr 2001 (assets bought earlier)")
    ap.add_argument("--fmv-2018", type=float, help="value on 31 Jan 2018 (equity bought before 1 Feb 2018)")
    ap.add_argument("--non-resident", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = analyse(a.asset, a.buy_date, a.sell_date, a.buy_price, a.sell_price, a.expenses, a.improvement,
                a.fmv_2001, a.fmv_2018, resident=not a.non_resident)
    print(json.dumps(r, indent=2, default=str) if a.json else render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
