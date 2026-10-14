"""Game process control scoped to the exact selected installation, never image name alone."""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import time

from .games import Installation
from .safety import ModError


def canonical(path) -> str:
    return os.path.normcase(str(Path(path).resolve())).casefold()


class GameProcesses:
    def __init__(self, psutil_module=None):
        if psutil_module is None:
            import psutil as psutil_module
        self.psutil = psutil_module
        self.launched = {}

    def matches(self, install: Installation):
        expected = canonical(install.path / install.game.exe)
        result = []
        for process in self.psutil.process_iter(["pid", "exe", "create_time"]):
            try:
                if process.info.get("exe") and canonical(process.info["exe"]) == expected:
                    result.append(process)
            except (self.psutil.NoSuchProcess, self.psutil.AccessDenied, OSError):
                continue
        return result

    def status(self, install: Installation):
        return {"running": bool(processes := self.matches(install)), "pids": [p.pid for p in processes]}

    def launch(self, install: Installation, steam=False, demo=False):
        if demo:
            raise ModError("Demo: sample game executables are not launched.")
        if not install.available:
            raise ModError("The game executable is missing.")
        if self.matches(install):
            return {"running": True, "already_running": True}
        if steam:
            os.startfile(f"steam://rungameid/{install.game.steam_id}")
            return {"launching": True}
        child = subprocess.Popen([str(install.path / install.game.exe)], cwd=install.path)
        self.launched[install.id] = child
        return {"launching": True, "pid": child.pid}

    def stop(self, install: Installation, force=False):
        processes = self.matches(install)
        if not processes:
            return {"stopped": True}
        snapshots = [(p.pid, p.create_time()) for p in processes]
        if force:
            for pid, created in snapshots:
                try:
                    current = self.psutil.Process(pid)
                    # Revalidate executable and creation time to defend against PID reuse.
                    if current.create_time() == created and canonical(current.exe()) == canonical(install.path / install.game.exe):
                        current.terminate()
                except self.psutil.NoSuchProcess:
                    pass
        elif os.name == "nt":
            user = ctypes.WinDLL("user32", use_last_error=True)
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
            pids = {pid for pid, _ in snapshots}
            def close_window(hwnd, _):
                pid = wintypes.DWORD()
                user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in pids:
                    user.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE: let the game exit normally.
                return True
            user.EnumWindows(callback_type(close_window), 0)
        deadline = time.monotonic() + (2 if force else 3)
        while time.monotonic() < deadline:
            if not self.matches(install):
                return {"stopped": True}
            time.sleep(0.1)
        return {"stopped": False, "needs_force": not force}
