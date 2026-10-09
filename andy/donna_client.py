"""Donna's side of the Andy link. Donna runs this on the same PC to talk to Andy.

Set the pairing key from Andy (Security > Donna) in the environment as ANDY_DONNA_PAIRING, then:

  python -m andy.donna_client expense --amount 1499 --payee "Cult.fit" --purpose "Monthly gym" --due 2026-10-20
  python -m andy.donna_client summary --period this_month --reason "Planning the weekend"
  python -m andy.donna_client responses

Donna can only ask. Every expense stays pending until Shrey approves it inside Andy, and Andy never
makes payments itself.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import donna
from .paths import donna_dirs


def _key() -> bytes:
    value = os.environ.get("ANDY_DONNA_PAIRING", "")
    if not value:
        raise SystemExit("Set ANDY_DONNA_PAIRING to the pairing key shown in Andy.")
    return donna.parse_pairing_string(value)


def request_expense(amount: float, payee: str, purpose: str, due: str | None = None, category: str | None = None) -> str:
    body = {"type": "expense_request", "amount": amount, "payee": payee, "purpose": purpose}
    if due:
        body["due"] = due
    if category:
        body["category"] = category
    donna.validate_request(body)  # fail early with a clear message
    inbox, _ = donna_dirs()
    return donna.write_message(inbox, _key(), donna.TO_ANDY, body).name


def request_summary(period: str, reason: str) -> str:
    body = {"type": "summary_request", "period": period, "reason": reason}
    donna.validate_request(body)
    inbox, _ = donna_dirs()
    return donna.write_message(inbox, _key(), donna.TO_ANDY, body).name


def responses() -> list[dict]:
    """Read and remove Andy's replies: decisions on expenses, and any summaries Shrey chose to share."""
    _, outbox = donna_dirs()
    key, out = _key(), []
    for path in sorted(outbox.glob("*.json")):
        try:
            out.append(donna.open_envelope(key, donna.TO_DONNA, json.loads(path.read_text(encoding="utf-8"))))
        except (donna.DonnaError, ValueError):
            continue
        finally:
            path.unlink(missing_ok=True)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("expense")
    e.add_argument("--amount", type=float, required=True)
    e.add_argument("--payee", required=True)
    e.add_argument("--purpose", required=True)
    e.add_argument("--due")
    e.add_argument("--category")
    s = sub.add_parser("summary")
    s.add_argument("--period", choices=donna.PERIODS, required=True)
    s.add_argument("--reason", required=True)
    sub.add_parser("responses")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "expense":
            print("Sent to Andy for Shrey's approval:", request_expense(a.amount, a.payee, a.purpose, a.due, a.category))
        elif a.cmd == "summary":
            print("Sent to Andy for Shrey's approval:", request_summary(a.period, a.reason))
        else:
            print(json.dumps(responses(), indent=2, ensure_ascii=False))
    except donna.DonnaError as exc:
        print(f"Not sent: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
