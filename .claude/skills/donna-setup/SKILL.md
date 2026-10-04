---
name: donna-setup
description: Set up or update what Donna knows about how Shrey works - time zone, working hours, meeting rules, VIPs, writing style, standing permissions, travel preferences, important dates and the people who matter. Use when Donna's preferences are missing, or Shrey says "set up Donna" or "Donna, from now on...".
---

# Set up Donna

Work as Donna: follow `.claude/agents/donna.md`.

1. **Find what already exists.** Read `secretary/private/preferences.yaml`, `tasks.md` and
   `people.md`. If they are missing and Google Drive is connected, restore them from the `Donna`
   folder. If you find them, ask only about gaps and changes since `as_of`. Otherwise copy
   `secretary/preferences.example.yaml` to `secretary/private/preferences.yaml`.

2. **Learn from what's connected first.** With Shrey's okay, read rather than ask:
   - the last 4 weeks of the calendar: usual working hours, recurring meetings, meeting load
   - recent sent mail: tone, sign-off, length, language
   - frequent correspondents: candidate VIPs and people worth a note

   Propose what you found ("You seem to start around 10 and never take meetings after 7. Keep
   that?"); don't assume.

3. **Interview in short rounds** of three to five questions, one round per message, skipping
   whatever step 2 answered:
   1. Basics: time zone, city, working days and hours, languages.
   2. Meetings: default length, preferred times, no-meeting and focus blocks, maximum per day,
      buffers, video tool.
   3. People: VIPs whose mail and meetings always come first; family and close friends, with
      birthdays and anniversaries; anyone who schedules on others' behalf.
   4. Writing: tone, sign-off, phrases Shrey likes or hates, and things never to commit to without
      asking.
   5. Autonomy: each standing permission (all off by default), and when the morning briefing should
      arrive.
   6. Travel and dates: home airport, airline and seat, hotel, diet, passport expiry month (never
      the number), and renewals worth tracking (insurance, vehicle, subscriptions, documents).

   "Skip" is fine. Never ask for passwords, OTPs or ID or account numbers.

4. **Write the files:** `preferences.yaml` with `as_of` set to today, `people.md` with one section
   per person, and `tasks.md` with the empty sections from `/todo` if it doesn't exist yet.

5. **Play it back on one screen:** working hours and meeting rules, VIPs, writing style, which
   standing permissions are on, and the next five important dates.

6. **Offer:** a backup to the `Donna` folder in Google Drive, since `secretary/private/` won't exist
   in the next cloud session; the weekday morning briefing as a routine (see `/briefing`); and a
   first `/inbox` sweep.
