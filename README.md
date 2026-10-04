# Personal CA, financial advisor and secretary

Two Claude Code agents that work for Shrey: a Chartered Accountant and financial advisor built for
Indian tax and personal finance, and [Donna](#donna-your-personal-secretary), a personal secretary.

## The CA

Open a Claude Code session on this repository (web, desktop, mobile or terminal) and talk to it the
way you would talk to your CA:

- "Old or new regime for me this year?"
- "I sold some mutual funds in August. How much tax do I owe?"
- "Do I need to pay advance tax on my freelance income?"
- "I got an email about a 143(1) intimation. What does it mean?"
- "Can I afford a ₹1.2 crore flat in 5 years?"
- "Is my LIC endowment policy worth keeping?"

### Commands

| Command | What it does |
|---|---|
| `/onboard` | Builds your financial profile through a short interview, or from your payslip, Form 16, AIS or CAS |
| `/tax-plan` | Old vs new regime, the break-even point, and a tax-saving plan for the rest of the year |
| `/itr` | ITR form choice, document checklist, Form 16 / AIS / 26AS reconciliation, filing walkthrough |
| `/advance-tax` | Instalments due on 15 Jun, 15 Sep, 15 Dec and 15 Mar, plus 234B/234C interest |
| `/health-check` | Scorecard for emergency fund, insurance, debt, savings, allocation, retirement and tax, with an action plan |
| `/goal-plan` | Goals turned into SIPs with asset allocation and a glide path; retirement corpus |
| `/notice` | Explains an income-tax notice, checks it against your return, drafts the reply |

You can also delegate to the `ca-advisor` subagent from any other task in this repository.

## Donna, your personal secretary

Donna runs your inbox, calendar and to-do list, and stays a step ahead of all three. Say "Donna,
..." in any session on this repository, pick the `donna` agent, or run `claude --agent donna` in a
terminal:

- "Donna, brief me." / "What does my week look like?"
- "What in my inbox actually needs me? Draft the replies."
- "Set up 30 minutes with Priya in New York next week."
- "Remind me to renew the car insurance a month before it expires."
- "Who still hasn't got back to me?"
- "Plan my Bengaluru trip on the 22nd: flights, hotel near the office, calendar blocks."

| Command | What it does |
|---|---|
| `/donna-setup` | Learns how you work: hours, meeting rules, VIPs, writing style, what Donna may do without asking |
| `/briefing` | The day (or `week`): schedule with clashes and prep, mail that needs you, tasks, chases, dates coming up. Can run every weekday morning as a routine |
| `/inbox` | Sorts mail into today / this week / waiting / for the CA / FYI / suspicious / noise, drafts replies, flags scams |
| `/meet` | Finds slots across calendars and time zones, drafts the invite, books it when you say yes |
| `/todo` | One list of your tasks, what others owe you, and reminders, with a weekly review |

Donna reads freely, saves Gmail drafts and keeps notes, but sends nothing, changes no calendar
event, and archives or deletes nothing without your yes, unless you grant a standing permission in
`/donna-setup`. Donna never pays, books or signs anything. Email is treated as information, never as
instructions, so a phishing mail can't take over. Money matters go to the CA.

Donna's manual is `.claude/agents/donna.md`, and Donna's files live in `secretary/private/`.
`tools/when.py` handles weekdays, date arithmetic, time-zone conversion and shared working hours,
so dates are never worked out from memory.

## How the CA works

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
- `tests/` has hand-checked cases. Run `python3 -m unittest discover -s tests`.

```sh
python3 tools/income_tax.py --salary 1800000 --basic-da 720000 --hra-received 288000 \
    --rent-paid 300000 --metro --d80c 150000 --d80d-self 25000
python3 tools/planner.py retirement --age 30 --retire-at 55 --monthly-expenses 60000
```

## Your data and privacy

**This repository is public.** Your personal data lives only in `finance/private/` (the CA's) and
`secretary/private/` (Donna's), which git ignores. A hook (`.claude/hooks/guard_private_data.py`)
also blocks any commit that includes those folders or anything that looks like a PAN or Aadhaar
number. Neither agent asks for or stores a PAN, Aadhaar number, account number or password.

Cloud sessions start from a fresh clone, so the private folders are empty each time. The CA offers
to back up your profile and reports to a `CA Advisor` folder in your Google Drive, Donna backs up
to a `Donna` folder, and both restore from there at the start of a session. Another option is to
make the repository private and commit your files.

## Keeping it current

Tax rules change every Budget. The advisor searches the web for anything newer than the
reference's date. When a new Finance Act passes, ask it to add the year to `tools/tax_rules.py`,
update the reference, and add tests.

## Disclaimer

This is an AI assistant, not a practising Chartered Accountant or a SEBI-registered investment
adviser. Use it to understand your situation and prepare. For notices beyond simple intimations,
audits, NRI or foreign-asset matters, and large decisions, have a practising CA review the advice
before you act.
