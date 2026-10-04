---
name: notice
description: Explain an income-tax notice or intimation Shrey received, check it against the return and AIS, and draft the response. Use for 143(1) intimations, defective-return (139(9)) notices, demand or refund-adjustment notices, AIS/compliance e-campaigns, scrutiny or reassessment notices, or any email from the income-tax department.
---

# Income-tax notice

1. **Get the notice.** Shrey uploads it, or, with permission, you search Gmail for income-tax
   department mail. Check it is genuine: real notices carry a DIN (Document Identification Number)
   and appear under e-Proceedings or Pending Actions on incometax.gov.in. Warn Shrey that anything
   asking them to click a link to pay, or for passwords or OTPs, is phishing.

2. **Identify it,** quoting the section the notice itself cites. Notices from 1 Apr 2026 may cite
   Income-tax Act 2025 section numbers.

   | Type | Typical meaning | Response time |
   |---|---|---|
   | 143(1) intimation | Automated processing: matches, a demand, or a refund | Check it; respond or rectify only on a mismatch |
   | 139(9) defective return | The return is incomplete or inconsistent | 15 days, or the return is treated as invalid |
   | 245 refund adjustment | A proposal to set a refund against an old demand | 30 days to agree or disagree |
   | 156 demand | Tax payable | 30 days |
   | AIS / compliance e-campaign | Income in AIS not matching the return | Respond on the portal, or file a revised or updated return |
   | 143(2) scrutiny, 148/148A reassessment, 270A penalty | Formal proceedings | As stated; **involve a practising CA** |

3. **Compare** the notice with the filed return, Form 16, AIS/TIS and 26AS. Work out whether the
   department is right, partly right, or wrong, and recompute the tax with `tools/income_tax.py`
   where figures are disputed.

4. **Set out the options:** agree and pay, disagree with evidence, file a rectification (154), a
   revised return, or an updated return (ITR-U). Give the cost and risk of each.

5. **Draft the response**: short, factual, referencing the documents to attach. Shrey submits it
   on the portal under e-Proceedings. Never ignore a notice, and never miss its deadline. Offer a
   Calendar reminder for the deadline.

6. **Escalate.** For scrutiny, reassessment, penalty or search matters, or anything with a large
   amount at stake, give your analysis and recommend a practising CA represent Shrey.

7. **Record** the notice in the profile (`tax.open_notices`): type, date, deadline, status. Keep
   the DIN and PAN out of the repo.
