# India tax and personal-finance reference

**Verified as of 4 October 2026.** Anything that may have changed since (a new Finance Act, CBDT
circulars, due-date extensions, small-savings rates, ITR form changes) must be checked with a web
search before you rely on it. The calculators in `tools/` encode the same figures in
`tools/tax_rules.py`.

## Which law applies

| Income earned | Law | Vocabulary |
|---|---|---|
| Up to 31 Mar 2026 (FY 2025-26 and earlier) | Income-tax Act, 1961 | "previous year" / "assessment year" (AY 2026-27), old section numbers |
| From 1 Apr 2026 | Income-tax Act, 2025 | "tax year" (tax year 2026-27 = 1 Apr 2026 to 31 Mar 2027), new section numbers |

Returns for FY 2025-26, filed in 2026, still use the 1961 Act. The 2025 Act mostly renumbers and
reorganises; it changed few benefits.

Section mapping (1961 → 2025). Quote both while people still use the old numbers:

| Old | New | What |
|---|---|---|
| 16(ia) | 19 | Standard deduction |
| 80C (with 80CCC and part of 80CCD) | 123 | ₹1.5 lakh deduction; eligible items listed in Schedule XV |
| 80CCD(1B), 80CCD(2) | 124 | NPS |
| 80D | 126 | Health insurance |
| 87A | 156 | Rebate |
| 115BAC | 202 | New regime |
| 111A | 196 | STCG on listed equity |
| 112A | 198 | LTCG on listed equity |
| 234A / 234B / 234C | 423 / 424 / 425 | Interest for late filing and advance-tax shortfalls |

Secondary sources disagree on 24(b) (home-loan interest; reported as section 20 or 22). Look up any
section not listed here before quoting it.

## Slabs: FY 2025-26 and tax year 2026-27

Budget 2026 changed none of these.

**New regime (default)**

| Income | Rate |
|---|---|
| up to ₹4 lakh | nil |
| ₹4–8 lakh | 5% |
| ₹8–12 lakh | 10% |
| ₹12–16 lakh | 15% |
| ₹16–20 lakh | 20% |
| ₹20–24 lakh | 25% |
| above ₹24 lakh | 30% |

- Standard deduction ₹75,000, so a salary up to ₹12.75 lakh pays no tax.
- Rebate (87A / 156): up to ₹60,000 when total income is ₹12 lakh or less, with marginal relief just
  above that. **It does not cover tax on special-rate income** (111A, 112, 112A gains). Total income
  for the ₹12 lakh test includes those gains.
- Surcharge: 10% above ₹50 lakh, 15% above ₹1 crore, 25% above ₹2 crore (capped at 25%).

**Old regime**

| Income | Below 60 | 60–79 | 80+ |
|---|---|---|---|
| nil up to | ₹2.5 lakh | ₹3 lakh | ₹5 lakh |
| 5% | to ₹5 lakh | to ₹5 lakh | n/a |
| 20% | ₹5–10 lakh | ₹5–10 lakh | ₹5–10 lakh |
| 30% | above ₹10 lakh | above ₹10 lakh | above ₹10 lakh |

- Standard deduction ₹50,000. Rebate up to ₹12,500 when total income is ₹5 lakh or less (not
  against 112A tax).
- Surcharge: 10% / 15% / 25% / 37% above ₹50 lakh / ₹1 crore / ₹2 crore / ₹5 crore.

**Both regimes:** 4% health and education cess on tax plus surcharge. Surcharge on dividends and
on capital gains under 111A, 112 and 112A is capped at 15%. Marginal relief applies at each
surcharge threshold.

**Choosing a regime:** salaried people with no business income can pick either regime every year
when they file. With business or professional income you opt out of the new regime with Form 10-IEA
by the due date, and you can switch back only once.

## What each regime allows

New regime: standard deduction ₹75,000; employer NPS contribution (80CCD(2)) up to 14% of basic +
DA; family pension deduction (one third, up to ₹25,000); Agniveer corpus (80CCH); interest on a
let-out property's loan against that property's rent only (no loss set-off against other income);
exemptions on retirement benefits such as gratuity and leave encashment.

Old regime only:

| Item | Limit |
|---|---|
| 80C: EPF/VPF, PPF, ELSS, life insurance, home-loan principal, tuition fees, 5-year FD, NSC, SSY | ₹1.5 lakh |
| 80CCD(1B): own NPS contribution, on top of 80C | ₹50,000 |
| 80CCD(2): employer NPS | 10% of basic + DA |
| 80D: health insurance for self, spouse, children | ₹25,000 (₹50,000 if 60+) |
| 80D: parents, on top (a ₹5,000 preventive check-up counts within these limits) | ₹25,000 (₹50,000 if they are 60+) |
| 24(b): interest on a self-occupied home loan; total house-property loss set-off is also capped at ₹2 lakh, with the rest carried forward 8 years | ₹2 lakh |
| HRA (10(13A)): least of HRA received, rent − 10% of basic+DA, 50% (metro) / 40% of basic+DA | formula |
| 80GG: rent paid without HRA | ₹60,000/year |
| LTA: two journeys in a block (current block: 2026–2029) | actual fare |
| 80E: education-loan interest, 8 years | no cap |
| 80G: donations | 50%/100%, some capped at 10% of income |
| 80TTA: savings interest (below 60) | ₹10,000 |
| 80TTB: all deposit interest (60+) | ₹50,000 |
| Professional tax | ₹2,500 |

