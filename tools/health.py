#!/usr/bin/env python3
"""Body numbers for Donna's food and diet planning: BMI, energy needs, protein and water.

Donna runs this instead of estimating. These are population formulas, not a diagnosis; anything
abnormal in a health report goes to a doctor, and a medical condition needs a registered dietitian.

  python3 tools/health.py --sex male --age 30 --height-cm 175 --weight-kg 78 --activity light
  python3 tools/health.py --sex female --age 28 --height-cm 160 --weight-kg 55 --activity moderate --goal lose

- BMI bands use the WHO cut-offs for Asian adults (overweight from 23, obese from 25), which suit
  Indians better than the global 25/30.
- Resting energy (BMR) uses the Mifflin-St Jeor equation; daily needs (TDEE) multiply it by an
  activity factor.
- A weight-loss target is a deficit of about 15% of TDEE, never below BMR or 1,200 kcal; a gain
  target is a surplus of about 10%.
- Protein: 0.8 g/kg is the minimum (ICMR-NIN); 1.2-1.6 g/kg suits active people and fat loss.
"""

from __future__ import annotations

import argparse
import json
import sys

ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very_active": 1.9}
ASIAN_BMI = [(18.5, "underweight"), (23.0, "normal"), (25.0, "overweight"), (float("inf"), "obese")]


def bmi(weight_kg: float, height_cm: float) -> float:
    return weight_kg / (height_cm / 100) ** 2


def bmi_band(value: float) -> str:
    return next(label for limit, label in ASIAN_BMI if value < limit)


def bmr(sex: str, age: int, height_cm: float, weight_kg: float) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


def needs(sex: str, age: int, height_cm: float, weight_kg: float, activity: str = "light",
          goal: str = "maintain") -> dict:
    if activity not in ACTIVITY:
        raise ValueError(f"activity is one of {', '.join(ACTIVITY)}")
    if sex not in ("male", "female"):
        raise ValueError("sex is male or female (the equations are sex-specific)")
    resting = bmr(sex, age, height_cm, weight_kg)
    tdee = resting * ACTIVITY[activity]
    if goal == "lose":
        target = max(tdee * 0.85, resting, 1200)
    elif goal == "gain":
        target = tdee * 1.10
    elif goal == "maintain":
        target = tdee
    else:
        raise ValueError("goal is lose, maintain or gain")
    value = bmi(weight_kg, height_cm)
    return {
        "bmi": round(value, 1),
        "bmi_band_asian": bmi_band(value),
        "healthy_weight_kg_asian": [round(18.5 * (height_cm / 100) ** 2, 1), round(22.9 * (height_cm / 100) ** 2, 1)],
        "bmr_kcal": round(resting),
        "tdee_kcal": round(tdee),
        "target_kcal": round(target / 10) * 10,
        "protein_g": [round(0.8 * weight_kg), round(1.2 * weight_kg), round(1.6 * weight_kg)],
        "water_litres": round(weight_kg * 0.035, 1),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sex", required=True, choices=["male", "female"])
    ap.add_argument("--age", type=int, required=True)
    ap.add_argument("--height-cm", type=float, required=True)
    ap.add_argument("--weight-kg", type=float, required=True)
    ap.add_argument("--activity", default="light", choices=list(ACTIVITY))
    ap.add_argument("--goal", default="maintain", choices=["lose", "maintain", "gain"])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = needs(a.sex, a.age, a.height_cm, a.weight_kg, a.activity, a.goal)
    if a.json:
        print(json.dumps(r, indent=2))
        return 0
    lo, hi = r["healthy_weight_kg_asian"]
    p_min, p_mid, p_high = r["protein_g"]
    print(f"BMI                      {r['bmi']} ({r['bmi_band_asian']}, Asian cut-offs)")
    print(f"Healthy weight range     {lo}-{hi} kg")
    print(f"Resting energy (BMR)     {r['bmr_kcal']:,} kcal/day")
    print(f"Daily needs (TDEE)       {r['tdee_kcal']:,} kcal/day ({a.activity})")
    print(f"Target to {a.goal:<14} {r['target_kcal']:,} kcal/day")
    print(f"Protein                  {p_min} g minimum, {p_mid}-{p_high} g if active or losing fat")
    print(f"Water                    about {r['water_litres']} litres/day, more in Ahmedabad's heat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
