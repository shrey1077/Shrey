---
name: advance-tax
description: Work out whether Shrey owes advance tax this year, how much is due by each instalment date, and any 234B/234C interest. Use for freelance or business income, large capital gains, rent or interest income, or when TDS will not cover the tax.
---

# Advance tax

1. **Project the full year's tax** with `tools/income_tax.py`: expected salary, freelance or
   business income, interest, rent, and capital gains booked so far. Use the regime Shrey will
   file under.

2. **Estimate the year's TDS and TCS**: employer TDS for the full year, TDS on interest, rent or
   professional fees, and any TCS on foreign remittances.

3. **Run** `python3 tools/advance_tax.py --tax <total> --tds <tds>`. Add `--paid-jun/--paid-sep/...`
   for instalments already paid (from the profile), `--presumptive` for 44AD/44ADA, or
   `--senior-without-business`.

4. **Report:**
   - whether advance tax is required at all (tax after TDS of ₹10,000 or more)
   - the next due date and exact amount, then the rest of the schedule
   - interest already incurred on missed instalments, and how to stop it growing
   - capital gains or dividends arising mid-year: tax on them can go in the remaining
     instalments without 234C interest for the earlier ones
   - salaried with other income: an alternative is to ask the employer to deduct more TDS by
     declaring the other income

5. **How to pay:** income-tax portal, e-Pay Tax, "Income Tax (other than companies)", minor head
   100 (advance tax). Record each payment in the profile under `tax.advance_tax_paid`. Keep the
   challan details out of the repo.

6. **Offer Google Calendar reminders** for the remaining instalment dates (15 Jun, 15 Sep, 15 Dec,
   15 Mar), each with the amount.
