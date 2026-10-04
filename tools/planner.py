#!/usr/bin/env python3
"""Financial-planning calculators. Rates are annual percentages; amounts are in rupees.

  python3 tools/planner.py sip --monthly 10000 --return 12 --years 15 --step-up 10
  python3 tools/planner.py lumpsum --amount 500000 --return 10 --years 10
  python3 tools/planner.py goal --target 2500000 --years 8 --inflation 6 --return 11 --existing 200000
  python3 tools/planner.py retirement --age 30 --retire-at 55 --life 85 --monthly-expenses 60000
  python3 tools/planner.py emi --principal 5000000 --rate 8.5 --years 20 --prepay-yearly 100000
  python3 tools/planner.py emergency --monthly-expenses 60000 --emi 25000
  python3 tools/planner.py insurance --annual-expenses 900000 --years 25 --liabilities 4000000 --assets 1500000
  python3 tools/planner.py fd --principal 500000 --rate 7.25 --years 3 --slab 30
  python3 tools/planner.py real-return --nominal 7 --inflation 6 --slab 30
  python3 tools/planner.py cagr --start 100000 --end 250000 --years 6
  python3 tools/planner.py xirr --flows 2023-01-01:-100000 2024-01-01:-100000 2026-09-01:260000
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from fmt import inr, pct


def monthly_rate(annual_pct: float) -> float:
    return (1 + annual_pct / 100) ** (1 / 12) - 1


def sip_future_value(monthly: float, annual_return: float, years: float, step_up: float = 0.0) -> dict:
    """SIP invested at the start of each month; the instalment rises by step_up% every 12 months."""
    i = monthly_rate(annual_return)
    balance = invested = 0.0
    instalment = monthly
    for month in range(round(years * 12)):
        if month and month % 12 == 0:
            instalment *= 1 + step_up / 100
        balance = (balance + instalment) * (1 + i)
        invested += instalment
    return {"future_value": balance, "invested": invested, "gain": balance - invested}


def lumpsum_future_value(amount: float, annual_return: float, years: float) -> float:
    return amount * (1 + annual_return / 100) ** years


def goal_plan(target_today: float, years: float, inflation: float, annual_return: float,
              existing: float = 0.0, step_up: float = 0.0) -> dict:
    future_cost = target_today * (1 + inflation / 100) ** years
    existing_fv = lumpsum_future_value(existing, annual_return, years)
    gap = max(0.0, future_cost - existing_fv)
    per_rupee = sip_future_value(1, annual_return, years, step_up)["future_value"]
    return {
        "future_cost": future_cost,
        "existing_grows_to": existing_fv,
        "gap": gap,
        "monthly_sip": gap / per_rupee if per_rupee else gap,
        "or_lumpsum_today": gap / (1 + annual_return / 100) ** years,
    }


def retirement_plan(age: int, retire_at: int, life: int, monthly_expenses: float, inflation: float = 6.0,
                    pre_return: float = 11.0, post_return: float = 7.0, existing: float = 0.0,
                    step_up: float = 0.0) -> dict:
    years_to_go = retire_at - age
    years_in_retirement = life - retire_at
    if years_to_go <= 0 or years_in_retirement <= 0:
        raise ValueError("need age < retire-at < life")
    first_year_expense = monthly_expenses * 12 * (1 + inflation / 100) ** years_to_go
    r, g = post_return / 100, inflation / 100
    # Withdrawals at the start of each year, rising with inflation.
    if abs(r - g) < 1e-9:
        corpus = first_year_expense * years_in_retirement
    else:
        corpus = first_year_expense * (1 - ((1 + g) / (1 + r)) ** years_in_retirement) / (r - g) * (1 + r)
    existing_fv = lumpsum_future_value(existing, pre_return, years_to_go)
    gap = max(0.0, corpus - existing_fv)
    per_rupee = sip_future_value(1, pre_return, years_to_go, step_up)["future_value"]
    return {
        "years_to_retirement": years_to_go,
        "monthly_expenses_at_retirement": first_year_expense / 12,
        "corpus_needed": corpus,
        "existing_grows_to": existing_fv,
        "gap": gap,
        "monthly_sip": gap / per_rupee,
    }


def emi_plan(principal: float, rate: float, years: float, prepay_yearly: float = 0.0) -> dict:
    i = rate / 12 / 100
    n = round(years * 12)
    emi = principal / n if i == 0 else principal * i * (1 + i) ** n / ((1 + i) ** n - 1)
    result = {"emi": emi, "total_interest": emi * n - principal, "months": n}
    if prepay_yearly:
        balance, interest, month = principal, 0.0, 0
        while balance > 0.01 and month < n:
            month += 1
            charge = balance * i
            interest += charge
            balance -= min(balance, emi - charge)
            if month % 12 == 0:
                balance -= min(balance, prepay_yearly)
        result.update(months_with_prepayment=month, interest_with_prepayment=interest,
                      interest_saved=result["total_interest"] - interest, months_saved=n - month)
    return result


def emergency_fund(monthly_expenses: float, emi: float = 0.0, insurance_premiums_yearly: float = 0.0,
                   months: int = 6) -> dict:
    monthly_need = monthly_expenses + emi + insurance_premiums_yearly / 12
    return {"monthly_outgo": monthly_need, "months": months, "target": monthly_need * months}


def insurance_need(annual_expenses: float, years: int, liabilities: float = 0.0, goals: float = 0.0,
                   assets: float = 0.0, existing_cover: float = 0.0, inflation: float = 6.0,
                   annual_return: float = 7.0, annual_income: float = 0.0) -> dict:
    real = (1 + annual_return / 100) / (1 + inflation / 100) - 1
    pv_expenses = annual_expenses * years if abs(real) < 1e-9 else annual_expenses * (1 - (1 + real) ** -years) / real * (1 + real)
    need = max(0.0, pv_expenses + liabilities + goals - assets - existing_cover)
    out = {"pv_of_family_expenses": pv_expenses, "term_cover_needed": need}
    if annual_income:
        out["rule_of_thumb_10x_15x"] = [annual_income * 10, annual_income * 15]
    return out


def fd_maturity(principal: float, rate: float, years: float, compounding: int = 4, slab: float = 0.0) -> dict:
    maturity = principal * (1 + rate / 100 / compounding) ** (compounding * years)
    effective = (1 + rate / 100 / compounding) ** compounding - 1
    return {
        "maturity": maturity,
        "interest": maturity - principal,
        "effective_annual_yield": effective,
        "post_tax_yield": effective * (1 - slab / 100 * 1.04),
    }


def real_return(nominal: float, inflation: float, slab: float = 0.0) -> dict:
    post_tax = nominal / 100 * (1 - slab / 100 * 1.04)
    return {"post_tax_nominal": post_tax, "real_return": (1 + post_tax) / (1 + inflation / 100) - 1}


def cagr(start: float, end: float, years: float) -> float:
    return (end / start) ** (1 / years) - 1


def xirr(flows: list[tuple[date, float]]) -> float:
    if not (any(a < 0 for _, a in flows) and any(a > 0 for _, a in flows)):
        raise ValueError("XIRR needs at least one outflow (negative) and one inflow (positive)")
    t0 = min(d for d, _ in flows)

    def npv(rate: float) -> float:
        return sum(a / (1 + rate) ** ((d - t0).days / 365) for d, a in flows)

    lo, hi = -0.9999, 10.0
    if npv(lo) * npv(hi) > 0:
        raise ValueError("could not bracket the XIRR")
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


_PERCENT_KEYS = {"effective_annual_yield", "post_tax_yield", "post_tax_nominal", "real_return", "cagr", "xirr"}
_COUNT_KEYS = {"months", "months_with_prepayment", "months_saved", "years_to_retirement"}


def _print(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2))
        return
    for key, value in result.items():
        if isinstance(value, list):
            value = " to ".join(inr(v) for v in value)
        elif key in _PERCENT_KEYS:
            value = pct(value, 2)
        elif key in _COUNT_KEYS:
            value = f"{value:g}"
        else:
            value = inr(value)
        print(f"{key.replace('_', ' '):<34}{value}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sip")
    p.add_argument("--monthly", type=float, required=True)
    p.add_argument("--return", dest="ret", type=float, default=12.0)
    p.add_argument("--years", type=float, required=True)
    p.add_argument("--step-up", type=float, default=0.0)

    p = sub.add_parser("lumpsum")
    p.add_argument("--amount", type=float, required=True)
    p.add_argument("--return", dest="ret", type=float, default=12.0)
    p.add_argument("--years", type=float, required=True)

    p = sub.add_parser("goal")
    p.add_argument("--target", type=float, required=True, help="cost in today's rupees")
    p.add_argument("--years", type=float, required=True)
    p.add_argument("--inflation", type=float, default=6.0)
    p.add_argument("--return", dest="ret", type=float, default=11.0)
    p.add_argument("--existing", type=float, default=0.0)
    p.add_argument("--step-up", type=float, default=0.0)

    p = sub.add_parser("retirement")
    p.add_argument("--age", type=int, required=True)
    p.add_argument("--retire-at", type=int, default=60)
    p.add_argument("--life", type=int, default=85)
    p.add_argument("--monthly-expenses", type=float, required=True, help="today's monthly expenses")
    p.add_argument("--inflation", type=float, default=6.0)
    p.add_argument("--pre-return", type=float, default=11.0)
    p.add_argument("--post-return", type=float, default=7.0)
    p.add_argument("--existing", type=float, default=0.0)
    p.add_argument("--step-up", type=float, default=0.0)

    p = sub.add_parser("emi")
    p.add_argument("--principal", type=float, required=True)
    p.add_argument("--rate", type=float, required=True)
    p.add_argument("--years", type=float, required=True)
    p.add_argument("--prepay-yearly", type=float, default=0.0)

    p = sub.add_parser("emergency")
    p.add_argument("--monthly-expenses", type=float, required=True)
    p.add_argument("--emi", type=float, default=0.0)
    p.add_argument("--insurance-premiums-yearly", type=float, default=0.0)
    p.add_argument("--months", type=int, default=6)

    p = sub.add_parser("insurance")
    p.add_argument("--annual-expenses", type=float, required=True, help="family's yearly expenses without you")
    p.add_argument("--years", type=int, required=True, help="years the family needs support")
    p.add_argument("--liabilities", type=float, default=0.0)
    p.add_argument("--goals", type=float, default=0.0, help="goals to fund, e.g. children's education")
    p.add_argument("--assets", type=float, default=0.0, help="investments the family could use")
    p.add_argument("--existing-cover", type=float, default=0.0)
    p.add_argument("--inflation", type=float, default=6.0)
    p.add_argument("--return", dest="ret", type=float, default=7.0)
    p.add_argument("--annual-income", type=float, default=0.0)

    p = sub.add_parser("fd")
    p.add_argument("--principal", type=float, required=True)
    p.add_argument("--rate", type=float, required=True)
    p.add_argument("--years", type=float, required=True)
    p.add_argument("--compounding", type=int, default=4, help="times a year")
    p.add_argument("--slab", type=float, default=0.0, help="your slab rate, %%")

    p = sub.add_parser("real-return")
    p.add_argument("--nominal", type=float, required=True)
    p.add_argument("--inflation", type=float, default=6.0)
    p.add_argument("--slab", type=float, default=0.0)

    p = sub.add_parser("cagr")
    p.add_argument("--start", type=float, required=True)
    p.add_argument("--end", type=float, required=True)
    p.add_argument("--years", type=float, required=True)

    p = sub.add_parser("xirr")
    p.add_argument("--flows", nargs="+", required=True, help="YYYY-MM-DD:amount, outflows negative")

    a = ap.parse_args(argv)
    if a.cmd == "sip":
        r = sip_future_value(a.monthly, a.ret, a.years, a.step_up)
    elif a.cmd == "lumpsum":
        fv = lumpsum_future_value(a.amount, a.ret, a.years)
        r = {"future_value": fv, "gain": fv - a.amount}
    elif a.cmd == "goal":
        r = goal_plan(a.target, a.years, a.inflation, a.ret, a.existing, a.step_up)
    elif a.cmd == "retirement":
        r = retirement_plan(a.age, a.retire_at, a.life, a.monthly_expenses, a.inflation,
                            a.pre_return, a.post_return, a.existing, a.step_up)
    elif a.cmd == "emi":
        r = emi_plan(a.principal, a.rate, a.years, a.prepay_yearly)
    elif a.cmd == "emergency":
        r = emergency_fund(a.monthly_expenses, a.emi, a.insurance_premiums_yearly, a.months)
    elif a.cmd == "insurance":
        r = insurance_need(a.annual_expenses, a.years, a.liabilities, a.goals, a.assets,
                           a.existing_cover, a.inflation, a.ret, a.annual_income)
    elif a.cmd == "fd":
        r = fd_maturity(a.principal, a.rate, a.years, a.compounding, a.slab)
    elif a.cmd == "real-return":
        r = real_return(a.nominal, a.inflation, a.slab)
    elif a.cmd == "cagr":
        r = {"cagr": cagr(a.start, a.end, a.years)}
    else:
        flows = []
        for item in a.flows:
            d, amount = item.split(":")
            flows.append((date.fromisoformat(d), float(amount)))
        r = {"xirr": xirr(flows)}
    _print(r, a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
