"""Andy's encrypted vault: the only place Andy stores anything.

File layout (JSON, %LOCALAPPDATA%\\Andy\\vault.andy):
- `device`: a random device secret, protected by Windows DPAPI (see device.py).
- `wraps.primary`: the data key, AES-256-GCM encrypted under
  HKDF(scrypt(passphrase) + device secret). Needs the passphrase AND this PC.
- `wraps.recovery`: the same data key under scrypt(recovery code). The recovery code is shown
  once, kept on paper, and moves the vault to a new PC.
- `data`: the vault contents, AES-256-GCM encrypted under the data key.

Nothing is ever written in plaintext. The passphrase is never stored.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import secrets
import shutil
import threading
import time
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from . import device

FORMAT = "andy-vault"
VERSION = 1
SCRYPT_PARAMS = {"n": 2**17, "r": 8, "p": 1}  # about 128 MB of memory per guess
_RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L
_COMMON = {"password", "passphrase", "andy", "shrey", "qwerty", "letmein", "welcome", "admin", "india"}


class VaultError(Exception):
    pass


class WrongSecret(VaultError):
    pass


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


def _scrypt(secret: str, salt: bytes, params: dict) -> bytes:
    return hashlib.scrypt(secret.encode("utf-8"), salt=salt, n=params["n"], r=params["r"], p=params["p"],
                          maxmem=512 * 1024 * 1024, dklen=32)


def _hkdf(material: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(material)


def _seal(key: bytes, plaintext: bytes, aad: bytes) -> dict:
    nonce = os.urandom(12)
    return {"nonce": _b64(nonce), "ct": _b64(AESGCM(key).encrypt(nonce, plaintext, aad))}


def _open(key: bytes, box: dict, aad: bytes) -> bytes:
    return AESGCM(key).decrypt(_unb64(box["nonce"]), _unb64(box["ct"]), aad)


def new_recovery_code() -> str:
    """40 characters from a 31-letter alphabet: about 198 bits, grouped for writing down."""
    chars = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(40))
    return "-".join(chars[i:i + 5] for i in range(0, 40, 5))


def normalize_recovery_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def passphrase_problems(passphrase: str) -> list[str]:
    problems = []
    if len(passphrase) < 12:
        problems.append("Use at least 12 characters.")
    classes = sum(any(test(ch) for ch in passphrase) for test in (str.islower, str.isupper, str.isdigit,
                                                                    lambda c: not c.isalnum()))
    if len(passphrase) < 20 and classes < 3:
        problems.append("Mix upper case, lower case, digits and symbols, or use a passphrase of 20+ characters.")
    if passphrase.lower().strip() in _COMMON or len(set(passphrase)) < 6:
        problems.append("That passphrase is too easy to guess.")
    return problems


def default_data() -> dict:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "schema": 1,
        "created": now,
        "onboarded": False,
        "recovery_confirmed": False,
        "profile": {},
        "budgets": {},
        "settings": {"auto_lock_minutes": 5, "approval_passphrase_above": 5000},
        "gmail": {"address": "", "app_password": "", "last_sync": None, "seen": []},
        "transactions": [],
        "rules": {},
        "donna": {"key": "", "paired_at": None, "seen": {}, "requests": []},
        "audit": [],
    }


class Vault:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._dek: bytearray | None = None
        self._data: dict | None = None
        self._failures = 0

    # ----- state -----
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def unlocked(self) -> bool:
        return self._dek is not None

    @property
    def data(self) -> dict:
        if self._data is None:
            raise VaultError("Andy is locked.")
        return self._data

    # ----- create / unlock -----
    def create(self, passphrase: str) -> str:
        problems = passphrase_problems(passphrase)
        if problems:
            raise VaultError(" ".join(problems))
        if self.exists():
            raise VaultError("A vault already exists on this PC.")
        with self._lock:
            method, blob, device_secret = device.new_secret()
            dek = os.urandom(32)
            recovery = new_recovery_code()
            header = {
                "format": FORMAT,
                "version": VERSION,
                "kdf": {"name": "scrypt", **SCRYPT_PARAMS},
                "device": {"method": method, "blob": _b64(blob)},
                "wraps": {},
            }
            header["wraps"]["primary"] = self._wrap_primary(dek, passphrase, device_secret)
            rsalt = os.urandom(16)
            rkey = _hkdf(_scrypt(normalize_recovery_code(recovery), rsalt, SCRYPT_PARAMS), b"andy/v1/recovery")
            header["wraps"]["recovery"] = {"salt": _b64(rsalt), **_seal(rkey, dek, b"andy/v1/wrap/recovery")}
            self._header = header
            self._dek = bytearray(dek)
            self._data = default_data()
            self._write()
            return recovery

    def _wrap_primary(self, dek: bytes, passphrase: str, device_secret: bytes) -> dict:
        salt = os.urandom(16)
        key = _hkdf(_scrypt(passphrase, salt, SCRYPT_PARAMS) + device_secret, b"andy/v1/primary")
        return {"salt": _b64(salt), **_seal(key, dek, b"andy/v1/wrap/primary")}

    def _read_header(self) -> dict:
        try:
            header = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise VaultError("The vault file is missing or damaged.") from exc
        if header.get("format") != FORMAT or header.get("version") != VERSION:
            raise VaultError("This is not an Andy vault, or it needs a newer Andy.")
        return header

    def _primary_key(self, header: dict, passphrase: str) -> bytes:
        dev = header["device"]
        device_secret = device.unprotect(dev["method"], _unb64(dev["blob"]))
        wrap = header["wraps"]["primary"]
        params = {k: header["kdf"][k] for k in ("n", "r", "p")}
        return _hkdf(_scrypt(passphrase, _unb64(wrap["salt"]), params) + device_secret, b"andy/v1/primary")

    def unlock(self, passphrase: str) -> None:
        with self._lock:
            if self._failures:
                time.sleep(min(30, 2 ** (self._failures - 1)))  # slows guessing at the keyboard
            header = self._read_header()
            try:
                key = self._primary_key(header, passphrase)
                dek = _open(key, header["wraps"]["primary"], b"andy/v1/wrap/primary")
            except InvalidTag:
                self._failures += 1
                raise WrongSecret("That passphrase is not right.") from None
            self._load(header, dek)
            failures, self._failures = self._failures, 0
            self.audit("unlock", f"{failures} failed attempt(s) before this" if failures else "")
            self._write()

    def recover(self, code: str, new_passphrase: str) -> None:
        """Open the vault with the recovery code (for example on a new PC) and set a new passphrase."""
        problems = passphrase_problems(new_passphrase)
        if problems:
            raise VaultError(" ".join(problems))
        with self._lock:
            header = self._read_header()
            wrap = header["wraps"]["recovery"]
            params = {k: header["kdf"][k] for k in ("n", "r", "p")}
            key = _hkdf(_scrypt(normalize_recovery_code(code), _unb64(wrap["salt"]), params), b"andy/v1/recovery")
            try:
                dek = _open(key, wrap, b"andy/v1/wrap/recovery")
            except InvalidTag:
                raise WrongSecret("That recovery code is not right.") from None
            method, blob, device_secret = device.new_secret()
            header["device"] = {"method": method, "blob": _b64(blob)}
            header["wraps"]["primary"] = self._wrap_primary(dek, new_passphrase, device_secret)
            self._load(header, dek)
            self.audit("recovered", "Opened with the recovery code; new passphrase set on this PC")
            self._write()

    def _load(self, header: dict, dek: bytes) -> None:
        try:
            plaintext = _open(dek, header["data"], b"andy/v1/data")
        except InvalidTag:
            raise VaultError("The vault contents failed their integrity check. It may have been tampered with.") from None
        self._header = header
        self._dek = bytearray(dek)
        self._data = json.loads(plaintext.decode("utf-8"))

    def verify_passphrase(self, passphrase: str) -> bool:
        """Step-up check for sensitive actions while unlocked."""
        if not self.unlocked:
            return False
        try:
            key = self._primary_key(self._header, passphrase)
            dek = _open(key, self._header["wraps"]["primary"], b"andy/v1/wrap/primary")
        except InvalidTag:
            self.audit("step-up failed", "Wrong passphrase for a protected action")
            return False
        return secrets.compare_digest(dek, bytes(self._dek))

    def change_passphrase(self, old: str, new: str) -> None:
        problems = passphrase_problems(new)
        if problems:
            raise VaultError(" ".join(problems))
        with self._lock:
            if not self.verify_passphrase(old):
                raise WrongSecret("The current passphrase is not right.")
            dev = self._header["device"]
            device_secret = device.unprotect(dev["method"], _unb64(dev["blob"]))
            self._header["wraps"]["primary"] = self._wrap_primary(bytes(self._dek), new, device_secret)
            self.audit("passphrase changed", "")
            self._write()

    def lock(self) -> None:
        with self._lock:
            if self._dek is not None:
                for i in range(len(self._dek)):  # best effort: Python may hold other copies
                    self._dek[i] = 0
            self._dek = None
            self._data = None

    # ----- persistence -----
    def save(self) -> None:
        with self._lock:
            if not self.unlocked:
                raise VaultError("Andy is locked.")
            self._write()

    def _write(self) -> None:
        payload = json.dumps(self._data, separators=(",", ":")).encode("utf-8")
        header = copy.deepcopy(self._header)
        header["data"] = _seal(bytes(self._dek), payload, b"andy/v1/data")
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(header), encoding="utf-8")
        if self.path.exists():
            shutil.copyfile(self.path, self.path.with_suffix(".bak"))  # the previous encrypted version
        os.replace(tmp, self.path)  # atomic: the vault file is always complete
        self._header = header

    # ----- audit -----
    def audit(self, event: str, detail: str = "") -> None:
        if self._data is None:
            return
        log = self._data.setdefault("audit", [])
        log.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, "detail": detail[:200]})
        del log[:-500]