HRA metro cities: Delhi, Mumbai, Kolkata, Chennai. The Income-tax Rules 2026 add Bengaluru,
Hyderabad, Pune and Ahmedabad from FY 2026-27. Confirm the final notified list before relying on it.

## Capital gains (transfers on or after 23 July 2024)

| Asset | Long-term after | Short-term rate | Long-term rate |
|---|---|---|---|
| Listed equity, equity MFs/ETFs, REIT/InvIT units (STT paid) | 12 months | 20% (111A) | 12.5% above ₹1.25 lakh a year (112A) |
| Other listed securities: listed bonds, gold ETFs | 12 months | slab | 12.5% (112) |
| Debt MFs bought on or after 1 Apr 2023, market-linked debentures, unlisted bonds | never | slab (50AA) | n/a |
| Land/building, physical gold, unlisted and foreign shares, debt MFs bought before 1 Apr 2023, gold and international FoFs | 24 months | slab | 12.5%, no indexation (112) |

- Land or building a resident individual bought before 23 Jul 2024: pay the lower of 12.5% without
  indexation or 20% with indexation. A loss under the indexed method can't be claimed.
- Equity bought before 1 Feb 2018: grandfathered cost is the higher of actual cost and
  min(31 Jan 2018 value, sale value).
- Cost Inflation Index: 2001-02 = 100 … 2024-25 = 363, 2025-26 = 376, 2026-27 = 384.
- Exemptions: 54 (sell a house, buy a house), 54F (sell another asset, put the full proceeds into a
  house), 54EC bonds (up to ₹50 lakh within 6 months). The 54/54F exemption is capped at ₹10 crore.
- Losses: short-term losses offset any capital gain; long-term losses offset only long-term gains.
  Unused losses carry forward 8 years, **only if the return is filed by the due date**.
- Tax harvesting: book up to ₹1.25 lakh of equity LTCG each year tax-free and reinvest; book losses
  before 31 March to offset gains.

**Changes from 1 April 2026 (Budget 2026):**
- Share buybacks are taxed as capital gains for the shareholder, not as dividends (promoters pay a
  higher effective rate).
- Sovereign Gold Bonds: the exemption at redemption applies only to original subscribers who hold
  until maturity. Bonds bought on the exchange are taxed on redemption.
- STT: futures 0.05% (was 0.02%); options premium and exercise 0.15%.

Also: F&O trading is non-speculative business income and needs ITR-3. Intraday equity is speculative
business income. Crypto and other virtual digital assets are taxed at a flat 30% (115BBH) with no
loss set-off, plus 1% TDS (194S).

## Calendar

**Tax year 2026-27 (FY 2026-27)**

| When | What |
|---|---|
| April | Tell the employer your regime; submit Form 15G/15H to banks if eligible |
| 15 Jun 2026 | Advance tax 15% |
| 15 Sep 2026 | Advance tax 45% |
| 15 Dec 2026 | Advance tax 75% |
| Jan–Feb 2027 | Investment proofs to the employer |
| 15 Mar 2027 | Advance tax 100% (presumptive 44AD/44ADA: everything is due now) |
| 31 Mar 2027 | Last day for old-regime tax-saving investments, PPF/SSY minimum deposits, and booking gains or losses |
| by 15 Jun 2027 | Form 16 from the employer |
| 31 Jul 2027 | ITR-1 / ITR-2 due |
| 31 Aug 2027 | ITR-3 / ITR-4 without audit due (new from Budget 2026) |
| 31 Oct 2027 | Audit cases |

Advance tax isn't needed if tax after TDS is under ₹10,000, or for resident seniors (60+) with no
business income. A shortfall attracts 234C interest (1% a month), plus 234B interest if less than
90% is paid by 31 March.

**FY 2025-26 returns (filing now):** the due dates were 31 Jul 2026 (ITR-1/2) and 31 Aug 2026
(non-audit ITR-3/4). Audit cases are due 31 Oct 2026. If the return is not filed yet, a **belated
return** is due by 31 Dec 2026 with a 234F late fee of ₹5,000 (₹1,000 if income ≤ ₹5 lakh), 234A
interest, and loss of carry-forward for most losses.
- Revised return: Budget 2026 moved the window from 31 Dec to 31 Mar after the year, with a fee for
  later revisions. Confirm which year it first applies to before advising.
- Updated return (ITR-U): up to 48 months after the end of the assessment year, with an additional
  25–70% of the tax and interest.
- E-verify within 30 days of filing, or the return is treated as not filed.

## ITR form selection (individuals)

