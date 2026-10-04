---
name: itr
description: Prepare and check Shrey's income-tax return - pick the ITR form, gather documents, reconcile Form 16 / AIS / 26AS, compute tax, and walk through filing and e-verification. Use for anything about filing, revising or tracking an ITR.
---

# Prepare the income-tax return

1. **Pin down the year and the deadline** from `finance/knowledge/india-tax-reference.md`:
   original, belated, revised or updated (ITR-U), and what being late costs (234F fee, 234A
   interest, losing loss carry-forward). If the deadline is close, say so up front.

2. **Choose the form** (ITR-1/2/3/4) from the income profile using the reference table. Say why,
   and name anything that would push Shrey to a different form: capital gains above ₹1.25 lakh,
   foreign assets or RSUs, F&O trading, a directorship, more than one house.

3. **Gather documents** with a checklist ticked against what is already in `finance/private/`:
   - Form 16 (Parts A and B) from every employer in the year
   - AIS and TIS, and Form 26AS (from the income-tax portal)
   - Interest certificates from every bank and post office
   - Capital-gains statements: broker P&L, CAS, MF capital-gains reports
   - Rent receipts and agreement (HRA), home-loan interest certificate, 80C/80D proofs (old
     regime)
   - Foreign assets: account statements, RSU/ESOP vesting and sale records (Schedule FA uses the
     calendar year)
   - Last year's ITR, for carried-forward losses

   With permission, search Gmail for these. Never ask for portal login details.

4. **Reconcile, line by line**: Form 16 against AIS/TIS against 26AS for salary, TDS, interest,
   dividends, securities transactions and rent. List every mismatch with its likely cause and fix:
   an interest accrual not reported, a duplicate entry, TDS under the wrong PAN, a deductor's error.
   For a wrong AIS entry, give feedback on the portal before filing.

5. **Compute** with the tools: `capital_gains.py` for each sale, then `income_tax.py` for both
   regimes. Check the TDS credit and the balance payable or refund. If tax is payable, it is paid
   as self-assessment tax (minor head 300) before filing.

6. **Walk through filing on incometax.gov.in:** use the pre-filled data, schedule by schedule.
   Flag the schedules people get wrong: CG, FA, AL (asset-liability, total income above ₹1 crore),
   exempt income, the regime choice, bank account for refund.

7. **E-verify within 30 days** (Aadhaar OTP or net banking). Then track the 143(1) intimation and
   the refund. Hand any intimation or notice to `/notice`.

8. **Save** a filing summary (form, figures, acknowledgement date, no identifiers) to
   `finance/private/reports/<date>-itr-<fy>.md`, and update `tax.last_itr` in the profile.
