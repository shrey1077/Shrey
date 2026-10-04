---
name: tax-plan
description: Compare the old and new tax regimes for Shrey and build a tax-saving plan for the rest of the year. Use for "which regime", "how do I save tax", salary restructuring, or year-end tax planning.
---

# Tax plan for the year

1. **Pick the year.** The default is the current tax year (FY 2026-27 while that runs). If Shrey
   is still filing an earlier year, ask which one they mean.

2. **Build the input.** Map the profile to `TaxInput` fields (see `tools/income_tax.py`) and write
   `finance/private/tax-input-<fy>.json`. Project full-year figures: salary for the full year,
   expected bonus, interest and dividends. Include capital gains already booked (classify them with
   `tools/capital_gains.py`). Ask only for missing items that would move the answer.

3. **Run it:** `python3 tools/income_tax.py --input finance/private/tax-input-<fy>.json`. Run it
   again with `--json` if you need the breakdown.

4. **Explain the result:**
   - the recommended regime and the saving in rupees
   - the break-even: how much more in deductions the old regime would need, and whether Shrey
     could realistically reach it (EPF, rent, home loan and insurance already count)
   - effective and marginal rates

5. **List the levers that fit Shrey**, ranked by rupee impact, each with an amount and deadline.
   Re-run the tool to show the effect of each one.
   - **Either regime:** employer NPS through salary restructuring (14% of basic + DA in the new
     regime); harvesting up to ₹1.25 lakh of equity LTCG tax-free each year; booking losses
     before 31 March; timing a sale across 31 March; investing through family members in lower
     brackets (mind the clubbing rules for a spouse or minor child).
   - **Old regime only:** filling 80C (prefer EPF/VPF, PPF, ELSS over insurance policies);
     80CCD(1B) NPS; 80D, including parents; HRA with a rent agreement and receipts (landlord's PAN
     if rent is over ₹1 lakh a year); LTA; home-loan interest.
   - **Never** suggest products bought only for the deduction if they are bad investments.

6. **Cover the mechanics:**
   - Salaried with no business income: the regime told to the employer only sets TDS. The final
     choice is made in the ITR.
   - With business income: Form 10-IEA by the due date to opt out, and only one switch back.
   - If TDS will fall short, hand over to `/advance-tax`.

7. **Save** the plan to `finance/private/reports/<date>-tax-plan-<fy>.md`. Offer Calendar reminders
   for the deadlines and a Drive backup.
