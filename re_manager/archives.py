"""Import supported mod payloads without executing archive contents."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import threading
import zipfile

from .safety import ModError, relative_name, safe_target

MAX_FILES = 100_000
MAX_BYTES = 16 * 1024**3
META_NAMES = {"modinfo.ini", "readme.md", "readme.txt", "readme", "license", "license.txt", "thumb.png", "screenshot.jpg", "preview.png", "desktop.ini"}


class Budget:
    def __init__(self):
        self.bytes = 0
        self.names: set[str] = set()
        self.lock = threading.Lock()

    def add(self, name: str, size: int = 0):
        name = relative_name(name)
        with self.lock:
            if name.casefold() in self.names:
                raise ModError(f"Archive có đường dẫn trùng nhau: {name}")
            self.names.add(name.casefold())
            if len(self.names) > MAX_FILES or size < 0 or size > MAX_BYTES:
                raise ModError("Archive vượt giới hạn số lượng hoặc dung lượng file.")
        return name

    def consume(self, count):
        with self.lock:
            self.bytes += count
            if self.bytes > MAX_BYTES:
                raise ModError("Tổng dữ liệu giải nén vượt giới hạn 16 GiB.")

    def copy(self, source, target: Path):
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            while chunk := source.read(1024 * 1024):
                self.consume(len(chunk))
                output.write(chunk)


def unpack(source: Path, dest: Path) -> None:
    budget = Budget()
    if source.is_symlink():
        raise ModError("Không nhập mod từ symbolic link.")
    if source.is_dir():
        for directory, dirs, files in os.walk(source, followlinks=False):
            base = Path(directory)
            for name in dirs + files:
                item = base / name
                if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
                    raise ModError("Thư mục mod chứa liên kết; hãy dùng thư mục file thật.")
            for name in files:
                item = base / name
                rel = budget.add(item.relative_to(source).as_posix(), item.stat().st_size)
                with item.open("rb") as stream:
                    budget.copy(stream, safe_target(dest, rel))
    elif source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            for member in archive.infolist():
                relative_name(member.filename.rstrip("/"))
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                    raise ModError("Archive chứa liên kết hoặc file đặc biệt.")
                if member.is_dir():
                    continue
                rel = budget.add(member.filename, member.file_size)
                with archive.open(member) as stream:
                    budget.copy(stream, safe_target(dest, rel))
    elif source.suffix.lower() == ".rar":
        try:
            import rarfile
        except ImportError as exc:
            raise ModError("Cài phần mở rộng archives hoặc giải nén RAR rồi thêm thư mục.") from exc
        with rarfile.RarFile(source) as archive:
            for member in archive.infolist():
                relative_name(member.filename.rstrip("/"))
                if member.is_symlink() or getattr(member, "file_redir", None):
                    raise ModError("RAR chứa liên kết không được hỗ trợ.")
                if member.isdir():
                    continue
                rel = budget.add(member.filename, member.file_size)
                with archive.open(member) as stream:
                    budget.copy(stream, safe_target(dest, rel))
    elif source.suffix.lower() == ".7z":
        _unpack_7z(source, dest, budget)
    elif source.suffix.lower() in (".lua", ".dll", ".pak"):
        rel = budget.add(source.name, source.stat().st_size)
        with source.open("rb") as stream:
            budget.copy(stream, safe_target(dest, rel))
    else:
        raise ModError("Hỗ trợ ZIP, thư mục, Lua, DLL, PAK; 7z/RAR cần phần mở rộng archives.")


def _unpack_7z(source: Path, dest: Path, budget: Budget):
    try:
        import py7zr
        from py7zr.io import Py7zIO, WriterFactory
    except ImportError as exc:
        raise ModError("Cài phần mở rộng archives hoặc giải nén 7z rồi thêm thư mục.") from exc

    class Sink(Py7zIO):
        def __init__(self, path):
            path.parent.mkdir(parents=True, exist_ok=True)
            self.stream = path.open("xb+")

        def write(self, data):
            budget.consume(len(data))
            return self.stream.write(data)

        def read(self, size=None):
            return self.stream.read(-1 if size is None else size)

        def seek(self, offset, whence=0):
            return self.stream.seek(offset, whence)

        def flush(self):
            self.stream.flush()

        def size(self):
            return os.fstat(self.stream.fileno()).st_size

    class Factory(WriterFactory):
        def __init__(self):
            self.sinks = []

        def create(self, filename):
            sink = Sink(safe_target(dest, budget.add(filename)))
            self.sinks.append(sink)
            return sink

    factory = Factory()
    try:
        with py7zr.SevenZipFile(source, mode="r") as archive:
            if archive.needs_password():
                raise ModError("Không hỗ trợ archive có mật khẩu.")
            # Custom sinks prevent the extractor from choosing arbitrary filesystem targets.
            for entry in archive.list():
                relative_name(entry.filename.rstrip("/"))
            for entry in archive.files:
                if entry.is_symlink or entry.is_junction:
                    raise ModError("7z chứa liên kết không được hỗ trợ.")
            archive.extractall(factory=factory)
    finally:
        for sink in factory.sinks:
            sink.stream.close()


def normalize(raw: Path, payload: Path) -> tuple[list[str], str, dict]:
    """Strip a single wrapper; do not silently combine optional mod variants."""
    root = raw
    while True:
        entries = list(root.iterdir())
        useful = [p for p in entries if p.name.casefold() not in META_NAMES and not p.name.startswith(".")]
        dirs = [p for p in useful if p.is_dir()]
        files = [p for p in useful if p.is_file()]
        if not files and len(dirs) == 1 and dirs[0].name.casefold() not in ("natives", "reframework", "autorun", "plugins", "paks", "pak_mods"):
            root = dirs[0]
        else:
            break
    metadata = {}
    info = root / "modinfo.ini"
    if info.is_file():
        # Fluffy's modinfo often has no INI section.
        for line in info.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                if key.strip().lower() in ("name", "version", "author", "description"):
                    metadata[key.strip().lower()] = value.strip()[:2000]
    mappings = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        parts = rel.split("/")
        if parts[0].startswith(".") or "__MACOSX" in parts or path.name.casefold() in META_NAMES:
            continue
        first = parts[0].casefold()
        if first == "natives" and len(parts) >= 3:
            target = "/".join(["natives", *parts[1:]])
        elif first == "reframework" and len(parts) >= 3 and parts[1].casefold() in ("autorun", "plugins", "data", "paks"):
            target = "/".join(["reframework", parts[1].lower(), *parts[2:]])
        elif first in ("autorun", "plugins") and len(parts) >= 2:
            target = "reframework/" + first + "/" + "/".join(parts[1:])
        elif len(parts) == 1 and path.suffix.lower() == ".lua":
            target = "reframework/autorun/" + path.name
        elif len(parts) == 1 and path.suffix.lower() == ".dll":
            target = "dinput8.dll" if path.name.lower() == "dinput8.dll" else "reframework/plugins/" + path.name
        elif path.suffix.lower() == ".pak" and (len(parts) == 1 or first == "pak_mods"):
            with path.open("rb") as stream:
                header = stream.read(16)
            if len(header) < 16 or header[:4] != b"KPKA":
                raise ModError("File PAK không có header KPKA hợp lệ của RE Engine.")
            # REFramework's directory loader requires a lowercase .pak extension.
            name = path.stem + ".pak"
            target = "/".join(["pak_mods", *parts[1:-1], name]) if first == "pak_mods" else "pak_mods/" + name
        elif path.suffix.lower() in (".md", ".txt", ".jpg", ".png", ".jpeg") and len(parts) == 1:
            continue
        else:
            raise ModError(f"Chưa xác định được vị trí cài '{rel}'. Chọn đúng thư mục biến thể chứa natives hoặc reframework.")
        mappings.append((path, relative_name(target)))
    if not mappings:
        raise ModError("Không tìm thấy payload mod hợp lệ.")
    seen = set()
    for source, rel in mappings:
        if rel.casefold() in seen:
            raise ModError(f"Payload trùng đường dẫn: {rel}")
        seen.add(rel.casefold())
        target = safe_target(payload, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    names = [rel for _, rel in mappings]
    if names == ["dinput8.dll"]:
        kind = "REFramework"
    elif all(n.startswith("pak_mods/") for n in names):
        kind = "PAK"
    elif any(n.startswith("pak_mods/") for n in names):
        kind = "Mixed / PAK"
    else:
        kind = "Natives" if any(n.startswith("natives/") for n in names) else "Script / Plugin"
    return names, kind, metadata
