"""Opt-in NXM registration and encrypted, per-user single-instance inbox."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import uuid

from .credentials import crypt
from .nexus import parse_nxm
from .safety import ModError


def enqueue(root: Path, url: str):
    parse_nxm(url)
    inbox = root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    temp = inbox / (uuid.uuid4().hex + ".tmp")
    try:
        temp.write_bytes(crypt(url.encode("utf-8")))
        temp.replace(temp.with_suffix(".nxm"))
    finally:
        temp.unlink(missing_ok=True)


def receive(root: Path):
    inbox = root / "inbox"
    if not inbox.exists():
        return
    for item in sorted(inbox.glob("*.nxm"))[:10]:
        try:
            yield crypt(item.read_bytes(), decrypt=True).decode("utf-8")
        finally:
            item.unlink(missing_ok=True)


def register(root: Path):
    if os.name != "nt":
        raise ModError("Đăng ký nxm:// chỉ hỗ trợ Windows.")
    import winreg
    if getattr(sys, "frozen", False):
        args = [sys.executable]
    else:
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        interpreter = str(pythonw if pythonw.exists() else Path(sys.executable))
        script = Path(__file__).resolve().parent.parent / "main.py"
        args = [interpreter, str(script)] if script.is_file() else [interpreter, "-m", "re_manager"]
    command = subprocess.list2cmdline([*args, "--data-dir", str(root), "--nxm", "%1"])
    # list2cmdline does not quote %1 without spaces, but Windows protocol placeholders must be quoted.
    command = command.rsplit("%1", 1)[0] + '"%1"'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\nxm") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:Nexus Mod Manager Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\nxm\shell\open\command") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
