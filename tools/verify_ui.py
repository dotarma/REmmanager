"""Run QA inside the native WinUI process; capture only its XAML tree."""
from pathlib import Path
import argparse
import subprocess

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--screenshots", type=Path, default=root / "artifacts/winui")
args = parser.parse_args()
args.screenshots.mkdir(parents=True, exist_ok=True)
executable = root / "dist/REmmanager.exe"
result = subprocess.run([str(executable), "--demo", "--qa", str(args.screenshots.resolve())], timeout=90)
report = args.screenshots / "verified.txt"
error = args.screenshots / "error.txt"
if result.returncode or error.exists() or not report.exists():
    raise SystemExit(error.read_text(encoding="utf-8") if error.exists() else "Native WinUI QA did not complete.")
print(report.read_text(encoding="utf-8"))
