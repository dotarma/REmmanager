"""Fetch official Google Sans Flex and Steam game artwork for the desktop UI."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1] / "re_manager/assets"
ROOT.mkdir(parents=True, exist_ok=True)


def fetch(url, limit=50 * 1024**2):
    request = Request(url, headers={"User-Agent": "REmmanager-AssetBuilder/0.3"})
    with urlopen(request, timeout=45) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Asset exceeded size limit")
    return data


def main():
    sources = []
    fonts = ROOT / "fonts"
    fonts.mkdir(exist_ok=True)
    repo = "https://api.github.com/repos/googlefonts/googlesans-flex"
    releases = json.loads(fetch(repo + "/releases"))
    candidates = [a for r in releases for a in r.get("assets", [])
                  if a["name"].endswith(".zip") and "workspace" not in a["name"].lower()]
    if not candidates:
        raise ValueError("No public Google Sans Flex font release found")
    asset = candidates[0]
    print("Font release:", asset["name"], flush=True)
    archive = zipfile.ZipFile(io.BytesIO(fetch(asset["browser_download_url"])))
    members = [m for m in archive.infolist() if m.filename.lower().endswith(".ttf")
               and "italic" not in m.filename.lower() and m.file_size < 20 * 1024**2]
    if not members:
        raise ValueError("Release does not contain an upright TrueType font")
    # Prefer the full variable master over static or workspace-specific instances.
    members.sort(key=lambda m: ("variable" not in m.filename.lower() and "[" not in m.filename,
                                "google" not in m.filename.lower(), len(m.filename)))
    data = archive.read(members[0])
    (fonts / "GoogleSansFlex.ttf").write_bytes(data)
    sources.append({"asset": "fonts/GoogleSansFlex.ttf", "source": asset["browser_download_url"],
                    "member": members[0].filename, "sha256": hashlib.sha256(data).hexdigest()})
    for name in ("OFL.txt", "TRADEMARKS.txt"):
        url = "https://raw.githubusercontent.com/googlefonts/googlesans-flex/main/" + name
        (fonts / name).write_bytes(fetch(url))
    banners = ROOT / "banners"
    banners.mkdir(exist_ok=True)
    games = {"re2": "883710", "re3": "952060", "re4": "2050650", "re7": "418370", "re8": "1196590", "re9": "3764200"}
    def banner(item):
        key, app_id = item
        for filename in ("library_hero.jpg", "header.jpg"):
            url = f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/{filename}"
            try:
                data = fetch(url, 8 * 1024**2)
                if not data.startswith(b"\xff\xd8"):
                    raise ValueError("Expected JPEG artwork")
                (banners / f"{key}.jpg").write_bytes(data)
                print("Banner:", key, len(data), "bytes", flush=True)
                return {"asset": f"banners/{key}.jpg", "source": url, "sha256": hashlib.sha256(data).hexdigest(),
                        "copyright": "CAPCOM / original rights holders; game identification artwork"}
            except Exception:
                if filename == "header.jpg":
                    raise
    with ThreadPoolExecutor(max_workers=4) as pool:
        sources.extend(pool.map(banner, games.items()))
    (ROOT / "sources.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    print("Bundled font, license and six game banners.")


if __name__ == "__main__":
    main()
