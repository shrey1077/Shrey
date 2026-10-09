"""Where Andy keeps its files on this machine."""

from __future__ import annotations

import os
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"


def dev_mode() -> bool:
    """Development mode runs on non-Windows systems with a weaker device binding. Never use it for real data."""
    return os.environ.get("ANDY_DEV") == "1"


def data_dir() -> Path:
    override = os.environ.get("ANDY_HOME")
    if override:
        base = Path(override)
    elif IS_WINDOWS:
        base = Path(os.environ["LOCALAPPDATA"]) / "Andy"
    else:
        base = Path.home() / ".local" / "share" / "andy-dev"
    base.mkdir(parents=True, exist_ok=True)
    if not IS_WINDOWS:
        os.chmod(base, 0o700)
    return base


def vault_path() -> Path:
    return data_dir() / "vault.andy"


def donna_dirs() -> tuple[Path, Path]:
    inbox = data_dir() / "donna" / "inbox"
    outbox = data_dir() / "donna" / "outbox"
    for d in (inbox, outbox):
        d.mkdir(parents=True, exist_ok=True)
    return inbox, outbox
