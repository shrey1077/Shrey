---
name: onboard
description: Build or refresh Shrey's financial profile (finance/private/profile.yaml) through a short interview. Use when the profile is missing or stale, or when Shrey says "set me up" or "update my details".
---

# Onboard: build Shrey's financial profile

1. **Find what already exists.** Read `finance/private/profile.yaml`. If it is missing and Google
   Drive is connected, look for `CA Advisor/profile.yaml` there. If you find a profile, ask only
   about gaps and changes since `as_of`. Otherwise copy `finance/profile.example.yaml` to
   `finance/private/profile.yaml`.

2. **Offer documents first.** Reading a payslip, Form 16, AIS, CAS statement or loan statement is
   faster and more accurate than recalling numbers. Shrey can upload them, or, with permission, you
   can search Gmail for them. Extract the figures, keep the files in `finance/private/`, and never
   copy the PAN, account numbers or other identifiers.

3. **Interview in short rounds** of three to five questions, one round per message:
   1. Basics: age, city, residential status, family and dependents, employment type.
   2. Income: salary structure (gross, basic + DA, HRA, employer NPS, bonus), freelance or business
      income, interest, dividends, rent.
   3. Monthly cash flow: take-home pay, household spending, rent, EMIs, current SIPs.
   4. Assets: bank and FDs, emergency fund, EPF, PPF, NPS, mutual funds by type, stocks, gold,
      property, any foreign RSUs/ESOPs.
   5. Protection: term cover, health cover (own, employer, parents), any endowment or ULIP
      policies.
   6. Goals and temperament: goals with rough cost and year, retirement age, risk appetite,
      investing experience.
   7. Tax status: regime declared to the employer, last ITR filed, carried-forward losses, any
      notices.

   Approximate numbers are fine; "skip" is fine. Never ask for a PAN, Aadhaar number, account
   numbers or passwords.

4. **Write the profile** and set `as_of` to today.

5. **Play it back** in one screen:
   - net worth (assets minus loans)
   - monthly surplus and savings rate
   - emergency-fund cover in months (`python3 tools/planner.py emergency ...`)
   - the three things most worth looking at next, each pointing to the command that handles it
     (for example `/tax-plan` or `/health-check`)

6. **Offer a backup** of the profile to the `CA Advisor` folder in Google Drive, since
   `finance/private/` won't exist in the next cloud session.
