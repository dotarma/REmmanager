"""Staging, conflict detection and recoverable deployment transactions."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

from .archives import normalize, unpack
from .games import CATALOG, Installation, framework_status
from .safety import FileLock, ModError, atomic_copy, atomic_json, digest, relative_name, safe_target


def default_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
    legacy = base / "REEngineModManager"
    return legacy if legacy.is_dir() else base / "REmmanager"


def is_game_running(install: Installation) -> bool:
    if os.name != "nt":
        return False
    # Match image names, independent of the localised tasklist column headings.
    result = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {install.game.exe}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10,
    )
    if result.returncode:
        raise ModError("Không kiểm tra được game đang chạy. Đóng game và thử lại.")
    return f'"{install.game.exe}"' in result.stdout.lower()


class Library:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(self.root / "library.lock")
        try:
            for name in ("mods", "backups", "transactions", "downloads", "staging"):
                (self.root / name).mkdir(exist_ok=True)
            self.state_file = self.root / "library.json"
            self.state = self._read_state()
            self.recover()
        except BaseException:
            self.lock.close()
            raise

    def _read_state(self):
        if not self.state_file.exists():
            return {"schema": 1, "mods": {}, "deployments": {}}
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            if data.get("schema") != 1 or not isinstance(data["mods"], dict) or not isinstance(data["deployments"], dict):
                raise ValueError("schema")
            for key, mod in data["mods"].items():
                if not re.fullmatch(r"[0-9a-f]{32}", key) or mod["id"] != key or mod["game"] not in CATALOG:
                    raise ValueError("mod identity")
                for name, sha in mod["files"].items():
                    relative_name(name)
                    if not re.fullmatch(r"[0-9a-f]{64}", sha):
                        raise ValueError("payload digest")
            for key, entry in data["deployments"].items():
                if Installation.deserialize(entry).id != key or any(m not in data["mods"] for m in entry["mods"]):
                    raise ValueError("deployment identity")
            return data
        except (ValueError, KeyError, TypeError, AttributeError, ModError) as exc:
            raise ModError(f"Không đọc được thư viện {self.state_file}. Dữ liệu được giữ nguyên để phục hồi.") from exc

    def close(self):
        self.lock.close()

    def save(self):
        atomic_json(self.state_file, self.state)

    def import_mod(self, source: Path, install: Installation, nexus: dict | None = None) -> dict:
        source = Path(source)
        if source.is_dir() and self.root.is_relative_to(source.resolve()):
            raise ModError("Không nhập thư mục chứa chính thư viện manager. Chọn thư mục mod riêng.")
        mod_id = uuid.uuid4().hex
        with tempfile.TemporaryDirectory(dir=self.root / "staging") as temp:
            raw, payload = Path(temp) / "raw", Path(temp) / "payload"
            raw.mkdir()
            payload.mkdir()
            unpack(Path(source), raw)
            files, kind, metadata = normalize(raw, payload)
            hashes = {name: digest(safe_target(payload, name)) for name in files}
            record = {
                "id": mod_id, "game": install.game.key,
                "name": metadata.get("name") or Path(source).stem,
                "author": metadata.get("author", ""), "version": metadata.get("version", "—"),
                "description": metadata.get("description", ""), "kind": kind,
                "files": hashes, "size": sum(p.stat().st_size for p in payload.rglob("*") if p.is_file()),
                "added": datetime.now(timezone.utc).isoformat(), "nexus": nexus,
            }
            target = self.root / "mods" / mod_id
            shutil.move(str(payload), target)
            self.state["mods"][mod_id] = record
            try:
                self.save()
            except BaseException:
                del self.state["mods"][mod_id]
                shutil.rmtree(target)
                raise
            return record

    def mods_for(self, install: Installation) -> list[dict]:
        return [m for m in self.state["mods"].values() if m["game"] == install.game.key]

    def active(self, install: Installation) -> dict:
        return self.state["deployments"].get(install.id, {}).get("mods", {})

    def conflicts(self, install: Installation, mod_id: str) -> list[str]:
        incoming = [p.casefold() for p in self.state["mods"][mod_id]["files"]]
        result = []
        for other in self.active(install):
            if other == mod_id:
                continue
            paths = [p.casefold() for p in self.state["mods"][other]["files"]]
            if any(a == b or a.startswith(b + "/") or b.startswith(a + "/") for a in incoming for b in paths):
                result.append(self.state["mods"][other]["name"])
        return result

    def _preflight(self, install: Installation):
        if not install.available:
            raise ModError("Không tìm thấy file chạy game. Chọn lại thư mục cài đặt.")
        if is_game_running(install):
            raise ModError("Hãy đóng game trước khi thay đổi mod.")
        # A pending journal blocks new mutations until fully recovered.
        self.recover()

    def enable(self, install: Installation, mod_id: str):
        self._preflight(install)
        mod = self.state["mods"][mod_id]
        if mod["game"] != install.game.key:
            raise ModError("Mod thuộc game khác.")
        if mod_id in self.active(install):
            return
        conflicts = self.conflicts(install, mod_id)
        if conflicts:
            raise ModError("Xung đột với: " + ", ".join(conflicts) + ". Tắt mod đó trước.")
        status = framework_status(install.path)
        includes_framework = "dinput8.dll" in mod["files"]
        needs_framework = any(p.startswith(("reframework/", "natives/", "pak_mods/")) for p in mod["files"])
        if needs_framework and not status.present and not includes_framework:
            raise ModError("Cần REFramework đã nhận diện. Cài dinput8.dll đúng bản cho game trước.")
        if any(p.startswith("natives/") for p in mod["files"]) and not status.loose_files:
            raise ModError("Mở game → REFramework → LooseFileLoader → Enable Loose File Loader, đóng game rồi thử lại. Mod texture còn phụ thuộc phiên bản loader.")
        if any(p.startswith("pak_mods/") for p in mod["files"]):
            if not status.pak_directory:
                raise ModError("PAK riêng cần REFramework có PAK Directory Loading cho Requiem. Game/loader này chưa hỗ trợ; dùng bản loose files tương thích.")
            if not status.pak_enabled:
                raise ModError("Mở REFramework → PAK Directory Loading → Enable, đóng game rồi bật lại mod PAK.")
        original = deepcopy(self.state)
        deployed = {}
        changes = []
        for rel, expected in mod["files"].items():
            source = safe_target(self.root / "mods" / mod_id, rel)
            if not source.is_file() or digest(source) != expected:
                raise ModError(f"Payload đã thay đổi: {rel}. Nhập lại mod.")
            target = safe_target(install.path, rel)
            if target.exists() and not target.is_file():
                raise ModError(f"Vị trí cài không phải file: {rel}")
            backup_rel = None
            if target.exists():
                backup_rel = f"{install.id}/{mod_id}/{rel}"
                atomic_copy(target, safe_target(self.root / "backups", backup_rel))
            deployed[rel] = {"sha256": expected, "backup": backup_rel,
                             "original_sha256": digest(target) if target.is_file() else None}
            changes.append((rel, source))
        entry = self.state["deployments"].setdefault(install.id, {**install.serialize(), "mods": {}})
        entry["mods"][mod_id] = deployed
        self._transaction(install, changes, original)

    def disable(self, install: Installation, mod_id: str):
        self._preflight(install)
        deployed = self.active(install).get(mod_id)
        if not deployed:
            return
        # Never remove the framework while other managed mods still require it.
        if "dinput8.dll" in deployed and len(self.active(install)) > 1:
            raise ModError("Tắt các mod khác trước khi tắt REFramework.")
        original = deepcopy(self.state)
        changes = []
        for rel, item in deployed.items():
            target = safe_target(install.path, rel)
            if not target.is_file() or digest(target) != item["sha256"]:
                raise ModError(f"File đã bị thay đổi bên ngoài manager: {rel}. Giữ nguyên file và bản sao lưu; khôi phục file mod đúng phiên bản trước khi tắt.")
            source = safe_target(self.root / "backups", item["backup"]) if item["backup"] else None
            if source and (not source.is_file() or digest(source) != item["original_sha256"]):
                raise ModError(f"Bản sao lưu không hợp lệ: {rel}. Dừng để bảo vệ file gốc.")
            changes.append((rel, source))
        del self.state["deployments"][install.id]["mods"][mod_id]
        self._transaction(install, changes, original)

    def remove(self, mod_id: str):
        if any(mod_id in d["mods"] for d in self.state["deployments"].values()):
            raise ModError("Tắt mod ở tất cả bản cài game trước khi xóa khỏi thư viện.")
        record = self.state["mods"].pop(mod_id)
        try:
            self.save()
        except BaseException:
            self.state["mods"][mod_id] = record
            raise
        shutil.rmtree(self.root / "mods" / mod_id)

    def _transaction(self, install: Installation, changes: list, original: dict):
        txid = uuid.uuid4().hex
        tx = self.root / "transactions" / txid
        records = []
        journal_written = False
        try:
            tx.mkdir()
            for index, (rel, source) in enumerate(changes):
                target = safe_target(install.path, rel)
                exists = target.is_file()
                if exists:
                    atomic_copy(target, tx / str(index))
                records.append({"path": rel, "snapshot": str(index) if exists else None,
                                "before": digest(target) if exists else None,
                                "after": digest(source) if source else None})
            atomic_json(tx / "journal.json", {"install": install.serialize(), "before": original, "records": records})
            journal_written = True
            for rel, source in changes:
                target = safe_target(install.path, rel)
                if source:
                    atomic_copy(source, target)
                else:
                    target.unlink(missing_ok=True)
            self.state["last_tx"] = txid
            self.save()
        except BaseException:
            # If the state replace succeeded, this transaction is committed, even if cleanup failed.
            disk = self._read_state()
            if disk.get("last_tx") != txid:
                self.state = original
                if journal_written:
                    self._rollback(tx)
                elif tx.exists():
                    shutil.rmtree(tx)
            else:
                self.state = disk
            raise
        # Cleanup failure does not change a successful deployment; recover() will retry it.
        try:
            shutil.rmtree(tx)
        except OSError:
            pass

    def _rollback(self, tx: Path):
        journal = json.loads((tx / "journal.json").read_text(encoding="utf-8"))
        install = Installation.deserialize(journal["install"])
        if not install.available:
            raise ModError(f"Cần kết nối lại game tại {install.path} để phục hồi giao dịch dang dở.")
        if is_game_running(install):
            raise ModError("Đóng game rồi mở lại manager để phục hồi giao dịch dang dở.")
        # Validate every target before restoring any file; avoid overwriting external edits.
        for record in journal["records"]:
            target = safe_target(install.path, record["path"])
            current = digest(target) if target.is_file() else None
            if current not in (record["before"], record["after"]):
                raise ModError(f"Giao dịch dang dở có file thay đổi ngoài manager: {record['path']}. Bản phục hồi tại {tx}.")
            if record["snapshot"]:
                source = safe_target(tx, record["snapshot"])
                if not source.is_file() or digest(source) != record["before"]:
                    raise ModError(f"Bản phục hồi hỏng: {source}")
        for record in reversed(journal["records"]):
            target = safe_target(install.path, record["path"])
            if record["snapshot"]:
                source = safe_target(tx, record["snapshot"])
                if not source.is_file() or digest(source) != record["before"]:
                    raise ModError(f"Bản phục hồi hỏng: {source}")
                atomic_copy(source, target)
            else:
                target.unlink(missing_ok=True)
        self.state = journal["before"]
        self.save()
        shutil.rmtree(tx)

    def recover(self):
        for tx in sorted((self.root / "transactions").iterdir()):
            if not tx.is_dir() or tx.is_symlink():
                continue
            if not (tx / "journal.json").is_file():
                # No journal means no game mutation started.
                shutil.rmtree(tx)
            elif self.state.get("last_tx") == tx.name:
                shutil.rmtree(tx)
            else:
                self._rollback(tx)
