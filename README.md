# Andy

Shrey's personal Chartered Accountant and financial advisor, in two parts:

- **The Andy desktop app** ([`andy/`](andy/README.md)): a secure, local-only Windows app. It tracks
  every expense from your bank, card and UPI alert emails, day by day, monthly and yearly. It
  suggests where to cut back, keeps My info and your tax status, and puts Donna's spending requests
  in front of you for the final call. Read [how it's protected](andy/SECURITY.md).
- **The Andy agent** in Claude Code, described below: your CA for tax questions, returns, notices
  and planning.

## The agent

Built for Indian tax and personal finance. Open a Claude Code session on this repository (web, desktop, mobile
or terminal) and talk to it the way you would talk to your CA:

- "Old or new regime for me this year?"
- "I sold some mutual funds in August. How much tax do I owe?"
- "Do I need to pay advance tax on my freelance income?"
- "I got an email about a 143(1) intimation. What does it mean?"
- "Can I afford a ₹1.2 crore flat in 5 years?"
- "Is my LIC endowment policy worth keeping?"

## Commands

| Command | What it does |
|---|---|
| `/onboard` | Builds your financial profile through a short interview, or from your payslip, Form 16, AIS or CAS |
| `/tax-plan` | Old vs new regime, the break-even point, and a tax-saving plan for the rest of the year |
| `/itr` | ITR form choice, document checklist, Form 16 / AIS / 26AS reconciliation, filing walkthrough |
| `/advance-tax` | Instalments due on 15 Jun, 15 Sep, 15 Dec and 15 Mar, plus 234B/234C interest |
| `/health-check` | Scorecard for emergency fund, insurance, debt, savings, allocation, retirement and tax, with an action plan |
| `/goal-plan` | Goals turned into SIPs with asset allocation and a glide path; retirement corpus |
| `/notice` | Explains an income-tax notice, checks it against your return, drafts the reply |

You can also delegate to the `andy` subagent from any other task in this repository.

## How it works

- `CLAUDE.md` is the advisor's operating manual: persona, priorities, ethics, privacy, tools.
- `finance/knowledge/india-tax-reference.md` holds the verified rules (as of 4 Oct 2026): both tax
  regimes, deductions, capital gains, due dates, ITR forms, Budget 2026 changes, and the new
  Income-tax Act 2025 section numbers.
- `tools/` contains calculators written in plain Python 3 with no dependencies. The advisor runs
  them for every figure instead of doing the arithmetic itself:
  - `income_tax.py`: old vs new regime with HRA, house property, deductions, special-rate capital
    gains, the 87A rebate with marginal relief, surcharge with marginal relief, cess, and the
    break-even deductions
  - `capital_gains.py`: short- or long-term classification, grandfathering, indexation choice for
    property
  - `advance_tax.py`: instalment schedule and 234B/234C interest
  - `planner.py`: SIP, lump sum, goal, retirement, EMI with prepayment, emergency fund, term
    cover, FD, real return, CAGR, XIRR
- `tests/` has hand-checked cases for the calculators and the Andy app. Run `python3 -m unittest discover -s tests`.

```sh
python3 tools/income_tax.py --salary 1800000 --basic-da 720000 --hra-received 288000 \
    --rent-paid 300000 --metro --d80c 150000 --d80d-self 25000
python3 tools/planner.py retirement --age 30 --retire-at 55 --monthly-expenses 60000
```

## Your data and privacy

**This repository is public.** Your personal data lives only in `finance/private/`, which git
ignores. A hook (`.claude/hooks/guard_private_data.py`) also blocks any commit that includes that
folder or anything that looks like a PAN or Aadhaar number. The advisor never asks for or stores a
PAN, Aadhaar number, account number or password.

Cloud sessions start from a fresh clone, so `finance/private/` is empty each time. The advisor
offers to back up your profile and reports to a `CA Advisor` folder in your Google Drive and to
restore them at the start of a session. Another option is to make the repository private and
commit your profile.

## Keeping it current

Tax rules change every Budget. The advisor searches the web for anything newer than the
reference's date. When a new Finance Act passes, ask it to add the year to `tools/tax_rules.py`,
update the reference, and add tests.

## Disclaimer

This is an AI assistant, not a practising Chartered Accountant or a SEBI-registered investment
adviser. Use it to understand your situation and prepare. For notices beyond simple intimations,
audits, NRI or foreign-asset matters, and large decisions, have a practising CA review the advice
before you act.
