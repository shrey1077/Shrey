# Setting up Donna on WhatsApp

Donna messages Shrey through Meta's official **WhatsApp Cloud API**. Unofficial tools that drive
WhatsApp Web (whatsapp-web.js, Baileys, browser bots) are not used: they break WhatsApp's terms,
get numbers banned, and hold a session that gives full access to your account.

Rules and prices as of October 2026; check Meta's developer docs if anything looks different.

## What you get

- Donna sends you short messages: wake-up, breakfast, the day's plan, session starts, birthdays,
  the wind-down, the weekly events digest.
- Reply to Donna's message at least once a day (a 👍 is enough). That keeps WhatsApp's 24-hour
  window open, so Donna can send ordinary messages. Outside the window, only pre-approved
  templates are delivered.
- In this first version, Donna doesn't read your replies. Talk to Donna in the Claude app for
  anything two-way.
- Cost: in India, a utility template costs ₹0.115 plus 18% GST. From 1 October 2026 each business
  number gets 1,000 free service messages a month. At Donna's volume that comes to a few rupees a
  month.

## 1. Create the app and get a number

1. Go to developers.facebook.com, sign in, and create an app of type **Business**. Add the
   **WhatsApp** product. Meta creates a WhatsApp Business account and a free **test number**.
2. On the WhatsApp **API Setup** page, add your own WhatsApp number as a recipient and verify it
   with the code Meta sends. The test number can only message up to five verified numbers, which
   suits Donna: it can't message anyone else even by mistake.
3. Note the **Phone number ID** of the sending number.

The test number is enough to start. If you later want a permanent number, use a new SIM that is
not on the WhatsApp or WhatsApp Business app, and add it in WhatsApp Manager.

## 2. Create a long-lived, minimal token

The token on the API Setup page expires in 24 hours. For Donna:

1. In Meta Business Settings (business.facebook.com/settings), go to **Users → System users** and
   add a system user.
2. Assign it the app and the WhatsApp account as assets.
3. Generate a token with only the **whatsapp_business_messaging** permission. Copy it once into the
   place it will live (step 4), and nowhere else. Never paste it into a chat, including with Donna.

## 3. Create the templates

In WhatsApp Manager, under **Message templates**, create these as **Utility**, English. Meta
doesn't accept a body that starts or ends with a variable.

| Name | Body |
|---|---|
| `donna_nudge` | `Donna here. {{1}} Reply to this message to keep our chat open.` |
| `donna_morning` | `Good morning from Donna. Today: {{1}} First step: {{2}} Reply 👍 when you're up.` |

Approval usually takes minutes to a day.

## 4. Store the settings

Donna reads four environment variables:

| Variable | Value |
|---|---|
| `WHATSAPP_TOKEN` | the system-user token |
| `WHATSAPP_PHONE_NUMBER_ID` | the sending number's ID |
| `WHATSAPP_TO` | your own number with country code, digits only (91 then the 10 digits) |
| `WHATSAPP_API_VERSION` | optional; defaults to v26.0 |

**For cloud sessions and routines:** open the cloud environment's settings (the environment menu in
the session's title bar, then Edit). Add the variables there, and under **Network access** choose
Custom, keep the default package-manager list, and add `graph.facebook.com` to the allowed domains.
Without that, the network blocks the API (it does today). Steps:
https://code.claude.com/docs/en/cloud-environments#network-access

**On your own computer:** keep them in your password manager or OS keychain and load them into the
shell when needed. Never put them in a file inside this repository.

## 5. Test

```sh
python3 tools/whatsapp.py check
python3 tools/whatsapp.py template donna_nudge --param "Test from Donna."
# reply to it on your phone, then, inside 24 hours:
python3 tools/whatsapp.py text "Free-form works too."
```

Then set `channels.whatsapp.enabled: true` in Donna's preferences (or tell Donna to).

## Keep it safe

- Turn on two-step verification on your own WhatsApp (Settings → Account → Two-step verification).
- Protect the Meta Business account with 2FA.
- Rotate the token every 90 days; revoke it at once if it ever leaks (`secretary/SECURITY.md`).
