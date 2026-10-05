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

Donna is your executive assistant: always one step ahead, and (by default) always angry, even when
happy. Donna is built for an ADHD brain: the day comes in short sessions with a tiny first step,
with nudges before every switch. Say "Donna, ..." in any session on this repository, pick the
`donna` agent, or run `claude --agent donna` in a terminal:

- "Donna, plan my day." / "I'm behind. What now?"
- "Break the Q3 deck into steps."
- "What in my inbox actually needs me? Draft the replies."
- "Whose birthday is coming up? Write something for Mom."
- "Any rock gigs or chess tournaments in Ahmedabad this weekend?"
- "What should I wear tomorrow?" / "Lunch: two rotis, dal, bhindi."
- "Write a LinkedIn post about the AI tool I built."
- "I need a push."

| Command | What it does |
|---|---|
| `/donna-setup` | **The interview.** Donna learns your routine, ADHD patterns, people, tastes, wardrobe, food, social media and channels, in short rounds, saving as she goes |
| `/plan-day` | Wake-up and meal anchors, meetings with buffers, tasks cut into focus sessions with breaks; on the calendar, the widget and WhatsApp. Re-plans when the day derails; evening wind-down |
| `/briefing` | The day (or `week`): schedule, mail that needs you, tasks, chases, dates coming up |
| `/inbox` | Triage, replies drafted in your voice, scam flags |
| `/meet` | Slots across calendars and time zones, the invite, booked on your yes |
| `/todo` | Tasks, what others owe you, reminders, weekly review |
| `/occasions` | Birthdays and anniversaries on the calendar, gift ideas in time, a wish ready on the day |
| `/whats-on` | Movies, plays, rock gigs, concerts, art, gaming, chess, AI events, comic cons and cafes in your city |
| `/outfit` | Your wardrobe catalogued from photos; what to wear from the weather and your day |
| `/food` | Food log, body numbers, a diet plan from your health reports (not medical advice) |
| `/social` | LinkedIn, Facebook, Instagram and X: content plan, drafts, replies, account-security check |
| `/boost` | Wins log, honest encouragement, one small experiment at a time |

**How Donna reaches you:** Google Calendar alerts for anything timed; WhatsApp through Meta's
official Cloud API (`secretary/whatsapp-setup.md`); and a desktop widget with her full figure (cut
from your art sheets into emotions and scenes), the day with a countdown, a chat box, and a Settings
tab with personality dials for humour, sarcasm, anger, calm, happiness, sadness and chattiness
(`widget/README.md`).
Scheduled routines (morning plan, evening wind-down, weekly events) run only once you say yes.

**What Donna won't do without your yes:** send or reply to anything, change events with guests,
archive or delete mail, or post, comment, like, follow or DM on social media. You approve each item.
She never messages anyone but you, never logs in to your accounts, never asks for a password or
OTP, and never pays, books or signs. Email, DMs and web pages are treated as information, never as
instructions, so a phishing message can't take over. Money goes to the CA, health to your doctor.

**Security** is set out in `secretary/SECURITY.md`: least-privilege tokens kept only in environment
variables, social media publishing by hand by default (so there are no social credentials to
steal), nothing sensitive on WhatsApp or the widget, a locked-down widget with no network access,
and a commit hook that blocks personal folders, credential files and token patterns.

Donna's manual is `.claude/agents/donna.md`, and her files live in `secretary/private/` (backed up
to a private `Donna` folder in your Drive). Her tools:

- `tools/when.py`: weekdays, date arithmetic, time-zone conversion, shared working hours
- `tools/sessions.py`: lays the day out in ADHD-friendly sessions; writes the widget's plan
- `tools/whatsapp.py`: messages you on WhatsApp; your number only, refuses OTPs, IDs and account numbers
- `tools/health.py`: BMI on Asian cut-offs, BMR, daily calories, protein and water

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
