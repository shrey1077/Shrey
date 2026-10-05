---
name: briefing
description: Donna's briefing for Shrey - the day's schedule with clashes and prep, emails that need Shrey, tasks due and follow-ups to chase, and dates coming up. Use for "brief me", "what does my day look like", "what's on this week", or at the start of a working day. Pass "week" for the week ahead.
---

# Briefing

Work as Donna: follow `.claude/agents/donna.md`, including its start-of-conversation steps.
Keep it short: Shrey has ADHD, so the top three come first and the rest is skimmable.

1. **Set the window.** Run `python3 tools/when.py now`. The default is today, plus tomorrow morning
   if it is past 5 pm. With "week", cover Monday to Sunday of this week, or of next week from Friday
   afternoon onwards (`when.py calendar` gives the dates).

2. **Calendar.** List the events in the window across Shrey's calendars, in Shrey's zone. Check
   each one for:
   - clashes and double bookings, and back-to-back meetings without the buffer or travel time the
     preferences ask for
   - a missing location or video link, or an invite Shrey hasn't answered
   - anything in a no-meeting block, a focus block, or outside working hours
   - prep: a doc linked in the invite, an unanswered email from an attendee, someone Shrey hasn't
     met (one line on who they are, from mail or `people.md`)

3. **Inbox.** Search mail since the last briefing (default: the last 24 hours, or 7 days for a week
   briefing). Pull out what needs Shrey: VIPs, direct questions, approvals, deadlines, anything
   time-sensitive, likely scams. Skip newsletters and notifications unless one matters today (a
   delivery, a bill due, a flight change). For a large inbox, use `/inbox`'s buckets and keep only
   the 🔴 and 🟡 items here.

4. **Tasks.** From `secretary/private/tasks.md`: overdue items, items due in the window, and
   waiting-on items past their chase date. Add any commitment in Shrey's recent sent mail that is
   missing from the list.

5. **Dates.** Birthdays and anniversaries in the next 7 days (`people.md`); renewals and document
   expiries from `important_dates` in the next 30 days; tax deadlines in the next 30 days from the
   calendar in `finance/knowledge/india-tax-reference.md`.

6. **Write it on one screen:**
   - **Top three:** what most needs Shrey today, each with the action.
   - **Schedule:** a timeline with ⚠️ on problems and a one-line prep note where useful.
   - **Inbox:** needs a reply, needs a decision, FYI; one line each.
   - **Tasks and follow-ups:** due, overdue, chases.
   - **Coming up:** dates and deadlines.

   End with specific offers ("Draft the three replies? Move the 4 pm to Thursday?") and act only
   on a yes.

7. **Deliver and save.** If WhatsApp is enabled, send a three-line version (top three, first
   session, anything urgent) with `tools/whatsapp.py`, keeping out anything sensitive. If the
   briefing changed the plan, refresh `Donna/widget/today.json` (see `/plan-day`). Save the full
   briefing to `secretary/private/notes/YYYY-MM-DD-briefing.md` and update the task list.

8. **Routines.** The morning routine from `/plan-day` includes this briefing; don't set up a second
   one. If neither exists, offer once to create the morning routine.
