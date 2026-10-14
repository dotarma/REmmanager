"""Download portable, project-local .NET SDK and embeddable CPython for WinUI builds."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile
import io

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".build-tools"


def fetch(url, maximum=400 * 1024**2):
    request = Request(url, headers={"User-Agent": "REmmanager-Build/0.3"})
    with urlopen(request, timeout=120) as response:
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Download exceeds limit")
    return data


def extract(data, target):
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            (target / entry.filename).resolve().relative_to(target.resolve())
        archive.extractall(target)


def main():
    TOOLS.mkdir(exist_ok=True)
    sdk = TOOLS / "dotnet/dotnet.exe"
    if not sdk.exists():
        metadata = json.loads(fetch("https://builds.dotnet.microsoft.com/dotnet/release-metadata/8.0/releases.json"))
        release = next(r for r in metadata["releases"] if r.get("sdk", {}).get("version") == "8.0.425")
        file = next(f for f in release["sdk"]["files"] if f["rid"] == "win-x64" and f["name"].endswith(".zip"))
        print("Downloading .NET SDK", release["sdk"]["version"], flush=True)
        data = fetch(file["url"])
        if hashlib.sha512(data).hexdigest().lower() != file["hash"].lower():
            raise ValueError(".NET SDK hash mismatch")
        extract(data, sdk.parent)
    python = TOOLS / "python/python.exe"
    if not python.exists():
        # Official embeddable runtime, independent of the user's installed Python 3.15.
        version = "3.13.9"
        url = f"https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip"
        print("Downloading embedded CPython", version, flush=True)
        extract(fetch(url, 30 * 1024**2), python.parent)
    latest = "2.5.1"
    (TOOLS / "versions.json").write_text(json.dumps({"winappsdk": latest, "python": "3.13.9"}, indent=2), encoding="utf-8")
    print("Portable tools ready. Windows App SDK:", latest, flush=True)


if __name__ == "__main__":
    main()
