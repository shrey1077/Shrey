"""Binds the vault to this Windows account on this PC.

A random device secret is protected with Windows DPAPI, which only the same Windows user on the
same machine can unprotect. The vault key needs both this secret and the passphrase, so a copied
vault file is useless on any other machine or account, even with the passphrase.
"""

from __future__ import annotations

import ctypes
import os
import sys

from .paths import dev_mode

_ENTROPY = b"andy/v1/device-binding"
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class DeviceBindingError(Exception):
    pass


if sys.platform == "win32":
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _take(blob: _Blob) -> bytes:
        try:
            return ctypes.string_at(blob.pbData, blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob.pbData)

    def _dpapi(data: bytes, protect: bool) -> bytes:
        crypt32 = ctypes.windll.crypt32
        # The buffers must outlive the call, so they stay in local variables.
        data_buf = ctypes.create_string_buffer(data, len(data))
        entropy_buf = ctypes.create_string_buffer(_ENTROPY, len(_ENTROPY))
        src = _Blob(len(data), ctypes.cast(data_buf, ctypes.POINTER(ctypes.c_char)))
        entropy = _Blob(len(_ENTROPY), ctypes.cast(entropy_buf, ctypes.POINTER(ctypes.c_char)))
        out = _Blob()
        fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        desc = "Andy device key" if protect else None
        ok = fn(ctypes.byref(src), desc, ctypes.byref(entropy), None, None,
                _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out))
        if not ok:
            raise DeviceBindingError("Windows could not unlock the device key. Is this the same PC and Windows user?")
        return _take(out)


def new_secret() -> tuple[str, bytes, bytes]:
    """Return (method, stored_blob, secret)."""
    secret = os.urandom(32)
    if sys.platform == "win32":
        return "dpapi", _dpapi(secret, True), secret
    if dev_mode():
        return "dev-insecure", secret, secret
    raise DeviceBindingError("Andy only runs on Windows. Set ANDY_DEV=1 for development with test data only.")


def unprotect(method: str, blob: bytes) -> bytes:
    if method == "dpapi":
        if sys.platform != "win32":
            raise DeviceBindingError("This vault is bound to a Windows PC.")
        return _dpapi(blob, False)
    if method == "dev-insecure" and dev_mode():
        return blob
    raise DeviceBindingError("This vault was created in development mode and cannot be opened here.")
