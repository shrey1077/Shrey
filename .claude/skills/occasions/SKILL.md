---
name: occasions
description: Donna makes sure Shrey never misses a birthday, anniversary or important day for family and close friends - keeps the dates, puts them on the calendar with reminders, suggests gifts in time, and has a personal wish ready to send on the day in the right language. Use for "remind me of birthdays", "whose birthday is coming up", "add Mom's birthday", "what should I write to X", or "gift ideas for Y".
---

# Birthdays and occasions

Work as Donna: follow `.claude/agents/donna.md`. Wishes go out in Shrey's voice, never Donna's
temper.

## Keeping the dates

Each person in `secretary/private/people.md` can carry:

```markdown
## Mom
- Relationship: mother · circle: family (family | close | friend | work)
- Birthday: 03-14 · Anniversary (with Dad): 11-22
- Language for wishes: Gujarati · Prefers: a call before 9 am
- Likes: gardening, old Hindi songs · Gift ideas: [running list]
- Last wished: 2026-03-14 (called)
```

Store birthdays as MM-DD, with the year only if Shrey wants ages mentioned. Other occasions
(Diwali, Raksha Bandhan, a friend's wedding, a work anniversary, a parent's surgery date) go under
`important_dates` in the preferences or under the person.

## Putting them on the calendar

For each occasion, offer (or with `calendar_holds`, just create) a yearly all-day event on Shrey's
own calendar, no guests, titled like "🎂 Mom's birthday", with alerts that depend on the circle:

| Circle | Reminders |
|---|---|
| family, close | 7 days before (gift or plan), 1 day before (evening), 8 am on the day |
| friend | 1 day before, 9 am on the day |
| work | 9 am on the day |

Festival dates move each year: check the date with a web search before adding it.

## Seven days before (family and close)

Suggest one gift that fits the person (from their notes), with a price and where to get it in time,
or an experience (a cafe, a show from `/whats-on`). Add "get Mom's gift" to the list with a date.
Donna never buys.

## On the day

1. Morning briefing, widget and WhatsApp (if enabled): who, and the action ("Call Mom before 9").
2. A wish ready to copy, written for that person: their language, the relationship, a specific
   memory or detail from their notes, no generic quotes. Offer a short and a longer version. For a
   call, three talking points.
3. Shrey sends it. Donna never messages anyone but Shrey.
4. Afterwards, update "Last wished" and note anything new Shrey learned (new job, new baby).

## Looking ahead

On request, or in the Sunday weekly review: the next 30 days of occasions, with what is already
done (gift bought, plan made) and what isn't.
