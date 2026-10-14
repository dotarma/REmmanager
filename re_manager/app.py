"""Source-tree launcher for the native REmmanager WinUI executable."""
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    executable = root / "dist/REmmanager.exe"
    if not executable.is_file():
        raise SystemExit("Build REmmanager first: powershell -File tools/build_winui.ps1")
    return subprocess.call([str(executable), *sys.argv[1:]])
