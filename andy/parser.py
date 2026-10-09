"""Turn a bank, card or UPI alert email into a transaction.

Indian banks word their alerts differently, so this looks for the pieces every alert has: an
amount in rupees, a debit or credit word, a merchant or payee, a date, and a masked account.
Anything that isn't clearly a completed transaction (OTPs, offers, failed or declined payments,
payment requests) is ignored.
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from .categorize import merchant_key

_AMOUNT = re.compile(r"(?:INR|Rs\.?|₹)\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.I)
_NOT_A_SPEND = re.compile(r"(?:avl\.?|avbl\.?|available|closing|total|outstanding)\s*(?:bal(?:ance)?|limit|credit limit|amt|amount|due)"
                          r"|(?:bal(?:ance)?|limit)\s*(?:is|:|of)?\s*$|min(?:imum)?\.?\s*(?:amount\s*)?due", re.I)
_SKIP = re.compile(r"\b(?:otp|one time password|failed|declined|unsuccessful|could not be processed|was not successful|"
                   r"payment request|collect request|requested money|offer|pre-approved|eligible|cashback of up to|"
                   r"statement (?:is ready|for)|e-?mandate (?:registered|created|registration)|will be debited|is due on)\b", re.I)
_DEBIT = re.compile(r"\b(?:debited|debit|spent|paid|sent|withdrawn|withdrawal|purchase|deducted|charged|txn of|"
                    r"transaction of|used for|done at|made at)\b", re.I)
_CREDIT_TO_YOU = re.compile(r"\b(?:credited to (?:your|a/?c|ac|acct|account|card)|has been credited|is credited|"
                            r"received (?:from|in|a payment)|deposited|refund(?:ed)?|reversed|reversal|cashback (?:of|credited))\b", re.I)
_CREDIT = re.compile(r"\b(?:credited|received|deposited|refund(?:ed)?|reversed|reversal)\b", re.I)
_ACCOUNT = re.compile(r"\b(?:a/c|ac|acct|account|card)\b[^0-9\n]{0,24}?(?:[Xx*]{1,12}\s?|ending(?: with)?\s*)(\d{4})\b", re.I)
_VPA = re.compile(r"\b(?:to|by|from|vpa)\s+(?:vpa\s+)?([A-Za-z0-9._\-]{2,64}@[A-Za-z0-9]{2,32})"
                  r"(?:\s+\(?(?!(?:on|upi|ref|at|via|for|dated)\b)([A-Z][A-Za-z0-9 &.'\-]{2,40}?)\)?)?"
                  r"(?=\s+(?:on|upi|ref|at|via|for|dated)\b|[.,;]|\s*$)", re.I)
_AT = re.compile(r"\b(?:at|@)\s+([A-Za-z0-9][A-Za-z0-9 &.'*/_\-]{1,50}?)\s*(?=\bon\b|\bvia\b|\busing\b|\bfor\b|\bavl\b|"
                 r"\bavbl\b|\bref\b|[.,;]|\s*$)", re.I)
_TO = re.compile(r"\b(?:to|towards|info:?|beneficiary:?|payee:?)\s+([A-Za-z][A-Za-z0-9 &.'\-]{2,40}?)\s*(?=\bon\b|\bvia\b|"
                 r"\bref\b|\bupi\b|\bimps\b|\bneft\b|\bfrom\b|[.,;]|\s*$)", re.I)
_FROM = re.compile(r"\bfrom\s+([A-Za-z][A-Za-z0-9 &.'\-]{2,50}?)\s*(?=\bon\b|\bvia\b|\bref\b|\bupi\b|[.,;]|\s*$)", re.I)
_TRAILING_NOISE = re.compile(r"\s+(?:not you|if not|avl|avbl|bal|call|sms|ref|on|info|thank)\b.*$", re.I)
_GATEWAY_WORDS = {"upi", "payu", "razorpay", "rzp", "stores", "store", "online", "pg", "bd", "billdesk", "cashfree",
                  "paytm", "ccavenue", "pay", "payments", "merchant", "india", "in", "ybl", "okaxis", "okhdfcbank"}
_UPI_NARRATION = re.compile(r"UPI[/\-](?:P2[AM][/\-])?(?:[0-9]+[/\-])?([A-Za-z][A-Za-z0-9 .&\-]{2,30})", re.I)
_UPI_REF = re.compile(r"(?:ref(?:erence)?\.?\s*(?:no\.?|number|id)?|rrn|utr)\s*[:\-]?\s*(\d{10,16})", re.I)
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})(?::\d{2})?\s*([AaPp][Mm])?")
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DATES = [
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[-/ ]?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-/, ]*(\d{2,4})\b", re.I), "dMy"),
    (re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b"), "dmy"),
]
_STOPWORDS = {"your", "you", "a/c", "ac", "account", "the", "card", "bank", "upi", "vpa", "self"}


@dataclass
class Parsed:
    date: str
    time: str | None
    amount: float
    direction: str
    kind: str  # expense, refund or income
    merchant: str
    mode: str
    account: str
    context: str
    fingerprint: str

    def to_dict(self) -> dict:
        return asdict(self)


def html_to_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</td>|</li>", "\n", markup)
    return html.unescape(re.sub(r"<[^>]+>", " ", markup))


def _clean(text: str) -> str:
    return re.sub(r"[ \t ]+", " ", text).strip()


def _mask_digits(text: str) -> str:
    """Hide long numbers (reference numbers, phone numbers) from anything stored."""
    return re.sub(r"\d{6,}", lambda m: "•" * 4 + m.group()[-2:], text)


_ABBREVIATIONS = {"no", "rs", "a/c", "ac", "ltd", "pvt", "avl", "avbl", "bal", "trxn", "txn", "ref", "approx", "dt", "co"}


def _sentences(text: str) -> list[str]:
    """Split into sentences without breaking at abbreviations such as 'A/c no.' or 'Rs.'."""
    out = []
    for line in text.splitlines():
        start = 0
        for m in re.finditer(r"[.!?]\s+(?=[A-Z])", line):
            word = re.findall(r"[A-Za-z/]+$", line[start:m.start()])
            if word and word[0].lower() in _ABBREVIATIONS:
                continue
            out.append(line[start:m.start() + 1])
            start = m.end()
        out.append(line[start:])
    return [_clean(p) for p in out if _clean(p)]


def _pick_amount(sentence: str) -> float | None:
    for m in _AMOUNT.finditer(sentence):
        before = sentence[max(0, m.start() - 30):m.start()]
        if _NOT_A_SPEND.search(before):
            continue
        try:
            value = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if value > 0:
            return value
    return None


def _parse_date(text: str, received: datetime) -> date:
    for pattern, kind in _DATES:
        for m in pattern.finditer(text):
            try:
                if kind == "ymd":
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif kind == "dMy":
                    d, mo, y = int(m.group(1)), _MONTHS[m.group(2).lower()[:3]], int(m.group(3))
                else:
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if y < 100:
                    y += 2000
                found = date(y, mo, d)
            except (ValueError, KeyError):
                continue
            # Alerts arrive within minutes of the transaction; anything far off is some other date.
            if received.date() - timedelta(days=45) <= found <= received.date() + timedelta(days=1):
                return found
    return received.date()


def _parse_time(text: str, received: datetime) -> str:
    for m in _TIME.finditer(text):
        hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
        if ampm:
            hour = hour % 12 + (12 if ampm.lower() == "pm" else 0)
        if hour < 24 and minute < 60:
            return f"{hour:02d}:{minute:02d}"
    return received.strftime("%H:%M")


def _name_from_vpa(vpa: str) -> str:
    handle = vpa.split("@")[0]
    if len(re.sub(r"[^0-9]", "", handle)) >= 8:
        return "UPI transfer to a phone number"
    words = []
    for w in re.split(r"[._\-0-9]+", handle.lower()):
        if w.endswith("upi") and len(w) > 5:
            w = w[:-3]
        if len(w) > 1 and w not in _GATEWAY_WORDS:
            words.append(w)
    return " ".join(w.capitalize() for w in words[:3]) or "UPI payee"


def _merchant(sentence: str, full: str, direction: str) -> str:
    if re.search(r"\batm\b|cash withdrawal", sentence, re.I):
        return "ATM cash withdrawal"
    m = _VPA.search(sentence) or _VPA.search(full)
    if m:
        return _clean(m.group(2)) if m.group(2) else _name_from_vpa(m.group(1))
    for pattern in ((_AT, _TO) if direction == "debit" else (_FROM, _TO, _AT)):
        for m in pattern.finditer(sentence):
            name = _TRAILING_NOISE.sub("", _clean(m.group(1))).strip(" .-*/")
            if name and name.lower() not in _STOPWORDS and not re.fullmatch(r"[Xx*]*\d*", name) \
                    and not name.lower().startswith(("your ", "a/c", "account", "card")):
                return name
    m = _UPI_NARRATION.search(full)
    if m:
        return _TRAILING_NOISE.sub("", _clean(m.group(1))).strip(" .-")
    return "Unknown payee"


def _mode(text: str) -> str:
    lower = text.lower()
    if "atm" in lower or "cash withdrawal" in lower:
        return "ATM"
    if "upi" in lower or "vpa" in lower:
        return "UPI"
    if "card" in lower:
        return "Card"
    if re.search(r"\b(neft|imps|rtgs)\b", lower):
        return "Bank transfer"
    if re.search(r"\b(nach|ecs|auto-?debit|si\b|standing instruction)", lower):
        return "Auto-debit"
    return "Bank"


def parse_alert(subject: str, body: str, received: datetime) -> Parsed | None:
    full = _clean(f"{subject}\n{body}")
    if not _AMOUNT.search(full):
        return None
    if _SKIP.search(full) and not re.search(r"\b(?:has been|is|was) (?:debited|credited)\b", full, re.I):
        return None

    chosen, amount, direction = None, None, None
    for sentence in [_clean(subject)] + _sentences(body):
        has_debit, has_credit_to_you = _DEBIT.search(sentence), _CREDIT_TO_YOU.search(sentence)
        if not (has_debit or has_credit_to_you or _CREDIT.search(sentence)):
            continue
        value = _pick_amount(sentence)
        if value is None:
            continue
        chosen, amount = sentence, value
        direction = "credit" if has_credit_to_you or not has_debit else "debit"
        break
    if chosen is None:
        return None

    when = _parse_date(chosen + " " + full, received)
    clock = _parse_time(chosen, received)
    account_match = _ACCOUNT.search(chosen) or _ACCOUNT.search(full)
    account = f"XX{account_match.group(1)}" if account_match else ""
    merchant = _merchant(chosen, full, direction)[:60]
    ref = _UPI_REF.search(full)
    key = ref.group(1) if ref else merchant_key(merchant)
    fingerprint = hashlib.sha256(f"{when}|{amount:.2f}|{direction}|{account}|{key}".encode()).hexdigest()[:20]
    if direction == "debit":
        kind = "expense"
    else:
        kind = "refund" if re.search(r"\b(?:refund|reversal|reversed|cashback)", chosen, re.I) else "income"
    return Parsed(
        date=when.isoformat(),
        time=clock,
        amount=round(amount, 2),
        direction=direction,
        kind=kind,
        merchant=merchant,
        mode=_mode(full),
        account=account,
        context=_mask_digits(chosen)[:240],
        fingerprint=fingerprint,
    )
