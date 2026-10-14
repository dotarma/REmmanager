"""Filesystem primitives shared by archive import and deployment."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile


class ModError(Exception):
    """An actionable error suitable for displaying to the user."""


def relative_name(name: str) -> str:
    value = name.replace("\\", "/")
    path = PurePosixPath(value)
    parts = value.split("/")
    reserved = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.I)
    if (not value or path.is_absolute() or any(
        part in ("", ".", "..") or part[-1:] in (" ", ".")
        or re.search(r'[<>:"|?*\x00-\x1f]', part) or reserved.match(part)
        for part in parts
    )):
        raise ModError(f"Đường dẫn không an toàn: {name!r}")
    return path.as_posix()


def safe_target(root: Path, name: str) -> Path:
    target = root / relative_name(name)
    current = target
    while current != root:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ModError(f"Từ chối liên kết trong đường dẫn: {name}")
        current = current.parent
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ModError("Đường dẫn vượt ra ngoài thư mục cho phép.") from exc
    return target


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".json-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".remm-", dir=target.parent)
    os.close(fd)
    try:
        shutil.copyfile(source, name)
        with open(name, "r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)


class FileLock:
    """OS lock released on process exit; the lock file itself may safely persist."""
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("a+b")
        self.file.seek(0, 2)
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            raise ModError("Một phiên Mod Manager khác đang dùng thư viện này.") from exc

    def close(self):
        if self.file.closed:
            return
        self.file.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()
