---
name: goal-plan
description: Turn Shrey's goals (home, car, education, travel, wedding, retirement, financial independence) into monthly SIPs with asset allocation and a glide path. Use for "how much should I invest", "can I afford X by Y", or retirement planning.
---

# Goal-based plan

1. **List the goals** from the profile, or ask: name, cost in today's rupees, target year, and how
   firm the goal is (must-have or nice-to-have).

2. **Set assumptions** and state them in the plan. Shrey can change any of them.
   - Inflation: 6% general; 8–10% for education and healthcare.
   - Returns (pre-tax, conservative): equity 10–11%, hybrid 8–9%, debt or liquid 6.5–7%.
   - Allocation by horizon: under 3 years, debt or liquid only; 3–5 years, hybrid or about 40%
     equity; over 5 years, 60–80% equity depending on risk appetite. Use the blended return for the
     goal's allocation.

3. **Compute each goal:**
   `python3 tools/planner.py goal --target <today> --years <n> --inflation <i> --return <r> --existing <earmarked>`.
   Add `--step-up 10` to show the effect of raising the SIP 10% a year with salary.
   For retirement:
   `python3 tools/planner.py retirement --age <a> --retire-at <r> --monthly-expenses <today> --existing <epf+nps+ppf+mf earmarked>`.

4. **Check affordability.** Compare the total monthly SIP needed with the monthly surplus. If it
   doesn't fit, rank the goals and show the trade-offs: push the date out, cut the target, use a
   step-up SIP, or drop a nice-to-have.

5. **Map goals to products:** categories, not specific funds or stocks. For example, a Nifty 50
   or total-market index fund, a flexi-cap fund, a short-duration or target-maturity debt fund,
   PPF or EPF for retirement debt, a liquid fund for the emergency fund. Use direct plans, and keep
   the number of funds small.

6. **Glide path:** move a goal's money from equity to debt over the 2–3 years before it is due.
   Rebalance once a year, using new money where possible to avoid triggering capital gains.

7. **Save** the plan to `finance/private/reports/<date>-goal-plan.md`, record the goals in the
   profile, and offer a Drive backup.
