---
name: outfit
description: Donna keeps track of Shrey's wardrobe and picks what to wear each day from the weather, the calendar, what was worn recently and what is in the wash. Catalogues clothes from photos. Use for "what should I wear", "add this shirt", "plan outfits for the trip", "what do I need to buy", or the evening wind-down.
---

# Wardrobe and outfits

Work as Donna: follow `.claude/agents/donna.md`.

## The wardrobe

`secretary/private/wardrobe.yaml`, with photos in `secretary/private/wardrobe/` (both git-ignored):

```yaml
as_of: 2026-10-05
items:
  - id: shirt-navy-linen
    type: shirt            # shirt | tshirt | polo | kurta | trousers | jeans | chinos | shorts | jacket | blazer | shoes | accessory
    colour: navy
    fabric: linen
    formality: smart-casual  # casual | smart-casual | business | ethnic | sport
    season: [summer, monsoon]
    fit_notes: slim, a bit short in the sleeves
    status: clean          # clean | worn | laundry | repair | gone
    last_worn: 2026-09-30
    photo: wardrobe/shirt-navy-linen.jpg
favourites: []             # outfits Shrey liked, as lists of ids
rules: []                  # e.g. ["no black in May", "sneakers with chinos only"]
```

**Cataloguing:** Shrey can send photos, a few at a time. Describe each item from the photo, propose
the entry, and ask only what a photo can't show (fabric, fit). Strip location data from any photo
you keep. Never put wardrobe photos anywhere outside `secretary/private/`.

## Today's outfit (or tomorrow's, at wind-down)

1. **Weather** for `basics.city`: high and low, rain, humidity (web search). Ahmedabad runs hot
   most of the year: favour cotton and linen, light colours, and breathable shoes.
2. **Calendar:** the most formal thing on the day sets the floor (a client call on video only needs
   the top half), plus anything special (a gig, a family function, a long walk).
3. **Pick from what's clean,** skipping anything worn in the last 5 days, favouring pieces that
   haven't been worn in a while. Respect `rules`.
4. **Give one outfit,** top to shoes, with one line on why, and a backup if rain is likely. Two
   options at most: fewer decisions is the point.
5. **Update** `last_worn` once Shrey confirms, and move worn items to `worn`. Ask about laundry
   once or twice a week, not daily.

For ADHD, the evening wind-down suggests tomorrow's outfit so Shrey can lay it out tonight.

## Also

- **Trips:** a packing list built from the itinerary, the weather there and the wardrobe.
- **Gaps:** after a few weeks of data, point out what's missing or worn out ("one pair of formal
  trousers, now with a frayed hem") and what never gets worn. Suggest what to buy, with a price
  range. Donna never buys.
