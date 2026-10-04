"""Indian personal income-tax rules, by financial year.

Rules verified as of 2026-10-04:
- FY 2025-26 (AY 2026-27): Finance Act 2025, under the Income-tax Act, 1961.
- FY 2026-27 ("tax year 2026-27"): the Income-tax Act, 2025 applies from 1 April 2026.
  Budget 2026 left slabs, the rebate, standard deduction, surcharge and cess
  unchanged, so this year reuses the FY 2025-26 figures.

When a new Finance Act arrives, add a new year here instead of editing an old one.
"""

INF = float("inf")

# Each slab table is a list of (upper_limit, rate). Income above the previous
# upper limit and up to this one is taxed at `rate`.
_NEW_REGIME_SLABS = [
    (400_000, 0.00),
    (800_000, 0.05),
    (1_200_000, 0.10),
    (1_600_000, 0.15),
    (2_000_000, 0.20),
    (2_400_000, 0.25),
    (INF, 0.30),
]

_OLD_REGIME_SLABS = {
    "below_60": [(250_000, 0.00), (500_000, 0.05), (1_000_000, 0.20), (INF, 0.30)],
    "60_to_79": [(300_000, 0.00), (500_000, 0.05), (1_000_000, 0.20), (INF, 0.30)],
    "80_plus": [(500_000, 0.00), (1_000_000, 0.20), (INF, 0.30)],
}

# (threshold, rate): the rate applies when total income exceeds the threshold.
_OLD_SURCHARGE = [(5_000_000, 0.10), (10_000_000, 0.15), (20_000_000, 0.25), (50_000_000, 0.37)]
_NEW_SURCHARGE = [(5_000_000, 0.10), (10_000_000, 0.15), (20_000_000, 0.25)]

_FY_2025_26 = {
    "label": "FY 2025-26 (AY 2026-27), Income-tax Act 1961",
    "new": {
        "slabs": _NEW_REGIME_SLABS,
        "standard_deduction": 75_000,
        "rebate_limit": 1_200_000,
        "rebate_max": 60_000,
        "rebate_covers_special_rates": False,
        "marginal_relief_on_rebate": True,
        "surcharge": _NEW_SURCHARGE,
        "employer_nps_pct": 0.14,
        "family_pension_cap": 25_000,
    },
    "old": {
        "slabs": _OLD_REGIME_SLABS,
        "standard_deduction": 50_000,
        "rebate_limit": 500_000,
        "rebate_max": 12_500,
        # In the old regime the rebate can absorb tax on STCG (111A) and other
        # LTCG (112), but never tax on equity LTCG (112A).
        "rebate_covers_special_rates": True,
        "marginal_relief_on_rebate": False,
        "surcharge": _OLD_SURCHARGE,
        "employer_nps_pct": 0.10,
        "family_pension_cap": 15_000,
        "limits": {
            "80c": 150_000,          # 80C + 80CCC + 80CCD(1) combined
            "80ccd_1b": 50_000,      # extra NPS
            "80d_self": 25_000,
            "80d_self_senior": 50_000,
            "80d_parents": 25_000,
            "80d_parents_senior": 50_000,
            "80tta": 10_000,         # savings interest, below 60
            "80ttb": 50_000,         # deposit interest, 60 and above
            "home_loan_interest_self": 200_000,
            "house_property_loss_setoff": 200_000,
            "professional_tax": 2_500,
        },
    },
    "cess": 0.04,
    "special_rate_surcharge_cap": 0.15,
    "stcg_111a_rate": 0.20,
    "ltcg_112a_rate": 0.125,
    "ltcg_112a_exemption": 125_000,
    "ltcg_112_rate": 0.125,
    "ltcg_112_indexed_rate": 0.20,
}

_FY_2026_27 = {**_FY_2025_26, "label": "FY 2026-27 (tax year 2026-27), Income-tax Act 2025"}

RULES = {
    "2025-26": _FY_2025_26,
    "2026-27": _FY_2026_27,
}

DEFAULT_FY = "2026-27"

# Cost Inflation Index, keyed by the financial year's starting calendar year.
COST_INFLATION_INDEX = {
    2001: 100, 2002: 105, 2003: 109, 2004: 113, 2005: 117, 2006: 122,
    2007: 129, 2008: 137, 2009: 148, 2010: 167, 2011: 184, 2012: 200,
    2013: 220, 2014: 240, 2015: 254, 2016: 264, 2017: 272, 2018: 280,
    2019: 289, 2020: 301, 2021: 317, 2022: 331, 2023: 348, 2024: 363,
    2025: 376, 2026: 384,
}


def rules_for(fy: str) -> dict:
    if fy not in RULES:
        known = ", ".join(sorted(RULES))
        raise ValueError(f"No tax rules for FY {fy}. Known years: {known}. Add the year to tools/tax_rules.py.")
    return RULES[fy]


def old_regime_age_band(age: int) -> str:
    if age >= 80:
        return "80_plus"
    if age >= 60:
        return "60_to_79"
    return "below_60"
