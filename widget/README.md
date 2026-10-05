# Donna's desktop widget

A small always-on-top card in Donna's style: her face (the expression changes with what's
happening), what you should be doing now with a countdown, the first step, what's next, today's
timeline, what to wear, birthdays, tonight's plans, and a box to tell Donna something. It nudges
you before each session and at the start of meals and breaks.

It works on Windows, macOS and Linux.

## How it gets the plan

Donna writes the day's plan to `Donna/widget/today.json` in your Google Drive. Google Drive for
desktop syncs that folder to your computer, and the widget reads it from there. Done, snooze and
skip go to `log.jsonl`, and what you type in "Tell Donna…" goes to `inbox.jsonl`, in the same
folder. Donna reads both next time she runs.

## Set it up

1. Install [Node.js](https://nodejs.org) (the LTS version) and
   [Google Drive for desktop](https://www.google.com/drive/download/). Sign in to Drive with the
   account Donna uses.
2. Get this repository onto your computer, then:

   ```sh
   cd widget
   npm install
   npm run demo      # a sample day, to see it working
   npm start         # the real thing
   ```

3. In the widget, open settings (⚙):
   - **Plan folder:** choose `Donna/widget` inside your synced Google Drive folder. It's usually
     `G:\My Drive\Donna\widget` on Windows, or under `~/Library/CloudStorage/GoogleDrive-…/My Drive/`
     on a Mac. Ask Donna to plan your day once if the folder doesn't exist yet.
   - **Character sheet:** choose your sheet image (PNG, JPEG or WebP). It stays on your machine;
     `widget/assets/` is a good place for it.
   - **Donna:** Angry or Classic, to match the sheet you chose.
   - **Start at login** if you want her there every morning (Windows and macOS; on Linux, add
     `npm start` in this folder to your desktop's startup applications).

Click her face to switch between the full card and a slim bar. **Ctrl+Shift+D**
(**Cmd+Shift+D** on a Mac) is discreet mode for screen sharing: faces and times only, and
notifications say only "Something needs you."

## Security

The widget is locked down because it sits on your screen all day:

- No network access at all. Only local files load; every other request is blocked.
- The page can't touch your computer. Context isolation and the sandbox are on and Node is off; the
  page can only ask for a short list of actions (read the plan, append to the two log files,
  pick a folder or image, change a setting).
- It reads one folder and one image, and writes only `inbox.jsonl` and `log.jsonl`.
- `today.json` is checked before it's shown (`feed.js`): known fields only, bounded lengths, shown
  as text, never HTML. A tampered file can't run code.
- A strict content security policy, no pop-ups, no navigation, no permissions (camera, microphone,
  location).
- No passwords, tokens or account data, ever. Donna keeps health and money details out of the
  plan she writes for it.
- Settings are kept in your user profile, not in the repository.

## Files

| File | What it is |
|---|---|
| `main.js` | The app: window, notifications, reading the plan, the lockdown |
| `preload.js` | The short list of actions the page may ask for |
| `feed.js` | Checks `today.json` |
| `renderer/` | The card: `index.html`, `styles.css`, `app.js`, and `faces.js`, which finds the expressions on your sheet |
| `sample/today.json` | The demo day; also shows the format Donna writes |
| `test/` | `npm test` |

## The plan format

`today.json` is what `python3 tools/sessions.py <input> --widget` produces, plus Donna's additions:

```json
{
  "version": 1,
  "date": "2026-10-05",
  "mood": "neutral",
  "message": "Three things today. Not four. Three.",
  "blocks": [{"id": "b5", "start": "10:00", "end": "10:45", "kind": "focus",
              "title": "Draft the Q3 deck (1/3)", "first_step": "Open the deck and write three slide titles"}],
  "outfit": {"summary": "Navy linen shirt, beige chinos, white sneakers"},
  "occasions": [{"who": "Mom", "what": "birthday", "action": "call before 9 pm"}],
  "events": [{"title": "Indie rock night", "when": "Sat 8 pm"}],
  "wins": ["Cleared all three email drafts before 10 yesterday"],
  "reminders": [{"at": "16:00", "text": "Water. And stand up for a minute."}]
}
```

Block kinds: `anchor`, `meal`, `meeting`, `event`, `buffer`, `reset`, `focus`, `break`. Moods:
`neutral`, `amused`, `serious`, `thoughtful`, `suspicious`, `surprised`, `happy`, `intimidating`.
