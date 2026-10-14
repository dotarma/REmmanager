"""Resident Evil catalog and bounded, read-only install discovery."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Game:
    key: str
    title: str
    steam_id: str
    nexus: str
    exe: str
    year: int
    badge: str


GAMES = (
    Game("re2", "Resident Evil 2", "883710", "residentevil22019", "re2.exe", 2019, "02"),
    Game("re3", "Resident Evil 3", "952060", "residentevil32020", "re3.exe", 2020, "03"),
    Game("re4", "Resident Evil 4", "2050650", "residentevil42023", "re4.exe", 2023, "04"),
    Game("re7", "Resident Evil 7: Biohazard", "418370", "residentevil7", "re7.exe", 2017, "VII"),
    Game("re8", "Resident Evil Village", "1196590", "residentevilvillage", "re8.exe", 2021, "VIII"),
    Game("re9", "Resident Evil Requiem", "3764200", "residentevilrequiem", "re9.exe", 2026, "IX"),
)
CATALOG = {g.key: g for g in GAMES}


@dataclass(frozen=True)
class Installation:
    game: Game
    path: Path
    source: str = "Thủ công"

    @property
    def id(self) -> str:
        canonical = os.path.normcase(str(self.path.resolve())).casefold()
        return self.game.key + "-" + hashlib.sha256(canonical.encode()).hexdigest()[:12]

    @property
    def available(self) -> bool:
        return (self.path / self.game.exe).is_file()

    def serialize(self) -> dict:
        return {"game": self.game.key, "path": str(self.path), "source": self.source}

    @classmethod
    def deserialize(cls, data: dict) -> Installation:
        return cls(CATALOG[data["game"]], Path(data["path"]), data.get("source", "Thủ công"))


def parse_vdf(text: str) -> dict:
    # Steam's quoted KeyValues subset; unlike unicode_escape this preserves Unicode paths.
    tokens = re.finditer(r'"((?:\\.|[^"\\])*)"|([{}])|(//[^\n]*)', text)
    values = [re.sub(r'\\([\\"])', r'\1', t[1]) if t[2] is None else t[2]
              for t in tokens if t[3] is None]
    pos = 0

    def obj() -> dict:
        nonlocal pos
        result = {}
        while pos < len(values):
            key = values[pos]
            pos += 1
            if key == "}":
                return result
            if pos >= len(values):
                break
            value = values[pos]
            pos += 1
            result[key] = obj() if value == "{" else value
        return result

    return obj()


def identify(path: Path, source: str = "Thủ công") -> Installation | None:
    path = Path(path)
    if path.is_file():
        path = path.parent
    for game in GAMES:
        if (path / game.exe).is_file():
            return Installation(game, path.resolve(), source)
    return None


def steam_roots() -> list[Path]:
    roots = []
    if os.name == "nt":
        import winreg
        for hive, key, name in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        ):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    roots.append(Path(winreg.QueryValueEx(handle, name)[0]))
            except OSError:
                pass
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        if os.environ.get(env):
            roots.append(Path(os.environ[env]) / "Steam")
    return list(dict.fromkeys(roots))


def discover(roots: list[Path] | None = None, epic_manifests: Path | None = None) -> list[Installation]:
    installs: dict[str, Installation] = {}
    libraries: set[Path] = set(steam_roots() if roots is None else roots)
    for root in list(libraries):
        try:
            data = parse_vdf((root / "steamapps/libraryfolders.vdf").read_text(encoding="utf-8-sig"))
            for key, value in data.get("libraryfolders", {}).items():
                if key.isdigit():
                    path = value.get("path") if isinstance(value, dict) else value
                    if path:
                        libraries.add(Path(path))
        except (OSError, ValueError, AttributeError):
            continue
    for library in libraries:
        for game in GAMES:
            try:
                manifest = library / "steamapps" / f"appmanifest_{game.steam_id}.acf"
                state = parse_vdf(manifest.read_text(encoding="utf-8-sig"))["AppState"]
                folder = library / "steamapps/common" / state["installdir"]
                # Treat manifests as data; an invalid install path must not escape common/.
                folder.resolve().relative_to((library / "steamapps/common").resolve())
                install = identify(folder, "Steam")
                if install and install.game == game:
                    installs[install.id] = install
            except (OSError, KeyError, ValueError, TypeError):
                continue
    if epic_manifests is None and os.environ.get("PROGRAMDATA"):
        epic_manifests = Path(os.environ["PROGRAMDATA"]) / "Epic/EpicGamesLauncher/Data/Manifests"
    if epic_manifests:
        try:
            manifests = list(epic_manifests.glob("*.item"))
        except OSError:
            manifests = []
        for manifest in manifests:
            try:
                data = json.loads(manifest.read_text(encoding="utf-8-sig"))
                install = identify(Path(data["InstallLocation"]), "Epic Games")
                if install:
                    installs[install.id] = install
            except (OSError, ValueError, KeyError, TypeError):
                continue
    return sorted(installs.values(), key=lambda i: (i.game.year, str(i.path)))


@dataclass(frozen=True)
class FrameworkStatus:
    state: str
    detail: str
    loose_files: bool = False
    pak_directory: bool = False
    pak_enabled: bool = False

    @property
    def present(self) -> bool:
        return self.state == "detected"


def framework_status(root: Path) -> FrameworkStatus:
    dll = root / "dinput8.dll"
    if not dll.is_file():
        return FrameworkStatus("missing", "Chưa tìm thấy dinput8.dll trong thư mục game.")
    marker = False
    pak_marker = False
    pak_path = False
    try:
        # Identify the binary itself: stale config/log files are not proof of an installed loader.
        with dll.open("rb") as stream:
            overlap = b""
            for _ in range(256):
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                data = (overlap + chunk).lower()
                if b"reframework" in data or "REFramework".encode("utf-16le").lower() in data:
                    marker = True
                pak_marker |= b"loadpakdirectory" in data or "LoadPakDirectory".encode("utf-16le").lower() in data
                pak_path |= b"pak_mods" in data or "pak_mods".encode("utf-16le") in data
                overlap = data[-64:]
    except OSError:
        return FrameworkStatus("unknown", "Không đọc được dinput8.dll; kiểm tra quyền truy cập.")
    loose = False
    pak_enabled = True  # REFramework defaults LoadPakDirectory to true.
    try:
        config = (root / "re2_fw_config.txt").read_text(encoding="utf-8-sig")
        loose = bool(re.search(r"(?mi)^\s*LooseFileLoader_Enabled\s*=\s*(true|1)\s*$", config))
        pak_setting = re.search(r"(?mi)^\s*(?:\w+_)?LoadPakDirectory\s*=\s*(true|false|1|0)\s*$", config)
        if pak_setting:
            pak_enabled = pak_setting[1].lower() in ("true", "1")
    except OSError:
        pass
    if marker:
        install = identify(root)
        # The upstream loader gates this feature at TDB >= 81. Of this catalog,
        # Requiem is the supported game; universal DLL strings alone prove no compatibility.
        pak_directory = bool(pak_marker and pak_path and install and install.game.key == "re9")
        return FrameworkStatus("detected", "Có dấu hiệu REFramework trong dinput8.dll; cần mở game để xác nhận tương thích.", loose, pak_directory, pak_directory and pak_enabled)
    return FrameworkStatus("unknown", "Có dinput8.dll nhưng chưa xác minh được là REFramework.", loose)
