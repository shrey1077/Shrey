"""Read-only Gmail sync for bank, card and UPI alerts.

- Connects only to imap.gmail.com:993 over verified TLS 1.2+.
- Opens the mailbox read-only (IMAP EXAMINE) and fetches with BODY.PEEK, so nothing is marked
  read, moved or deleted.
- Accepts an email only if it comes from a known bank or card domain AND Gmail recorded a passing
  DKIM or DMARC check for that domain. A spoofed "bank alert" cannot plant transactions.
"""

from __future__ import annotations

import email
import email.policy
import hashlib
import imaplib
import re
import ssl
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime

from .parser import html_to_text

HOST, PORT = "imap.gmail.com", 993
# Gmail search: any of these words, newest alerts, no promotions.
_QUERY = "{debited spent withdrawn credited txn transaction upi refund reversed} -category:promotions -category:social"
MAX_PER_SYNC = 600

# Sender domains of Indian banks, card issuers and payment banks. Shrey can add more in Settings.
TRUSTED_DOMAINS = (
    "hdfcbank.net", "hdfcbank.com", "icicibank.com", "axisbank.com", "axis.bank.in", "sbi.co.in", "sbicard.com",
    "kotak.com", "kotak.bank.in", "yesbank.in", "idfcfirstbank.com", "indusind.com", "pnb.co.in", "bankofbaroda.com",
    "bankofbaroda.co.in", "canarabank.com", "unionbankofindia.co.in", "federalbank.co.in", "aubank.in", "rblbank.com",
    "sc.com", "hsbc.co.in", "citi.com", "americanexpress.com", "aexp.com", "getonecard.app", "paytmbank.com",
    "airtel.in", "jupiter.money", "fi.money", "sliceit.com", "bobcard.co.in", "idbibank.co.in", "iob.in",
    "indianbank.in", "centralbankofindia.co.in", "dbs.com", "equitasbank.com", "ujjivansfb.in", "bandhanbank.com",
)


class GmailError(Exception):
    pass


@dataclass
class Alert:
    uid_hash: str
    sender_domain: str
    subject: str
    body: str
    received: datetime


def _domain_ok(domain: str, trusted: tuple[str, ...]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in trusted)


def authenticated_domain(msg: email.message.Message, trusted: tuple[str, ...]) -> str | None:
    """The trusted sender domain if Gmail verified it with DKIM or DMARC, else None."""
    _, address = parseaddr(msg.get("From", ""))
    domain = address.rpartition("@")[2].lower()
    if not domain or not _domain_ok(domain, trusted):
        return None
    # Gmail adds its own Authentication-Results header (authserv-id mx.google.com) at the top.
    for header in msg.get_all("Authentication-Results", []):
        text = str(header).lower()
        if not text.lstrip().startswith("mx.google.com"):
            continue
        if re.search(r"dmarc=pass[^;]*header\.from=" + re.escape(domain), text):
            return domain
        for m in re.finditer(r"dkim=pass[^;]*header\.(?:i|d)=@?([a-z0-9.\-]+)", text):
            signer = m.group(1)
            if signer == domain or domain.endswith("." + signer) or signer.endswith("." + domain):
                return domain
        return None
    return None


def _body_text(msg: email.message.Message) -> str:
    plain, markup = None, None
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        try:
            payload = part.get_content()
        except (LookupError, ValueError):
            continue
        if not isinstance(payload, str):
            continue
        if part.get_content_type() == "text/plain" and plain is None:
            plain = payload
        elif part.get_content_type() == "text/html" and markup is None:
            markup = payload
    text = plain if plain and plain.strip() else html_to_text(markup or "")
    return text[:20000]


def _all_mail_box(conn: imaplib.IMAP4_SSL) -> str:
    """Gmail's All Mail folder has a different name in some languages; find it by its \\All flag."""
    typ, boxes = conn.list()
    if typ == "OK":
        for raw in boxes or []:
            line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
            if "\\All" in line:
                name = line.rsplit(' "/" ', 1)[-1].strip()
                return name if name.startswith('"') else f'"{name}"'
    return "INBOX"


def fetch_alerts(address: str, app_password: str, since: date, seen: set[str],
                 trusted: tuple[str, ...] = TRUSTED_DOMAINS) -> tuple[list[Alert], dict]:
    """Fetch new, authenticated alert emails since `since`. Returns (alerts, counts)."""
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", address.strip(), re.I):
        raise GmailError("Enter your full Gmail address.")
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    counts = {"found": 0, "new": 0, "untrusted_sender": 0, "failed_authentication": 0}
    alerts: list[Alert] = []
    try:
        with imaplib.IMAP4_SSL(HOST, PORT, ssl_context=ctx, timeout=30) as conn:
            try:
                conn.login(address.strip(), app_password.replace(" ", ""))
            except imaplib.IMAP4.error:
                raise GmailError("Gmail refused the sign-in. Check the address and the 16-letter app password.") from None
            typ, _ = conn.select(_all_mail_box(conn), readonly=True)
            if typ != "OK":
                raise GmailError("Could not open the mailbox.")
            raw_query = f"after:{since:%Y/%m/%d} {_QUERY}"
            typ, data = conn.search(None, "X-GM-RAW", '"' + raw_query.replace('"', "") + '"')
            if typ != "OK":
                raise GmailError("Gmail search failed.")
            ids = (data[0] or b"").split()[-MAX_PER_SYNC:]
            counts["found"] = len(ids)
            for msg_id in ids:
                typ, parts = conn.fetch(msg_id, "(BODY.PEEK[])")
                if typ != "OK" or not parts or not isinstance(parts[0], tuple):
                    continue
                msg = email.message_from_bytes(parts[0][1], policy=email.policy.default)
                key = hashlib.sha256((msg.get("Message-ID", "") or msg.get("Date", "")).encode()).hexdigest()[:24]
                if key in seen:
                    continue
                _, sender = parseaddr(msg.get("From", ""))
                if not _domain_ok(sender.rpartition("@")[2].lower(), trusted):
                    counts["untrusted_sender"] += 1
                    continue
                domain = authenticated_domain(msg, trusted)
                if domain is None:
                    counts["failed_authentication"] += 1
                    continue
                try:
                    received = parsedate_to_datetime(msg.get("Date"))
                    received = received.astimezone().replace(tzinfo=None) if received.tzinfo else received
                except (TypeError, ValueError):
                    received = datetime.now(timezone.utc).astimezone().replace(tzinfo=None)
                alerts.append(Alert(key, domain, str(msg.get("Subject", ""))[:300], _body_text(msg), received))
                counts["new"] += 1
    except (OSError, ssl.SSLError) as exc:
        raise GmailError(f"Could not reach Gmail securely: {exc.__class__.__name__}.") from None
    return alerts, counts


def test_login(address: str, app_password: str) -> None:
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        with imaplib.IMAP4_SSL(HOST, PORT, ssl_context=ctx, timeout=20) as conn:
            conn.login(address.strip(), app_password.replace(" ", ""))
    except imaplib.IMAP4.error:
        raise GmailError("Gmail refused the sign-in. Check the address and the 16-letter app password.") from None
    except (OSError, ssl.SSLError) as exc:
        raise GmailError(f"Could not reach Gmail securely: {exc.__class__.__name__}.") from None
