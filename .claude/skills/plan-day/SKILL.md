---
name: plan-day
description: Donna plans Shrey's day for an ADHD brain - wake-up and meal anchors, meetings with buffers, and tasks broken into short focus sessions with breaks and a tiny first step each - then puts it on the calendar, the widget and WhatsApp. Also re-plans when the day derails and does the evening wind-down. Use for "plan my day", "break this down", "I'm behind", "what now", "plan tomorrow", or the morning and evening routines.
---

# Plan the day

Work as Donna: follow `.claude/agents/donna.md`, especially "ADHD first".

## Morning plan (or "plan tomorrow" the evening before)

1. **Gather.** `python3 tools/when.py now`. Read the calendar for the day, `tasks.md` (overdue,
   today, this week), `routine` and `adhd` in the preferences, the widget log from yesterday (what
   actually got done, and when Shrey tends to stall), and the weather if it affects the plan.

2. **Choose at most three priorities.** Pick what matters most and is due soonest. Everything else
   is optional today. For each, estimate minutes honestly (ADHD estimates run short: add 50%), set
   `energy` (high for deep thinking, low for admin), and write a first step small enough to start
   in under two minutes.

3. **Build the input** at `secretary/private/plan-input.json` (see
   `python3 tools/sessions.py --example`): anchors from `routine` (wake, breakfast, lunch, dinner,
   wind-down, plus medication reminders if Shrey set any), fixed events from the calendar
   (`kind: meeting` for calls and meetings so they get a buffer), tasks, and `settings` from `adhd`.
   Give personal tasks their own window (chess, a gig) so work never leaks into the evening.

4. **Run it:** `python3 tools/sessions.py secretary/private/plan-input.json`. Check the result:
   - Clashes: fix or ask.
   - Anything under "Didn't fit": move it to tomorrow on the list, or ask whether to drop it.
     Never cram it in.
   - A day with more than about five hours of focus, or no real break before 2 pm, is too full.

5. **Show Shrey the plan** in one screen: the three priorities, then the timeline with icons, then
   what moved to tomorrow. Ask one question at most ("Deck first or emails first?").

6. **Make it real** once Shrey agrees (or straight away with the `calendar_holds` permission):
   - Calendar: one event per anchor and focus session on Shrey's own calendar, no guests, with alerts
     at `calendar_alerts_minutes`. Put the first step in the description. Breaks need no event.
   - Widget: `python3 tools/sessions.py secretary/private/plan-input.json --widget`, then add
     `temperament` (from `persona`), `mood`, a one-line `message` in that temperament, `outfit`
     (from `/outfit`), today's `occasions`, tonight's `events`, and yesterday's `wins`. Replace `Donna/widget/today.json` in Drive: move
     the old one to the bin, then create the new one as plain JSON (no conversion to a Google Doc).
   - WhatsApp (if enabled): one short message with the three priorities and the first session's
     time and first step.

## Wake-up and meals

- A calendar alert won't wake a sleeping person. Make sure Shrey has a phone alarm at
  `routine.wake`; the "Wake up" anchor and your morning WhatsApp follow it.
- Breakfast, lunch and dinner are anchors with alerts, every day. If the widget log shows a meal
  skipped, say so plainly at the next check-in, without a lecture.

## When the day derails ("I'm behind", "what now", a skipped session)

1. No post-mortem. Ask nothing about why.
2. Re-run the planner from now: set `day_start` to the current time, drop or shrink what can't fit,
   keep meals and wind-down.
3. Give Shrey exactly one next step and its time. Update the calendar, widget and list.

## Breaking down a big task ("break this down")

Split it into steps of 15 to 45 minutes, each with a visible result ("outline with five headings",
not "research"). The first step must be laughably small. Put the steps on the list with the task's
due date, and schedule only the next one or two.

## Evening wind-down

At `routine.wind_down`: what got done today (from the log and calendar; one line of honest
praise), what moved to tomorrow, tomorrow's first thing and its first step, tomorrow's outfit to lay
out now (`/outfit`), and screens off. Save the day to `secretary/private/notes/YYYY-MM-DD-day.md`,
add wins to `wins.md`, and back up to Drive.

## Routines

If `routines.morning_plan.id` or `routines.evening_wind_down.id` is empty, offer once to run these
automatically. On a yes, create a recurring routine for each (a scheduled trigger that starts a fresh
session) whose prompt runs `/plan-day` then `/briefing` (morning) or `/plan-day wind-down`
(evening), with only the Google Calendar, Gmail and Google Drive connectors, and record the IDs.
Remind Shrey that these runs work from the files backed up in Drive, so backups matter.