| Form | Who |
|---|---|
| ITR-1 Sahaj | Resident, total income ≤ ₹50 lakh: salary, one house property, other sources, 112A LTCG ≤ ₹1.25 lakh, agricultural income ≤ ₹5,000. Not for directors, holders of unlisted shares or foreign assets, or anyone with brought-forward losses |
| ITR-2 | No business income, but capital gains, more than one house, foreign assets or income, director, income > ₹50 lakh, or NRI |
| ITR-3 | Business or professional income, including F&O, intraday and partners' remuneration |
| ITR-4 Sugam | Resident on presumptive income (44AD/44ADA/44AE), total income ≤ ₹50 lakh, 112A LTCG ≤ ₹1.25 lakh |

Before filing, reconcile Form 16, **AIS/TIS** and **Form 26AS**: salary, TDS, interest from every bank,
dividends, securities and MF transactions, and rent. Mismatches trigger automated notices.

## Compliance red flags

- Reported to the department (SFT): cash deposits ≥ ₹10 lakh a year in savings accounts; credit-card
  payments ≥ ₹1 lakh in cash or ≥ ₹10 lakh in total; MF, share or bond purchases ≥ ₹10 lakh; FDs
  ≥ ₹10 lakh; property deals ≥ ₹30 lakh. The return must match.
- Cash: accepting ₹2 lakh or more in cash from one person in a day or for one transaction (269ST) brings
  a penalty equal to the amount. Loans or deposits of ₹20,000 or more must not be in cash (269SS/269T).
- Gifts from non-relatives above ₹50,000 a year are taxable. Gifts from relatives are exempt. Clubbing
  rules apply to gifts to a spouse or minor child.
- Foreign assets, including RSUs/ESOPs of a foreign employer and foreign accounts, must go in
  Schedule FA. Non-disclosure carries heavy Black Money Act penalties. Budget 2026 introduced
  FAST-DS 2026, a time-bound disclosure scheme for small foreign assets.
- TCS on LRS remittances (from 1 Apr 2026): 2% for education and medical above ₹10 lakh and on overseas
  tour packages. TCS is credited against your tax.

## Personal-finance rules of thumb

- Order: emergency fund (6 months of expenses plus EMIs; more if income is variable or single) →
  term insurance (≈10–15× income or need-based) and health insurance (≥ ₹10 lakh family floater in a
  metro, plus a super top-up) → clear high-interest debt (credit cards, personal loans) → goal-based
  investing → optimisation.
- EMIs ≤ 40% of take-home pay. Savings rate ≥ 20–30%.
- Asset allocation by goal horizon: under 3 years liquid or debt; 3–5 years hybrid; over 5–7 years
  mostly equity, moving to debt 2–3 years before the goal.
- Prefer low-cost direct plans and index funds. Be sceptical of endowment, money-back and ULIP
  policies (typical IRR 4–6%). Maturity proceeds are taxable when premiums exceed ₹5 lakh a year
  (₹2.5 lakh for ULIPs).
- EPF interest on employee contributions above ₹2.5 lakh a year is taxable.
- Small-savings rates (PPF, SSY, SCSS, NSC) are reset every quarter. Look up the current quarter
  before quoting a rate. NPS withdrawal rules have been changing too, so check them.
- Keep nominations current everywhere (bank, demat, MF, EPF, insurance) and make a will.

## Sources

- [ClearTax: income tax slabs FY 2025-26 and FY 2026-27](https://cleartax.in/s/income-tax-slabs)
- [Business Today: what Budget 2026 changed for individual taxpayers](https://www.businesstoday.in/personal-finance/tax/story/tax-slabs-fy-2026-27-what-budget-2026-changed-for-individual-taxpayers-and-which-regime-works-best-514044-2026-02-01)
- [Upstox: 10 income-tax announcements in Budget 2026](https://upstox.com/news/personal-finance/tax/top-10-income-tax-announcements-in-budget-2026-from-tcs-on-lrs-stt-buyback-shares-to-revised-itr-filing-date/article-188714/)
- [Business Today: section 80C becomes section 123](https://www.businesstoday.in/personal-finance/tax/story/income-tax-act-2025-section-80c-becomes-section-123-from-april-1-2026-heres-what-taxpayers-must-know-522120-2026-03-24)
- [ClearTax: Income Tax Act 2025 section mapping](https://cleartax.in/s/income-tax-act-2025-section-numbers-old-vs-new)
- [TaxGuru: section 87A and section 156 rebate](https://taxguru.in/income-tax/section-87a-section-156-rebate-tax-payable-rs-12-lakh.html)
- [Business Standard: CII for FY 2026-27 notified at 384](https://www.business-standard.com/finance/news/cbdt-cost-inflation-index-fy27-384-capital-gains-tax-126071600429_1.html)
- [CAalley: Budget 2026 changes SGB tax rules](https://www.caalley.com/news-updates/budget-2026/budget-2026-changes-sgb-tax-rules-ends-blanket-capital-gains-exemption)
- [TaxGuru: ITR due dates FY 2025-26](https://taxguru.in/income-tax/itr-filing-due-dates-fy-2025-26-ay-2026-27.html)
- [Angel One: draft Income-tax Rules 2026, HRA cities](https://www.angelone.in/news/taxation/draft-income-tax-rules-2026-bengaluru-pune-hyderabad-ahmedabad-set-to-get-50-hra-rebate-in-new-rules)
