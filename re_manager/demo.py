"""Explicit, isolated UI demo fixtures. Never used in the normal startup path."""
from pathlib import Path
import zipfile

from .games import CATALOG, Installation
from .safety import atomic_json


def populate(library):
    installs = []
    for key in ("re2", "re4", "re9"):
        game = CATALOG[key]
        path = library.root / "sample-games" / game.title
        path.mkdir(parents=True)
        (path / game.exe).write_bytes(b"DEMO ONLY - NOT AN EXECUTABLE")
        (path / "dinput8.dll").write_bytes(b"DEMO REFramework LoadPakDirectory pak_mods - NOT AN EXECUTABLE")
        (path / "re2_fw_config.txt").write_text("LooseFileLoader_Enabled=true\n", encoding="utf-8")
        installs.append(Installation(game, path, "Demo"))
    atomic_json(library.root / "settings.json", {"installations": [i.serialize() for i in installs]})
    for index, name in enumerate(("Camera controls", "Minimal HUD", "Photo mode helpers")):
        archive = library.root / f"sample-{index}.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("modinfo.ini", f"name={name} [DEMO]\nversion=1.0\nauthor=Demo fixture\n")
            package.writestr(f"reframework/autorun/demo_{index}.lua", "-- Demo fixture, no game functionality\n")
        library.import_mod(archive, installs[0])
    pak = library.root / "sample.pak"
    pak.write_bytes(b"KPKA" + bytes(12) + b"DEMO ONLY - NO GAME ASSETS")
    library.import_mod(pak, installs[-1])
