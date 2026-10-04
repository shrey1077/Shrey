#!/usr/bin/env python3
"""Compute Indian income tax for a resident individual under the old and new regimes.

Every amount is annual and in rupees. Run with --help for all inputs.

Examples:
  python3 tools/income_tax.py --salary 1800000 --basic-da 720000 \
      --hra-received 288000 --rent-paid 300000 --metro --d80c 150000 --d80d-self 25000
  python3 tools/income_tax.py --input finance/private/tax-input.json --json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, fields

from fmt import inr, pct
from tax_rules import DEFAULT_FY, old_regime_age_band, rules_for

# Order in which an unused basic exemption is set against special-rate gains:
# the highest-taxed gains first.
_GAIN_KEYS = ["stcg_111a", "ltcg_112_indexed", "ltcg_112", "ltcg_112a"]


@dataclass
class TaxInput:
    fy: str = DEFAULT_FY
    age: int = 30
    resident: bool = True

    # Salary or pension. `salary` is gross: basic, DA, HRA, allowances, bonus,
    # perquisites, and the employer's NPS contribution.
    salary: float = 0.0
    basic_da: float = 0.0
    hra_received: float = 0.0
    rent_paid: float = 0.0
    metro: bool = False
    hra_exemption: float | None = None  # overrides the computed HRA exemption
    lta_exemption: float = 0.0
    other_salary_exemptions: float = 0.0
    professional_tax: float = 0.0
    employer_nps: float = 0.0  # 80CCD(2); deductible in both regimes

    # House property
    home_loan_interest_self: float = 0.0
    rent_received: float = 0.0
    municipal_tax: float = 0.0
    home_loan_interest_let_out: float = 0.0

    # Net taxable business or professional profit (for example 50% of gross
    # receipts under presumptive taxation, section 44ADA).
    business_income: float = 0.0

    # Other sources
    savings_interest: float = 0.0
    deposit_interest: float = 0.0
    dividends: float = 0.0
    family_pension: float = 0.0
    other_income: float = 0.0

    # Capital gains for the year, net of set-off of losses
    stcg_slab: float = 0.0  # short-term gains taxed at slab rates
    stcg_111a: float = 0.0  # listed equity / equity MF, short-term: 20%
    ltcg_112a: float = 0.0  # listed equity / equity MF, long-term: 12.5% above 1.25 lakh
    ltcg_112: float = 0.0  # other long-term gains: 12.5%
    ltcg_112_indexed: float = 0.0  # property bought before 23 Jul 2024, indexed: 20%

    # Old-regime deductions
    d80c: float = 0.0
    d80ccd_1b: float = 0.0
    d80d_self: float = 0.0
    d80d_parents: float = 0.0
    parents_senior: bool = False
    d80e: float = 0.0
    d80g: float = 0.0  # the deductible amount, after the 50%/100% and 10% limits
    other_deductions: float = 0.0

    # Tax already paid for the year
    tds: float = 0.0
    advance_tax: float = 0.0


def slab_tax(income: float, slabs) -> float:
    tax, lower = 0.0, 0.0
    for upper, rate in slabs:
        if income <= lower:
            break
        tax += (min(income, upper) - lower) * rate
        lower = upper
    return tax


def surcharge_rate(total_income: float, table) -> float:
    rate = 0.0
    for threshold, r in table:
        if total_income > threshold:
            rate = r
    return rate


def round_tax(amount: float) -> int:
    """Section 288B: drop the paise, then round to the nearest 10, with 5 rounding up."""
    rupees = math.floor(amount + 1e-6)
    return (rupees + 5) // 10 * 10


def hra_exemption(basic_da: float, hra_received: float, rent_paid: float, metro: bool) -> float:
    if hra_received <= 0 or rent_paid <= 0 or basic_da <= 0:
        return 0.0
    return max(0.0, min(hra_received, rent_paid - 0.10 * basic_da, (0.50 if metro else 0.40) * basic_da))


def _slabs(inp: TaxInput, regime: str):
    params = rules_for(inp.fy)[regime]
    if regime == "old":
        return params["slabs"][old_regime_age_band(inp.age)]
    return params["slabs"]


def _tax_on(inp: TaxInput, regime: str, normal: float, gains: dict) -> dict:
    """Tax and surcharge (before cess and surcharge marginal relief) on an income mix."""
    rules = rules_for(inp.fy)
    p = rules[regime]
    slabs = _slabs(inp, regime)
    total = normal + sum(gains.values())

    taxable = dict(gains)
    taxable["ltcg_112a"] = max(0.0, gains["ltcg_112a"] - rules["ltcg_112a_exemption"])
    # A resident may use any basic exemption left over by slab income against these gains.
    shortfall = max(0.0, slabs[0][0] - normal) if inp.resident else 0.0
    for key in _GAIN_KEYS:
        used = min(shortfall, taxable[key])
        taxable[key] -= used
        shortfall -= used

    rates = {
        "stcg_111a": rules["stcg_111a_rate"],
        "ltcg_112_indexed": rules["ltcg_112_indexed_rate"],
        "ltcg_112": rules["ltcg_112_rate"],
        "ltcg_112a": rules["ltcg_112a_rate"],
    }
    normal_tax = slab_tax(normal, slabs)
    special = {k: taxable[k] * rates[k] for k in _GAIN_KEYS}
    special_tax = sum(special.values())

    rebate = 0.0
    if inp.resident:
        rebatable = normal_tax
        if p["rebate_covers_special_rates"]:
            rebatable += special["stcg_111a"] + special["ltcg_112"] + special["ltcg_112_indexed"]
        if total <= p["rebate_limit"]:
            rebate = min(p["rebate_max"], rebatable)
        elif p["marginal_relief_on_rebate"]:
            # Tax may not exceed the income earned above the rebate limit.
            excess = total - p["rebate_limit"]
            if normal_tax + special_tax > excess:
                rebate = min(rebatable, normal_tax + special_tax - excess)

    rate = surcharge_rate(total, p["surcharge"])
    surcharge = 0.0
    if rate:
        # Surcharge on dividends and special-rate gains is capped (15%).
        capped_rate = min(rate, rules["special_rate_surcharge_cap"])
        dividends_in_normal = min(inp.dividends, normal)
        dividend_tax = normal_tax - slab_tax(normal - dividends_in_normal, slabs)
        surcharge = (normal_tax - dividend_tax - rebate) * rate + (dividend_tax + special_tax) * capped_rate

    return {
        "total_income": total,
        "taxable_gains": taxable,
        "normal_tax": normal_tax,
        "special_tax": special_tax,
        "rebate": rebate,
        "surcharge_rate": rate,
        "surcharge": surcharge,
        "tax_and_surcharge": normal_tax + special_tax - rebate + surcharge,
    }


def _reduce_income(normal: float, gains: dict, cut: float):
    """Lower the income mix by `cut`, slab income first, then gains."""
    n = max(0.0, normal - cut)
    cut -= normal - n
    g = dict(gains)
    for key in _GAIN_KEYS:
        used = min(cut, g[key])
        g[key] -= used
        cut -= used
    return n, g


def compute(inp: TaxInput, regime: str, with_marginal_rate: bool = True) -> dict:
    if regime not in ("old", "new"):
        raise ValueError("regime must be 'old' or 'new'")
    rules = rules_for(inp.fy)
    p = rules[regime]
    old = regime == "old"
    limits = rules["old"]["limits"]
    notes: list[str] = []

    # Salary
    exemptions = 0.0
    if old:
        hra = inp.hra_exemption
        if hra is None:
            hra = hra_exemption(inp.basic_da, inp.hra_received, inp.rent_paid, inp.metro)
            if inp.hra_received and inp.rent_paid and not inp.basic_da:
                notes.append("HRA exemption needs --basic-da; it was taken as 0.")
        exemptions = min(inp.salary, hra + inp.lta_exemption + inp.other_salary_exemptions)
    standard_deduction = min(p["standard_deduction"], inp.salary - exemptions)
    professional_tax = min(inp.professional_tax, limits["professional_tax"]) if old else 0.0
    salary_income = max(0.0, inp.salary - exemptions - standard_deduction - professional_tax)

    # House property
    let_out = max(0.0, inp.rent_received - inp.municipal_tax) * 0.70 - inp.home_loan_interest_let_out
    if old:
        self_occupied = -min(inp.home_loan_interest_self, limits["home_loan_interest_self"])
        house_property = self_occupied + let_out
        if house_property < -limits["house_property_loss_setoff"]:
            notes.append(
                f"House-property loss of {inr(-house_property)} capped at {inr(limits['house_property_loss_setoff'])} "
                "for set-off this year; the rest carries forward for 8 years."
            )
            house_property = -limits["house_property_loss_setoff"]
    else:
        house_property = max(0.0, let_out)
        if inp.home_loan_interest_self:
            notes.append("New regime: no deduction for interest on a self-occupied home loan.")
        if let_out < 0:
            notes.append("New regime: a let-out property loss cannot be set off against other income.")

    # Other sources
    family_pension_deduction = min(inp.family_pension / 3, p["family_pension_cap"])
    other_sources = (
        inp.savings_interest + inp.deposit_interest + inp.dividends + inp.other_income
        + inp.family_pension - family_pension_deduction
    )

    gross_normal = max(0.0, salary_income + house_property + inp.business_income + other_sources + inp.stcg_slab)

    # Deductions, which can only reduce slab-rate income
    nps_cap = p["employer_nps_pct"] * inp.basic_da if inp.basic_da else float("inf")
    employer_nps = min(inp.employer_nps, nps_cap)
    if inp.employer_nps > employer_nps:
        notes.append(f"{regime.title()} regime: employer NPS deduction capped at {pct(p['employer_nps_pct'], 0)} of basic + DA.")
    elif inp.employer_nps and not inp.basic_da:
        notes.append("Employer NPS taken in full; pass --basic-da to apply the % of salary cap.")
    deductions = {"80CCD(2) employer NPS": employer_nps}
    if old:
        self_cap = limits["80d_self_senior"] if inp.age >= 60 else limits["80d_self"]
        parents_cap = limits["80d_parents_senior"] if inp.parents_senior else limits["80d_parents"]
        if inp.age >= 60 and inp.resident:
            interest = ("80TTB deposit interest", min(inp.savings_interest + inp.deposit_interest, limits["80ttb"]))
        else:
            interest = ("80TTA savings interest", min(inp.savings_interest, limits["80tta"]))
        deductions.update({
            "80C": min(inp.d80c, limits["80c"]),
            "80CCD(1B) NPS": min(inp.d80ccd_1b, limits["80ccd_1b"]),
            "80D health insurance": min(inp.d80d_self, self_cap) + min(inp.d80d_parents, parents_cap),
            "80E education loan": inp.d80e,
            "80G donations": inp.d80g,
            interest[0]: interest[1],
            "other": inp.other_deductions,
        })
    else:
        deductions["other"] = inp.other_deductions
    claimed = sum(deductions.values())
    total_deductions = min(claimed, gross_normal)

    normal = gross_normal - total_deductions
    gains = {
        "stcg_111a": inp.stcg_111a,
        "ltcg_112_indexed": inp.ltcg_112_indexed,
        "ltcg_112": inp.ltcg_112,
        "ltcg_112a": inp.ltcg_112a,
    }
    res = _tax_on(inp, regime, normal, gains)
    total_income = res["total_income"]

    if not old and inp.resident and total_income <= p["rebate_limit"] and res["special_tax"]:
        notes.append("New regime: the 87A rebate does not cover tax on special-rate capital gains.")
    if res["rebate"] and total_income > p["rebate_limit"]:
        notes.append(f"Marginal relief applied just above the {inr(p['rebate_limit'])} rebate limit.")

    # Marginal relief on surcharge: crossing a surcharge threshold may not cost
    # more in tax than the income earned above it.
    surcharge_relief = 0.0
    crossed = [t for t, _ in p["surcharge"] if total_income > t]
    if crossed:
        threshold = max(crossed)
        at_threshold = _tax_on(inp, regime, *_reduce_income(normal, gains, total_income - threshold))
        ceiling = at_threshold["tax_and_surcharge"] + (total_income - threshold)
        if res["tax_and_surcharge"] > ceiling:
            surcharge_relief = min(res["surcharge"], res["tax_and_surcharge"] - ceiling)
            notes.append("Marginal relief on surcharge applied.")

    surcharge = res["surcharge"] - surcharge_relief
    tax_after_rebate = res["normal_tax"] + res["special_tax"] - res["rebate"]
    cess = (tax_after_rebate + surcharge) * rules["cess"]
    total_tax = round_tax(tax_after_rebate + surcharge + cess)

    # Measured, not looked up, so rebate and surcharge marginal relief show through.
    marginal = None
    if with_marginal_rate:
        bumped = TaxInput(**{**asdict(inp), "other_income": inp.other_income + 10_000})
        marginal = (compute(bumped, regime, with_marginal_rate=False)["total_tax"] - total_tax) / 10_000

    return {
        "regime": regime,
        "fy": inp.fy,
        "gross_salary": inp.salary,
        "salary_exemptions": exemptions,
        "standard_deduction": standard_deduction,
        "professional_tax": professional_tax,
        "income_from_salary": salary_income,
        "income_from_house_property": house_property,
        "business_income": inp.business_income,
        "income_from_other_sources": other_sources,
        "stcg_slab": inp.stcg_slab,
        "gross_total_income": gross_normal + sum(gains.values()),
        "deductions": deductions,
        "total_deductions": total_deductions,
        "slab_income": normal,
        "special_rate_gains": gains,
        "total_income": total_income,
        "tax_on_slab_income": res["normal_tax"],
        "tax_on_special_rate_gains": res["special_tax"],
        "rebate_87a": res["rebate"],
        "surcharge": surcharge,
        "surcharge_relief": surcharge_relief,
        "cess": cess,
        "total_tax": total_tax,
        "tds": inp.tds,
        "advance_tax": inp.advance_tax,
        "balance_payable": total_tax - inp.tds - inp.advance_tax,
        "effective_rate": total_tax / total_income if total_income else 0.0,
        "marginal_rate": marginal,
        "notes": notes,
    }


def breakeven_extra_deductions(inp: TaxInput, target_tax: float) -> float | None:
    """Extra old-regime deductions needed for the old regime to cost no more than target_tax."""
    def old_tax(extra: float) -> float:
        trial = TaxInput(**{**asdict(inp), "other_deductions": inp.other_deductions + extra})
        return compute(trial, "old", with_marginal_rate=False)["total_tax"]

    if old_tax(0) <= target_tax:
        return 0.0
    hi = compute(inp, "old", with_marginal_rate=False)["gross_total_income"]
    if old_tax(hi) > target_tax:
        return None
    lo = 0.0
    while hi - lo > 100:
        mid = (lo + hi) / 2
        if old_tax(mid) <= target_tax:
            hi = mid
        else:
            lo = mid
    return float(-(-hi // 100) * 100)  # round up to the next 100


def compare(inp: TaxInput) -> dict:
    old, new = compute(inp, "old"), compute(inp, "new")
    better = "new" if new["total_tax"] <= old["total_tax"] else "old"
    result = {
        "old": old,
        "new": new,
        "recommended": better,
        "saving": abs(old["total_tax"] - new["total_tax"]),
    }
    if better == "new":
        result["old_needs_extra_deductions"] = breakeven_extra_deductions(inp, new["total_tax"])
    return result


def _row(label: str, old, new) -> str:
    def cell(v):
        if v is None:
            return ""
        return v if isinstance(v, str) else inr(v)
    return f"{label:<38}{cell(old):>16}{cell(new):>16}"


def render(inp: TaxInput, result: dict) -> str:
    o, n = result["old"], result["new"]
    rules = rules_for(inp.fy)
    out = [
        f"Income tax - {rules['label']}",
        f"{'Resident' if inp.resident else 'Non-resident'} individual, age {inp.age}",
        "",
        f"{'':<38}{'Old regime':>16}{'New regime':>16}",
    ]
    rows = [
        ("Gross salary / pension", "gross_salary"),
        ("  less exemptions (HRA, LTA, ...)", "salary_exemptions"),
        ("  less standard deduction", "standard_deduction"),
        ("  less professional tax", "professional_tax"),
        ("Income from salary", "income_from_salary"),
        ("Income from house property", "income_from_house_property"),
        ("Business / profession", "business_income"),
        ("Other sources", "income_from_other_sources"),
        ("Short-term gains at slab rates", "stcg_slab"),
        ("Gross total income", "gross_total_income"),
        ("  less deductions (Chapter VI-A)", "total_deductions"),
        ("Total income", "total_income"),
        ("Tax on slab income", "tax_on_slab_income"),
        ("Tax on special-rate gains", "tax_on_special_rate_gains"),
        ("  less rebate u/s 87A", "rebate_87a"),
        ("Surcharge", "surcharge"),
        ("Health & education cess (4%)", "cess"),
        ("TOTAL TAX", "total_tax"),
    ]
    for label, key in rows:
        if key in ("business_income", "stcg_slab", "professional_tax", "surcharge") and not (o[key] or n[key]):
            continue
        out.append(_row(label, o[key], n[key]))
    if inp.tds or inp.advance_tax:
        out.append(_row("  less TDS + advance tax", o["tds"] + o["advance_tax"], n["tds"] + n["advance_tax"]))
        out.append(_row("Balance payable (- = refund)", o["balance_payable"], n["balance_payable"]))
    out.append(_row("Effective tax rate", pct(o["effective_rate"]), pct(n["effective_rate"])))
    out.append(_row("Marginal rate on next rupee", pct(o["marginal_rate"]), pct(n["marginal_rate"])))

    claimed = [(k, v) for k, v in o["deductions"].items() if v]
    if claimed:
        out += ["", "Old-regime deductions counted: " + ", ".join(f"{k} {inr(v)}" for k, v in claimed)]

    out.append("")
    better = result["recommended"]
    if result["saving"] == 0:
        out.append("Both regimes cost the same.")
    else:
        out.append(f"Recommendation: the {better} regime saves {inr(result['saving'])}.")
    extra = result.get("old_needs_extra_deductions")
    if better == "new" and extra:
        out.append(f"The old regime would need {inr(extra)} more in deductions/exemptions to break even.")
    elif better == "new" and extra is None:
        out.append("No amount of extra deductions makes the old regime cheaper.")

    notes = list(dict.fromkeys(o["notes"] + n["notes"]))
    if notes:
        out += ["", "Notes:"] + [f"- {note}" for note in notes]
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Indian income tax: old vs new regime. All amounts are annual, in rupees.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", help="JSON file with any of the fields below (CLI flags override it)")
    parser.add_argument("--regime", choices=["old", "new", "both"], default="both")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    for f in fields(TaxInput):
        flag = "--" + f.name.replace("_", "-")
        if f.type in ("bool", bool):
            parser.add_argument(flag, dest=f.name, action=argparse.BooleanOptionalAction, default=argparse.SUPPRESS)
        elif f.name == "fy":
            parser.add_argument(flag, dest=f.name, default=argparse.SUPPRESS, help=f"financial year (default {DEFAULT_FY})")
        else:
            kind = int if f.name == "age" else float
            parser.add_argument(flag, dest=f.name, type=kind, default=argparse.SUPPRESS)
    return parser


def parse_input(argv=None) -> tuple[TaxInput, argparse.Namespace]:
    args = build_parser().parse_args(argv)
    values = {}
    if args.input:
        with open(args.input) as fh:
            values.update(json.load(fh))
    names = {f.name for f in fields(TaxInput)}
    unknown = set(values) - names
    if unknown:
        raise SystemExit(f"Unknown fields in {args.input}: {', '.join(sorted(unknown))}")
    values.update({k: v for k, v in vars(args).items() if k in names})
    return TaxInput(**values), args


def main(argv=None) -> int:
    inp, args = parse_input(argv)
    if args.regime == "both":
        result = compare(inp)
        print(json.dumps(result, indent=2) if args.json else render(inp, result))
    else:
        result = compute(inp, args.regime)
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
