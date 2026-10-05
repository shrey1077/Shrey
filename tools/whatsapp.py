#!/usr/bin/env python3
"""Send Shrey a WhatsApp message from Donna through Meta's official WhatsApp Cloud API.

Security model:
- Credentials come only from environment variables, never from arguments or files in the repo,
  and are never printed:
    WHATSAPP_TOKEN            access token of a System User with only the whatsapp_business_messaging permission
    WHATSAPP_PHONE_NUMBER_ID  the ID of Donna's sending number (from WhatsApp Manager)
    WHATSAPP_TO               Shrey's own number, digits only with country code (e.g. 91XXXXXXXXXX)
    WHATSAPP_API_VERSION      optional, default below; Meta retires old versions, so keep it current
- The recipient is always WHATSAPP_TO. Donna cannot message anyone else with this tool.
- Messages that look like they carry secrets or identifiers (OTP, password, PAN, Aadhaar, card or
  account numbers) are refused. WhatsApp Cloud API messages pass through Meta's servers, so keep
  health, money and other sensitive details out of them.
- --dry-run shows exactly what would be sent, without sending.

  python3 tools/whatsapp.py check
  python3 tools/whatsapp.py text "Breakfast. Now. Eggs or poha, your call." --dry-run
  python3 tools/whatsapp.py template donna_nudge --param "Session 2 starts at 10:00: Q3 deck" --dry-run

A free-form `text` only delivers inside the 24-hour window after Shrey last messaged Donna's number.
Outside it, WhatsApp requires an approved template (see secretary/whatsapp-setup.md).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT_API_VERSION = "v26.0"  # Graph API, as of Oct 2026
MAX_CHARS = 1000  # WhatsApp allows 4096; anything longer won't get read on a phone anyway

_BLOCKED = [
    (re.compile(r"\b(otp|one[- ]time password|password|passcode|cvv|upi pin|mpin|atm pin)\b", re.I),
     "mentions a password, OTP or PIN"),
    (re.compile(r"\b[A-Z]{3}[PCHFATBLJG][A-Z][0-9]{4}[A-Z]\b"), "contains a PAN"),
    (re.compile(r"\b[2-9][0-9]{3}[ -]?[0-9]{4}[ -]?[0-9]{4}\b"), "contains an Aadhaar-like number"),
    (re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), "contains an IFSC code"),
    (re.compile(r"\b\d{11,18}\b"), "contains a long number (account or card?)"),
]
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def screen(text: str) -> list[str]:
    """Reasons this text must not go out over WhatsApp. Empty means it is fine."""
    problems = [why for pattern, why in _BLOCKED if pattern.search(text)]
    for m in _CARD.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            problems.append("contains a card-like number")
            break
    if len(text) > MAX_CHARS:
        problems.append(f"is {len(text)} characters; keep it under {MAX_CHARS}")
    if not text.strip():
        problems.append("is empty")
    return problems


def config(env=os.environ) -> dict:
    missing = [k for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_TO") if not env.get(k)]
    if missing:
        raise RuntimeError("not configured; set " + ", ".join(missing) + " (see secretary/whatsapp-setup.md)")
    to = env["WHATSAPP_TO"].lstrip("+")
    if not re.fullmatch(r"\d{10,15}", to):
        raise RuntimeError("WHATSAPP_TO must be digits with the country code, e.g. 91XXXXXXXXXX")
    if not re.fullmatch(r"\d{5,30}", env["WHATSAPP_PHONE_NUMBER_ID"]):
        raise RuntimeError("WHATSAPP_PHONE_NUMBER_ID should be the numeric ID from WhatsApp Manager")
    version = env.get("WHATSAPP_API_VERSION", DEFAULT_API_VERSION)
    if not re.fullmatch(r"v\d+\.\d+", version):
        raise RuntimeError("WHATSAPP_API_VERSION looks wrong; expected something like v26.0")
    return {"token": env["WHATSAPP_TOKEN"], "number_id": env["WHATSAPP_PHONE_NUMBER_ID"], "to": to,
            "url": f"https://graph.facebook.com/{version}/{env['WHATSAPP_PHONE_NUMBER_ID']}/messages"}


def text_payload(to: str, body: str) -> dict:
    return {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": "text",
            "text": {"preview_url": False, "body": body}}


def template_payload(to: str, name: str, params: list[str], lang: str = "en") -> dict:
    if not re.fullmatch(r"[a-z0-9_]{1,512}", name):
        raise ValueError("template names are lowercase letters, digits and underscores")
    template = {"name": name, "language": {"code": lang}}
    if params:
        template["components"] = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]
    return {"messaging_product": "whatsapp", "to": to, "type": "template", "template": template}


def masked(number: str) -> str:
    return number[:2] + "•" * (len(number) - 6) + number[-4:]


def send(cfg: dict, payload: dict) -> str:
    request = urllib.request.Request(
        cfg["url"], data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {cfg['token']}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            reply = json.load(response)
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")
        try:
            detail = json.loads(detail)["error"].get("message", detail)
        except (ValueError, KeyError, TypeError):
            pass
        raise RuntimeError(f"WhatsApp API refused it ({err.code}): {detail.replace(cfg['token'], '[token]')}") from None
    except urllib.error.URLError as err:
        raise RuntimeError(f"couldn't reach WhatsApp: {err.reason}. Is graph.facebook.com allowed on this network?") from None
    return reply.get("messages", [{}])[0].get("id", "sent")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="check the configuration without sending")
    p = sub.add_parser("text", help="free-form text (only inside the 24-hour window)")
    p.add_argument("body")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("template", help="an approved template")
    p.add_argument("name")
    p.add_argument("--param", action="append", default=[], help="body parameter, in order; repeatable")
    p.add_argument("--lang", default="en")
    p.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    try:
        if a.cmd == "check":
            cfg = config()
            print(f"Configured: sending from number ID {cfg['number_id']} to {masked(cfg['to'])} via {cfg['url']}")
            return 0
        texts = [a.body] if a.cmd == "text" else a.param
        problems = [p for t in texts for p in screen(t)]
        if problems:
            print("Refused: the message " + "; ".join(dict.fromkeys(problems)) + ".", file=sys.stderr)
            return 3
        cfg = config() if not a.dry_run else None
        to = cfg["to"] if cfg else "<WHATSAPP_TO>"
        payload = text_payload(to, a.body) if a.cmd == "text" else template_payload(to, a.name, a.param, a.lang)
        if a.dry_run:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
        print(f"Sent to {masked(cfg['to'])}: {send(cfg, payload)}")
        return 0
    except (RuntimeError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
