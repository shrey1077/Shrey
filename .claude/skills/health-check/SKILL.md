---
name: health-check
description: Full financial health review for Shrey - emergency fund, insurance, debt, savings rate, asset allocation, retirement readiness, tax efficiency and estate basics - with a scorecard and a prioritised action plan. Use for "how am I doing financially", annual reviews, or after a life event (new job, marriage, child, home purchase).
---

# Financial health check

Use the profile. Ask for missing numbers only when a section can't be scored without them; otherwise
mark it "unknown". Run the calculators for every figure.

| Area | Measure | Healthy |
|---|---|---|
| Emergency fund | months of (expenses + EMIs) held liquid: `planner.py emergency` | ≥ 6 (≥ 9 with variable or single income) |
| Life cover | term cover against need: `planner.py insurance` | cover ≥ need; no dependents means none needed |
| Health cover | own cover outside the employer's group policy, plus super top-up | ≥ ₹10 lakh family floater in a metro; parents covered separately |
| Debt | EMIs ÷ take-home pay; any credit-card or personal-loan balance | ≤ 40%; no revolving high-interest debt |
| Savings rate | (take-home − spending) ÷ take-home | ≥ 20–30% |
| Asset allocation | equity / debt / gold / real estate against goal horizons and risk appetite | matches the goals (see `/goal-plan`) |
| Retirement | corpus on track: `planner.py retirement` | current SIP ≥ required SIP |
| Tax efficiency | regime choice and unused levers: `income_tax.py` | on the cheaper regime, no money left on the table |
| Product hygiene | endowment, ULIP or money-back policies; regular (non-direct) MF plans; idle savings balances | none, or a plan to exit |
| Estate | nominations everywhere, a will, a family member knows where things are | all done |

Steps:

1. Score each area ✅ / ⚠️ / ❌ / unknown, with the actual number next to the target.
2. List the **five most important actions**, in the order the priority ladder in `CLAUDE.md` gives,
   each with a rupee amount and a date. For example: "Move ₹2,40,000 into a liquid fund to reach 6
   months' cover by March."
3. For a policy that is probably mis-sold, compute its IRR (`planner.py xirr`), compare it with
   term insurance plus investing the difference, and set out the surrender versus paid-up options.
   Don't recommend surrendering in the same breath; lay out the trade-off.
4. Save the review to `finance/private/reports/<date>-health-check.md`, update the profile, and
   offer a Drive backup. Suggest repeating the check every year, or after any big life event.
