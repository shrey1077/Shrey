# Donna's desktop widget

Donna on your desktop: her full figure on the left, changing with the moment (at her desk while you
focus, on a call during meetings, arms crossed when you're late, laughing when you finish the day),
with a close-up of her face beside it. On the right: her line in a speech bubble, what to do now
with a countdown and the first step, what's next, today's timeline, what to wear and tonight's
plans, and a chat box. A Settings tab tunes her personality.

It runs on Windows, macOS and Linux.

## Set it up

1. Install [Node.js](https://nodejs.org) (LTS) and
   [Google Drive for desktop](https://www.google.com/drive/download/), signed in to the account
   Donna uses.
2. In this repository:

   ```sh
   cd widget
   npm install
   npm run demo      # a sample day
   npm start         # the real thing
   ```

3. **Settings → Plan and desktop → Plan folder:** choose `Donna/widget` in your synced Drive
   (`G:\My Drive\Donna\widget` on most Windows machines). Ask Donna to plan your day once if the
   folder doesn't exist yet.
4. **Settings → Look → Pictures folder:** choose the folder with Donna's sheets, for example
   `D:\Projects\Donna`. Next to each picture, say what it is (the widget guesses from the name),
   then press **Cut pictures**.
5. Optional: **Start at login**, and the live chat (below).

Click ▁ for the slim bar and her face to come back. **Ctrl+Shift+D** (**Cmd+Shift+D** on a Mac) is
discreet mode for screen sharing: figure and times only, chat hidden, notifications say only
"Something needs you."

## She moves

Every picture is animated with a light mesh warp drawn by WebGL: she breathes, shifts her weight,
tilts her head, her hair sways, and she nods while her line changes. The way she moves follows her
mood: bouncier when laughing, stiff and shaking when furious, slower and lower when sad, head
tilted when thoughtful. With reduced motion turned on in your system settings, she stays still.

## Her pictures

The widget cuts each sheet into separate emotions and scenes and saves them in a `donna-cut` folder
inside your pictures folder. Look there to check the cuts; replace any file with your own crop
(same name) and it's used next time. Re-cutting replaces that folder.

| Sheet | What it gives her |
|---|---|
| Smiles | Normal smile, wide smile, laughing, playful, enchanted: full figures and close-ups |
| Poses | Over-the-shoulder half bust, walking, at the desk, on the phone, coffee, reading, close-ups |
| A day in her life | Morning, getting ready, heading out, at work, lunch, pickleball, winding down; a half bust |
| Full-body emotions | Serious, angry, amused, happy, thoughtful |
| Intense emotions | Cold anger, fury, crying, sobbing, cooling down: full figures and close-ups |
| Gig night | Evening events, celebrating, relaxed close-ups |
| Office emotions | Normal, happy, amused, surprised, thoughtful |
| Character sheet | Turnaround (cut out from the paper), in-action poses, the eight expressions |

A single picture can be used whole for one emotion or scene ("One picture, used as…").

**When she shows what.** In Auto, calm moments show the scene for the block (at work, on a call,
lunch, coffee break, morning, winding down, exercise for anything like pickleball or the gym).
Strong moments show emotion: late with high anger means arms crossed, and furious after 15 minutes
if anger is 8 or more; late with sarcasm means amused; started late means cooling down; done means
happy, laughing or playful; finishing the whole day with happiness at 9 or more means enchanted. With
sadness at 8 or more, a skip or a long delay can bring tears. Missing pictures fall back to the
nearest one (furious → angry → serious → normal). Full body, Half bust and Close-up fix the view;
Off hides her and narrows the widget.

## Personality

Settings → Personality: your temperament (late or doing well, always angry, or classic) and seven
dials from 0 to 10: humour, sarcasm, anger, calm, happiness, sadness and chattiness. "Running late"
and "Doing well" show sample lines as you move them. The widget writes them to `persona.json` in the
plan folder, and Donna picks them up at her next session, so she sounds the same in chat, on
WhatsApp and here.

## Chat

- **Live**, when Claude Code is installed and signed in on this computer: the widget finds
  `claude` (or `claude.exe` / `claude.cmd`) and this repository, and Donna answers in the chat. It
  starts Claude Code with the `donna` agent and only read-only tools (read files, search the web,
  run Donna's calculators), so from the widget she can look things up and prepare, never send, post,
  book or change your calendar. For those, she tells you to confirm in the Claude app. On Windows,
  Donna's calculators need Python on the path as `python3`.
- **Messages only** otherwise: what you type goes to `inbox.jsonl`, Donna handles it at her next
  check-in and her answer appears in the chat.

Settings → Chat shows which one is active, and lets you point at Claude Code or this repository if
they weren't found, or start a fresh conversation.

## Security

- The page has no network access: only local files load, every other request is blocked. No
  permissions (camera, microphone, location), no pop-ups, no navigation, a strict content security
  policy, context isolation and the sandbox on, Node off.
- The page can only ask the app for a short list of actions (`preload.js`).
- The app reads the plan folder and the pictures folder, and writes only `inbox.jsonl`,
  `log.jsonl` and `persona.json` in the plan folder and the cut pictures in `donna-cut`.
- `today.json` is checked before it's shown (`feed.js`), and everything is shown as text, never
  HTML.
- The live chat uses Claude Code on your own computer with your own login; your message goes to it
  through standard input, never the command line, and its tools are read-only.
- No passwords, tokens or account data anywhere in the widget. Settings live in your user profile,
  your pictures stay on your machine.

## Files

| File | What it is |
|---|---|
| `main.js` | The app: window, notifications, plan and pictures folders, the chat, the lockdown |
| `preload.js` | The short list of actions the page may ask for |
| `feed.js` | Checks `today.json` |
| `renderer/index.html`, `styles.css`, `app.js` | The widget |
| `renderer/voice.js` | Her lines, chosen by temperament and dials |
| `renderer/manifest.js` | Where each emotion and scene sits on each sheet; which scene fits which block |
| `renderer/art.js` | Cuts the sheets and picks the picture for the moment |
| `renderer/motion.js` | Animates her: breathing, weight shift, head tilt, hair, nods while she talks, motion by mood |
| `sample/today.json` | The demo day; also shows the format Donna writes |
| `test/` | `npm test` |

## The plan format

`today.json` is what `python3 tools/sessions.py <input> --widget` produces, plus Donna's additions:

```json
{
  "version": 1,
  "date": "2026-10-05",
  "temperament": "earned",
  "mood": "neutral",
  "message": "Three things today. Not four. Three.",
  "blocks": [{"id": "b5", "start": "10:00", "end": "10:45", "kind": "focus",
              "title": "Draft the Q3 deck (1/3)", "first_step": "Open the deck and write three slide titles"}],
  "outfit": {"summary": "Navy linen shirt, beige chinos, white sneakers"},
  "occasions": [{"who": "Mom", "what": "birthday", "action": "call before 9 pm"}],
  "events": [{"title": "Indie rock night", "when": "Sat 8 pm"}],
  "wins": ["Cleared all three email drafts before 10 yesterday"],
  "reminders": [{"at": "16:00", "text": "Water. And stand up for a minute."}],
  "replies": [{"at": "2026-10-05T08:10", "text": "Moved the gym to 6 pm. Deck first."}]
}
```

Block kinds: `anchor`, `meal`, `meeting`, `event`, `buffer`, `reset`, `focus`, `break`.
