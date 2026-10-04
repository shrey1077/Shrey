---
name: todo
description: Donna keeps Shrey's list - captures tasks, commitments and reminders, tracks what others owe Shrey, marks things done, and runs a daily or weekly review. Use for "remind me to", "add to my list", "what's on my plate", "what am I waiting on", "mark X done", or "weekly review".
---

# The list

Work as Donna: follow `.claude/agents/donna.md`. The list lives in `secretary/private/tasks.md`.

## Format

```markdown
# Tasks (as of YYYY-MM-DD)

## Today
## This week
## Later
## Waiting on others
## Someday
## Done

- [ ] Send the Q3 deck to Anil · due 2026-10-09 · from: email "Q3 review", 3 Oct
- [ ] (waiting) Anil: signed NDA · asked 2026-10-01 · chase 2026-10-06
- [x] Renew car insurance · done 2026-10-02
```

Each item starts with a verb, and has a due or chase date when one exists, and where it came from
(email, meeting, Shrey).

## Capturing

- Turn relative dates into real ones and check them: "next Friday" with `python3 tools/when.py
  calendar`, "in three weeks" with `when.py add`.
- File it under the right section by date. Something someone else owes Shrey goes under Waiting on
  others with a chase date (default 3 working days: `when.py add <date> --workdays 3`).
- When a reminder must reach Shrey at a set time, offer an event on Shrey's own calendar with no
  guests. Create it on a yes, or under the `calendar_holds` standing permission.
- Money items (a bill, a premium, an advance-tax instalment) go on the list too. The CA handles the
  substance.

## Reviewing

Show, in this order:

1. **Overdue**, with an offer to do, reschedule or drop each item.
2. **Today** and **this week**.
3. **Waiting** past the chase date, with a short chaser drafted for each (saved as Gmail drafts).
4. **Stale** items untouched for 30 days: schedule them or drop them.

Move items between sections as dates arrive. Move Done items older than 30 days into
`secretary/private/notes/done-YYYY-MM.md`.

## Weekly review

On Friday, or when Shrey asks: what got done, what slipped and why, the three things that matter
most next week, chases to send, and next week's calendar pressure points (from `/briefing week`).

Update `as_of` at the top, and offer a Drive backup after changes.
