"""The secure link between Andy and Donna, Shrey's other AI assistant.

Design:
- No network port. The two exchange small files in %LOCALAPPDATA%\\Andy\\donna\\inbox (Donna to
  Andy) and \\outbox (Andy to Donna).
- Every message is encrypted and authenticated with AES-256-GCM under a key derived from a 32-byte
  pairing key that Shrey copies from Andy into Donna once. Each direction has its own key.
- Messages carry a random id and a timestamp. Andy rejects stale, future-dated, replayed,
  oversized or malformed messages.
- Donna can only *ask*: propose an expense, or request a spending summary. Andy queues each
  request for Shrey. Nothing is paid and nothing is shared until Shrey approves it in Andy, and
  larger expenses need the passphrase too.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from datetime import date
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .categorize import CATEGORIES

PAIR_PREFIX = "andy-pair-v1:"
MAX_FILE_BYTES = 16 * 1024
MAX_AGE_SECONDS = 7 * 24 * 3600
MAX_FUTURE_SECONDS = 300
MAX_AMOUNT = 10_00_000
TO_ANDY, TO_DONNA = "donna->andy", "andy->donna"
PERIODS = ("this_month", "last_month", "this_year")


class DonnaError(Exception):
    pass


def new_pairing_key() -> bytes:
    return os.urandom(32)


def pairing_string(key: bytes) -> str:
    return PAIR_PREFIX + base64.urlsafe_b64encode(key).decode("ascii").rstrip("=")


def parse_pairing_string(text: str) -> bytes:
    text = text.strip()
    if not text.startswith(PAIR_PREFIX):
        raise DonnaError("Not an Andy pairing key.")
    raw = text[len(PAIR_PREFIX):]
    key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    if len(key) != 32:
        raise DonnaError("Pairing key has the wrong length.")
    return key


def _direction_key(pairing_key: bytes, direction: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=f"andy-donna/v1/{direction}".encode()).derive(pairing_key)


def _aad(direction: str, msg_id: str, ts: int) -> bytes:
    return f"andy-donna/v1|{direction}|{msg_id}|{ts}".encode()


def seal(pairing_key: bytes, direction: str, body: dict) -> dict:
    msg_id, ts = uuid.uuid4().hex, int(time.time())
    nonce = os.urandom(12)
    plaintext = json.dumps(body, separators=(",", ":")).encode()
    ct = AESGCM(_direction_key(pairing_key, direction)).encrypt(nonce, plaintext, _aad(direction, msg_id, ts))
    return {"v": 1, "id": msg_id, "ts": ts, "nonce": base64.b64encode(nonce).decode(), "ct": base64.b64encode(ct).decode()}


def open_envelope(pairing_key: bytes, direction: str, envelope: dict, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    if not isinstance(envelope, dict) or envelope.get("v") != 1:
        raise DonnaError("Unknown message format.")
    msg_id, ts = envelope.get("id"), envelope.get("ts")
    if not isinstance(msg_id, str) or not re.fullmatch(r"[0-9a-f]{32}", msg_id) or not isinstance(ts, int):
        raise DonnaError("Malformed message header.")
    if ts > now + MAX_FUTURE_SECONDS or ts < now - MAX_AGE_SECONDS:
        raise DonnaError("Message is too old or dated in the future.")
    try:
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ct = base64.b64decode(envelope["ct"], validate=True)
        plaintext = AESGCM(_direction_key(pairing_key, direction)).decrypt(nonce, ct, _aad(direction, msg_id, ts))
    except (InvalidTag, KeyError, ValueError, TypeError):
        raise DonnaError("Message failed authentication.") from None
    body = json.loads(plaintext)
    if not isinstance(body, dict):
        raise DonnaError("Message body must be an object.")
    return body


def _text(value, limit: int, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DonnaError(f"'{field}' is required.")
    value = re.sub(r"[\x00-\x1f\x7f]", " ", value).strip()
    return value[:limit]


def validate_request(body: dict) -> dict:
    kind = body.get("type")
    if kind == "expense_request":
        amount = body.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not 0 < amount <= MAX_AMOUNT:
            raise DonnaError("Amount must be between ₹1 and ₹10,00,000.")
        out = {"type": kind, "amount": round(float(amount), 2), "payee": _text(body.get("payee"), 80, "payee"),
               "purpose": _text(body.get("purpose"), 200, "purpose")}
        if body.get("due"):
            try:
                out["due"] = date.fromisoformat(str(body["due"])).isoformat()
            except ValueError:
                raise DonnaError("'due' must be a date like 2026-10-20.") from None
        if body.get("category"):
            if body["category"] not in CATEGORIES:
                raise DonnaError("Unknown category.")
            out["category"] = body["category"]
        return out
    if kind == "summary_request":
        if body.get("period") not in PERIODS:
            raise DonnaError(f"'period' must be one of {', '.join(PERIODS)}.")
        return {"type": kind, "period": body["period"], "reason": _text(body.get("reason", "Not given"), 200, "reason")}
    raise DonnaError("Donna can only send expense_request or summary_request.")


def read_inbox(inbox: Path, pairing_key: bytes, seen: dict[str, int], now: float | None = None) -> tuple[list[dict], list[str]]:
    """Validate and remove every file in the inbox. Returns (accepted requests, rejection reasons)."""
    now = time.time() if now is None else now
    accepted, rejected = [], []
    for path in sorted(inbox.glob("*.json")):
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                raise DonnaError("Message is too large.")
            envelope = json.loads(path.read_text(encoding="utf-8"))
            body = open_envelope(pairing_key, TO_ANDY, envelope, now)
            if envelope["id"] in seen:
                raise DonnaError("Replayed message.")
            request = validate_request(body)
            seen[envelope["id"]] = envelope["ts"]
            accepted.append({"id": envelope["id"], "received": int(now), "sent": envelope["ts"], **request,
                             "status": "pending"})
        except (DonnaError, ValueError, OSError) as exc:
            rejected.append(f"{path.name}: {exc}")
        finally:
            try:
                path.unlink()
            except OSError:
                pass
    # Forget ids older than the acceptance window; they would be rejected as stale anyway.
    for msg_id in [k for k, ts in seen.items() if ts < now - MAX_AGE_SECONDS - 3600]:
        del seen[msg_id]
    return accepted, rejected


def write_message(folder: Path, pairing_key: bytes, direction: str, body: dict) -> Path:
    envelope = seal(pairing_key, direction, body)
    path = folder / f"{envelope['ts']}-{envelope['id']}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(envelope), encoding="utf-8")
    os.replace(tmp, path)
    return path
