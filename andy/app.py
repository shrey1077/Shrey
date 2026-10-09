"""Andy's window: a native Windows window (WebView2) around the local interface.

- No web server and no open port: the page is loaded from memory and talks to Python through
  pywebview's in-process bridge.
- Strict Content-Security-Policy with a fresh nonce per launch.
- Private browsing mode, no dev tools, no context menu.
- Other apps can't screenshot or screen-record the window (Windows display affinity).
- Locks itself after the idle time set in Security, and when the window closes.
"""

from __future__ import annotations

import ctypes
import secrets
import sys
import threading
import time
import webbrowser
from pathlib import Path

from . import paths
from .service import AndyService, ServiceError

UI = Path(__file__).resolve().parent / "ui"
LINKS = {"apppasswords": "https://myaccount.google.com/apppasswords",
         "twostep": "https://myaccount.google.com/signinoptions/twosv"}


def build_page(nonce: str) -> str:
    page = (UI / "index.html").read_text(encoding="utf-8")
    return (page.replace("{{NONCE}}", nonce)
                .replace("/*{{CSS}}*/", (UI / "app.css").read_text(encoding="utf-8"))
                .replace("/*{{JS}}*/", (UI / "app.js").read_text(encoding="utf-8"))
                .replace("<!--{{LOGO}}-->", (UI / "logo.svg").read_text(encoding="utf-8")))


class Api:
    """Everything the page may call. Names starting with _ are not exposed to the page."""

    def __init__(self, service: AndyService):
        self._service = service

    def _call(self, fn, *args, touch: bool = True):
        try:
            if touch and self._service.vault.unlocked:
                self._service.touch()
            return {"ok": True, "data": fn(*args)}
        except ServiceError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:  # never leak internals or data to the page
            return {"ok": False, "error": "Something went wrong inside Andy. Your data is unchanged."}

    # vault
    def status(self): return self._call(self._service.status, touch=False)
    def create_vault(self, passphrase, confirm): return self._call(self._service.create, str(passphrase), str(confirm))
    def confirm_recovery(self, last_group): return self._call(self._service.confirm_recovery, str(last_group))
    def unlock(self, passphrase): return self._call(self._service.unlock, str(passphrase), touch=False)
    def recover(self, code, passphrase, confirm): return self._call(self._service.recover, str(code), str(passphrase), str(confirm))
    def lock(self): return self._call(self._service.lock, touch=False)
    def ping(self): return self._call(lambda: True)

    # profile
    def get_profile(self): return self._call(self._service.get_profile)
    def save_profile(self, profile): return self._call(self._service.save_profile, profile)
    def suggested_budgets(self): return self._call(self._service.suggested_budgets)
    def save_budgets(self, budgets): return self._call(self._service.save_budgets, budgets)
    def finish_onboarding(self): return self._call(self._service.finish_onboarding)

    # expenses
    def overview(self): return self._call(self._service.overview)
    def view(self, mode, anchor=None): return self._call(self._service.view, str(mode), anchor)
    def insights(self): return self._call(self._service.insights)
    def add_transaction(self, fields): return self._call(self._service.add_transaction, fields)
    def update_transaction(self, tx_id, changes): return self._call(self._service.update_transaction, str(tx_id), changes)
    def delete_transaction(self, tx_id): return self._call(self._service.delete_transaction, str(tx_id))

    # gmail
    def gmail_connect(self, address, app_password): return self._call(self._service.gmail_connect, str(address), str(app_password))
    def gmail_disconnect(self): return self._call(self._service.gmail_disconnect)
    def gmail_sync(self): return self._call(self._service.gmail_sync)

    # donna
    def donna_pair(self, passphrase): return self._call(self._service.donna_pair, str(passphrase or ""))
    def donna_unpair(self, passphrase): return self._call(self._service.donna_unpair, str(passphrase or ""))
    def donna_check(self): return self._call(self._service.donna_check)
    def donna_requests(self): return self._call(self._service.donna_requests)
    def donna_decide(self, request_id, decision, note="", passphrase=None):
        return self._call(self._service.donna_decide, str(request_id), str(decision), str(note or ""), passphrase)

    # tax, settings, security
    def tax_overview(self): return self._call(self._service.tax_overview)
    def save_settings(self, settings): return self._call(self._service.save_settings, settings)
    def change_passphrase(self, old, new, confirm): return self._call(self._service.change_passphrase, str(old), str(new), str(confirm))
    def audit_log(self): return self._call(self._service.audit_log)

    def open_link(self, name):
        url = LINKS.get(str(name))
        if not url:
            return {"ok": False, "error": "Unknown link."}
        webbrowser.open(url)
        return {"ok": True, "data": True}


def _exclude_from_capture(window) -> None:
    """Ask Windows to keep this window out of screenshots and screen recordings by other apps."""
    if not paths.IS_WINDOWS:
        return
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
        hwnd = window.native.Handle.ToInt64()
        user32.SetWindowDisplayAffinity(hwnd, 0x11)  # WDA_EXCLUDEFROMCAPTURE
    except Exception:
        pass


def _watch(service: AndyService, window) -> None:
    """Auto-lock after idle time, and check Donna's inbox while unlocked."""
    last_donna = 0.0
    while True:
        time.sleep(5)
        try:
            if not service.vault.unlocked:
                continue
            minutes = service.vault.data.get("settings", {}).get("auto_lock_minutes", 5)
            if service.idle_seconds() > minutes * 60:
                service.lock()
                window.evaluate_js("window.andy && window.andy.onLocked()")
                continue
            if time.monotonic() - last_donna > 30 and service.vault.data.get("onboarded"):
                last_donna = time.monotonic()
                result = service.donna_check()
                if result["new"]:
                    window.evaluate_js(f"window.andy && window.andy.onDonna({int(result['new'])})")
        except Exception:
            continue


def _single_instance():
    """Hold an exclusive lock so two copies of Andy never write the vault at once."""
    handle = open(paths.data_dir() / "andy.lock", "a+")
    try:
        if paths.IS_WINDOWS:
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return handle


def main() -> int:
    if not paths.IS_WINDOWS and not paths.dev_mode():
        print("Andy runs on Windows. For development with test data only, set ANDY_DEV=1.", file=sys.stderr)
        return 1
    instance = _single_instance()
    if instance is None:
        print("Andy is already running.", file=sys.stderr)
        return 1

    import webview  # imported late so tests and tools don't need it

    service = AndyService()
    window = webview.create_window("Andy", html=build_page(secrets.token_urlsafe(18)), js_api=Api(service),
                                   width=1360, height=880, min_size=(1000, 680), background_color="#05070D")
    window.events.shown += lambda: _exclude_from_capture(window)
    window.events.closing += lambda: service.lock()
    threading.Thread(target=_watch, args=(service, window), daemon=True).start()
    webview.start(private_mode=True, debug=False)
    service.lock()
    return 0
