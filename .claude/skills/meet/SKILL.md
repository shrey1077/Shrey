---
name: meet
description: Donna finds a time and sets up a meeting or call for Shrey - checks calendars, working hours and time zones, proposes slots, drafts the invite or the email offering times, and books it once Shrey approves. Also reschedules and cancels. Use for "set up a call with X", "find time for", "move my 3 pm", or "when can I meet Y".
---

# Set up a meeting

Work as Donna: follow `.claude/agents/donna.md`.

1. **Get the facts.** Ask only for what's missing: who, what it's for, how long (default
   `meetings.default_minutes`), by when, and whether it's in person, video or phone. Look up each
   attendee's email and time zone in `people.md` and recent mail.

2. **Find slots.**
   - Shrey's free time from Google Calendar, within working hours and the meeting rules in the
     preferences: preferred times, no-meeting and focus blocks, `max_per_day`, buffers, and travel
     time either side of an in-person meeting.
   - Attendees' free time, where their calendars are visible.
   - Across zones: `python3 tools/when.py overlap <date> --zones <Shrey's zone> <their zone>`. Give a
     zone its own hours when someone is flexible (`IST=8-21`). Check each proposed slot with
     `when.py convert`.
   - Pick three slots, best first, spread over different days, each shown in every attendee's zone.

3. **Draft it.**
   - **The invite:** title, date and time with the zone, duration, attendees, location or video
     link, and a two-line agenda. Add a video link only if the calendar tool can create one;
     otherwise say Shrey needs to add it.
   - **An email offering times** instead, when attendees are external or their calendars aren't
     visible.

4. **Confirm, then act.** Show Shrey the draft. On a yes, create the event or send the email.
   Never decline or move a VIP's meeting without asking.

5. **Close the loop.** Add the prep to the task list (a doc to read, an agenda to send). If you
   offered times by email, add "waiting on <name> to pick a time" with a chase date.

**Rescheduling or cancelling:** find the event, propose new slots as above, draft a short note to
the attendees, and change nothing until Shrey says yes.
