from __future__ import annotations

from copy import deepcopy
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from re_manager.archives import unpack
from re_manager.credentials import CredentialStore, crypt
from re_manager.games import CATALOG, Installation, discover, framework_status, identify, parse_vdf
from re_manager.library import Library
from re_manager.nexus import NexusClient, NxmLink, download, parse_mod_input, parse_nxm
from re_manager.safety import FileLock, ModError, atomic_copy, atomic_json, digest, relative_name, safe_target


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.game = self.root / "game"
        self.game.mkdir()
        (self.game / "re2.exe").write_bytes(b"fake game")
        (self.game / "dinput8.dll").write_bytes(b"fake REFramework")
        self.install = Installation(CATALOG["re2"], self.game)
        self.lib = Library(self.root / "library")
        self.running = patch("re_manager.library.is_game_running", return_value=False)
        self.running.start()
        self.addCleanup(self.running.stop)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.lib.close)

    def archive(self, entries, filename="mod.zip"):
        archive = self.root / filename
        with zipfile.ZipFile(archive, "w") as output:
            for name, content in entries.items():
                output.writestr(name, content)
        return archive

    def mod(self, entries=None, filename="mod.zip"):
        return self.lib.import_mod(self.archive(entries or {"reframework/autorun/test.lua": "return 1"}, filename), self.install)


class DiscoveryTests(Fixture):
    def test_identify_game_and_executable(self):
        self.assertEqual(identify(self.game).game.key, "re2")
        self.assertEqual(identify(self.game / "re2.exe").game.key, "re2")
        self.assertIsNone(identify(self.root))

    def test_all_catalog_games(self):
        for game in CATALOG.values():
            folder = self.root / game.key
            folder.mkdir()
            (folder / game.exe).touch()
            self.assertEqual(identify(folder).game, game)

    def test_unicode_vdf(self):
        result = parse_vdf('"libraryfolders" { "0" { "path" "D:\\\\Trò chơi\\\\Steam" } }')
        self.assertEqual(result["libraryfolders"]["0"]["path"], "D:\\Trò chơi\\Steam")

    def test_multiple_steam_libraries(self):
        steam, extra = self.root / "steam", self.root / "Thư viện"
        (steam / "steamapps").mkdir(parents=True)
        (extra / "steamapps/common/RE2").mkdir(parents=True)
        (extra / "steamapps/common/RE2/re2.exe").touch()
        (steam / "steamapps/libraryfolders.vdf").write_text(f'"libraryfolders" {{ "1" {{ "path" "{extra.as_posix()}" }} }}', encoding="utf-8")
        (extra / "steamapps/appmanifest_883710.acf").write_text('"AppState" { "appid" "883710" "installdir" "RE2" }', encoding="utf-8")
        result = discover([steam], self.root / "no-epic")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source, "Steam")

    def test_epic_manifest(self):
        folder = self.root / "epic"
        folder.mkdir()
        (folder / "game.item").write_text(json.dumps({"InstallLocation": str(self.game)}), encoding="utf-8")
        result = discover([], folder)
        self.assertEqual(result[0].game.key, "re2")
        self.assertEqual(result[0].source, "Epic Games")

    def test_framework_heuristic_and_config(self):
        self.assertTrue(framework_status(self.game).present)
        (self.game / "re2_fw_config.txt").write_text("LooseFileLoader_Enabled=true\n")
        self.assertTrue(framework_status(self.game).loose_files)
        (self.game / "dinput8.dll").write_bytes(b"another loader")
        self.assertEqual(framework_status(self.game).state, "unknown")
        (self.game / "dinput8.dll").unlink()
        self.assertEqual(framework_status(self.game).state, "missing")


class ArchiveTests(Fixture):
    def test_wrapper_and_metadata(self):
        mod = self.mod({"Wrapper/modinfo.ini": "name=My mod\nversion=2.1\nauthor=Tester", "Wrapper/reframework/autorun/a.lua": "hello"})
        self.assertEqual(mod["name"], "My mod")
        self.assertEqual(mod["version"], "2.1")
        self.assertIn("reframework/autorun/a.lua", mod["files"])

    def test_single_lua_maps_to_autorun(self):
        path = self.root / "single.lua"
        path.write_text("return true")
        mod = self.lib.import_mod(path, self.install)
        self.assertIn("reframework/autorun/single.lua", mod["files"])

    def test_directory_import(self):
        path = self.root / "unpacked/autorun"
        path.mkdir(parents=True)
        (path / "test.lua").write_text("hello")
        mod = self.lib.import_mod(path.parent, self.install)
        self.assertIn("reframework/autorun/test.lua", mod["files"])

    def test_zip_slip_and_windows_unsafe_names(self):
        names = ["../outside.lua", "/absolute.lua", "C:/evil.lua", "autorun/a:evil.lua", "autorun/NUL.lua", "autorun/a. ", "autorun/../evil.lua", "autorun\\..\\evil.lua"]
        for name in names:
            with self.subTest(name=name), self.assertRaises(ModError):
                self.mod({name: "bad"})
        self.assertFalse((self.root / "outside.lua").exists())
        self.assertEqual(self.lib.state["mods"], {})

    def test_case_insensitive_duplicate(self):
        with self.assertRaises(ModError):
            self.mod({"autorun/A.lua": "a", "autorun/a.lua": "b"})

    def test_zip_symlink(self):
        archive = self.root / "link.zip"
        entry = zipfile.ZipInfo("autorun/link.lua")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr(entry, "../../escape")
        with self.assertRaises(ModError):
            self.lib.import_mod(archive, self.install)

    def test_optional_variants_are_not_combined(self):
        with self.assertRaises(ModError):
            self.mod({"OptionA/natives/stm/a.tex.1": "A", "OptionB/natives/stm/a.tex.1": "B"})

    def test_invalid_standalone_pak_is_rejected(self):
        with self.assertRaisesRegex(ModError, "PAK"):
            self.mod({"test.pak": "opaque"})

    def test_byte_limit(self):
        with patch("re_manager.archives.MAX_BYTES", 4), self.assertRaises(ModError):
            self.mod({"test.lua": "0123456789"})

    def test_import_cannot_recurse_into_its_own_staging(self):
        with self.assertRaisesRegex(ModError, "thư viện manager"):
            self.lib.import_mod(self.root, self.install)


class DeploymentTests(Fixture):
    def test_enable_disable_restores_original(self):
        target = self.game / "reframework/autorun/test.lua"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"original")
        mod = self.mod()
        self.lib.enable(self.install, mod["id"])
        self.assertEqual(target.read_text(), "return 1")
        self.lib.disable(self.install, mod["id"])
        self.assertEqual(target.read_bytes(), b"original")
        self.assertEqual(self.lib.active(self.install), {})
        self.lib.enable(self.install, mod["id"])
        self.lib.disable(self.install, mod["id"])
        self.assertEqual(target.read_bytes(), b"original")

    def test_new_files_removed_on_disable(self):
        mod = self.mod()
        self.lib.enable(self.install, mod["id"])
        self.lib.disable(self.install, mod["id"])
        self.assertFalse((self.game / "reframework/autorun/test.lua").exists())

    def test_conflicting_mod_is_rejected(self):
        first = self.mod(filename="one.zip")
        second = self.mod(filename="two.zip")
        self.lib.enable(self.install, first["id"])
        with self.assertRaisesRegex(ModError, "Xung đột"):
            self.lib.enable(self.install, second["id"])
        self.assertNotIn(second["id"], self.lib.active(self.install))

    def test_external_edits_preserved(self):
        mod = self.mod()
        self.lib.enable(self.install, mod["id"])
        target = self.game / "reframework/autorun/test.lua"
        target.write_bytes(b"edited externally")
        with self.assertRaisesRegex(ModError, "bên ngoài"):
            self.lib.disable(self.install, mod["id"])
        self.assertEqual(target.read_bytes(), b"edited externally")
        self.assertIn(mod["id"], self.lib.active(self.install))

    def test_wrong_game_and_missing_framework(self):
        mod = self.mod()
        other = self.root / "other"
        other.mkdir()
        (other / "re4.exe").touch()
        with self.assertRaisesRegex(ModError, "game khác"):
            self.lib.enable(Installation(CATALOG["re4"], other), mod["id"])
        (self.game / "dinput8.dll").unlink()
        with self.assertRaisesRegex(ModError, "REFramework"):
            self.lib.enable(self.install, mod["id"])

    def test_natives_requires_enabled_loose_loader(self):
        mod = self.mod({"natives/stm/a.mesh.1": "test"})
        with self.assertRaisesRegex(ModError, "LooseFileLoader"):
            self.lib.enable(self.install, mod["id"])
        (self.game / "re2_fw_config.txt").write_text("LooseFileLoader_Enabled=true\n")
        self.lib.enable(self.install, mod["id"])
        self.assertTrue((self.game / "natives/stm/a.mesh.1").exists())

    def test_modified_payload_rejected(self):
        mod = self.mod()
        (self.lib.root / "mods" / mod["id"] / "reframework/autorun/test.lua").write_text("changed")
        with self.assertRaisesRegex(ModError, "Payload"):
            self.lib.enable(self.install, mod["id"])

    def test_running_game_rejected(self):
        mod = self.mod()
        with patch("re_manager.library.is_game_running", return_value=True), self.assertRaisesRegex(ModError, "đóng game"):
            self.lib.enable(self.install, mod["id"])

    def test_cannot_delete_active_mod(self):
        mod = self.mod()
        self.lib.enable(self.install, mod["id"])
        with self.assertRaises(ModError):
            self.lib.remove(mod["id"])
        self.lib.disable(self.install, mod["id"])
        self.lib.remove(mod["id"])
        self.assertNotIn(mod["id"], self.lib.state["mods"])

    def test_partial_write_failure_rolls_back(self):
        mod = self.mod({"autorun/a.lua": "A", "autorun/b.lua": "B"})
        real_copy = atomic_copy
        def fail_second(source, target):
            if target == self.game / "reframework/autorun/b.lua":
                raise PermissionError("simulated disk failure")
            real_copy(source, target)
        with patch("re_manager.library.atomic_copy", side_effect=fail_second), self.assertRaises(PermissionError):
            self.lib.enable(self.install, mod["id"])
        self.assertFalse((self.game / "reframework/autorun/a.lua").exists())
        self.assertNotIn(mod["id"], self.lib.active(self.install))
        self.assertEqual(list((self.lib.root / "transactions").iterdir()), [])

    def test_recovery_after_interrupted_deployment(self):
        before = deepcopy(self.lib.state)
        target = self.game / "reframework/autorun/crash.lua"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"original")
        tx = self.lib.root / "transactions" / "crash-test"
        tx.mkdir()
        atomic_copy(target, tx / "0")
        old_hash = digest(target)
        target.write_bytes(b"modded")
        atomic_json(tx / "journal.json", {"install": self.install.serialize(), "before": before, "records": [{"path": "reframework/autorun/crash.lua", "snapshot": "0", "before": old_hash, "after": digest(target)}]})
        self.lib.close()
        reopened = Library(self.lib.root)
        self.addCleanup(reopened.close)
        self.assertEqual(target.read_bytes(), b"original")
        self.assertFalse(tx.exists())

    def test_registry_commit_failure_rolls_back(self):
        mod = self.mod()
        real_save = self.lib.save
        call = [0]
        def fail_first():
            call[0] += 1
            if call[0] == 1:
                raise OSError("simulated state write failure")
            real_save()
        with patch.object(self.lib, "save", side_effect=fail_first), self.assertRaises(OSError):
            self.lib.enable(self.install, mod["id"])
        self.assertNotIn(mod["id"], self.lib.active(self.install))
        self.assertFalse((self.game / "reframework/autorun/test.lua").exists())

    def test_library_exclusive_lock(self):
        with self.assertRaises(ModError):
            Library(self.lib.root)

    def test_registry_rejects_path_traversal_mod_id(self):
        state = {"schema": 1, "mods": {"../outside": {"id": "../outside", "game": "re2", "files": {}}}, "deployments": {}}
        atomic_json(self.lib.state_file, state)
        self.lib.close()
        with self.assertRaisesRegex(ModError, "Không đọc được thư viện"):
            Library(self.lib.root)

    def test_framework_cannot_be_disabled_with_active_script(self):
        framework = self.mod({"dinput8.dll": "managed REFramework"}, "framework.zip")
        script = self.mod(filename="script.zip")
        self.lib.enable(self.install, framework["id"])
        self.lib.enable(self.install, script["id"])
        with self.assertRaisesRegex(ModError, "mod khác"):
            self.lib.disable(self.install, framework["id"])
        self.lib.disable(self.install, script["id"])
        self.lib.disable(self.install, framework["id"])
        self.assertEqual((self.game / "dinput8.dll").read_bytes(), b"fake REFramework")

    def test_failed_transaction_directory_does_not_mark_mod_active(self):
        mod = self.mod()
        real_mkdir = Path.mkdir
        def fail_tx(path, *args, **kwargs):
            if path.parent == self.lib.root / "transactions":
                raise PermissionError("simulated transaction directory failure")
            return real_mkdir(path, *args, **kwargs)
        with patch.object(Path, "mkdir", fail_tx), self.assertRaises(PermissionError):
            self.lib.enable(self.install, mod["id"])
        self.assertNotIn(mod["id"], self.lib.active(self.install))


class NexusTests(unittest.TestCase):
    def test_parse_nxm(self):
        expires = int(time.time()) + 3600
        link = parse_nxm(f"nxm://residentevil22019/mods/12/files/34?key=token&expires={expires}&user_id=7")
        self.assertEqual((link.mod_id, link.file_id, link.user_id), (12, 34, 7))

    def test_expired_or_invalid_nxm(self):
        for value in ["https://evil.test", "nxm://game/mods/0/files/2", "nxm://game/mods/1/files/2?key=k", "nxm://game/mods/1/files/2?key=k&expires=1"]:
            with self.subTest(value=value), self.assertRaises(ModError):
                parse_nxm(value)

    def test_mod_url_game_validation(self):
        self.assertEqual(parse_mod_input("https://www.nexusmods.com/residentevil22019/mods/42", "residentevil22019"), 42)
        with self.assertRaises(ModError):
            parse_mod_input("https://www.nexusmods.com/residentevil42023/mods/42", "residentevil22019")

    def test_free_download_requires_site_token(self):
        client = NexusClient("secret")
        client.account = {"user_id": 7, "is_premium": False}
        with self.assertRaisesRegex(ModError, "miễn phí"):
            client.download_links(NxmLink("game", 1, 2))

    def test_nxm_account_mismatch(self):
        client = NexusClient("secret")
        client.account = {"user_id": 7, "is_premium": True}
        with self.assertRaisesRegex(ModError, "khác"):
            client.download_links(NxmLink("game", 1, 2, user_id=8))

    def test_authenticated_endpoint_and_redacted_account(self):
        client = NexusClient("very-secret")
        with patch.object(client, "request", return_value={"user_id": 7, "name": "tester", "key": "very-secret", "is_premium": True}) as request:
            account = client.login()
        request.assert_called_once_with("/users/validate.json")
        self.assertNotIn("key", account)

    def test_download_sends_no_api_key_and_writes_stream(self):
        class Response(io.BytesIO):
            headers = {"Content-Length": "7"}
            def geturl(self):
                return "https://cdn.nexusmods.com/mod.zip"
        class Opener:
            def open(self, request, timeout):
                self.request = request
                return Response(b"payload")
        opener = Opener()
        with tempfile.TemporaryDirectory() as temp, patch("re_manager.nexus.build_opener", return_value=opener):
            target = download("https://cdn.nexusmods.com/mod.zip", Path(temp), "mod.zip", threading.Event())
            self.assertEqual(target.read_bytes(), b"payload")
            self.assertNotIn("apikey", dict((k.lower(), v) for k, v in opener.request.header_items()))

    def test_cancel_cleans_partial_download(self):
        class Response(io.BytesIO):
            headers = {"Content-Length": "100"}
            def geturl(self):
                return "https://cdn.nexusmods.com/mod.zip"
        event = threading.Event()
        event.set()
        with tempfile.TemporaryDirectory() as temp, patch("re_manager.nexus.build_opener") as opener:
            opener.return_value.open.return_value = Response(b"partial")
            with self.assertRaisesRegex(ModError, "hủy"):
                download("https://cdn.nexusmods.com/mod.zip", Path(temp), "mod.zip", event)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_api_errors_do_not_expose_key(self):
        from urllib.error import HTTPError
        client = NexusClient("private-key")
        client.opener = unittest.mock.Mock()
        client.opener.open.side_effect = HTTPError("https://api.nexusmods.com", 401, "private-key", {}, None)
        with self.assertRaises(ModError) as error:
            client.login()
        self.assertNotIn("private-key", str(error.exception))

    def test_sso_uses_registered_application_and_returns_key(self):
        from re_manager.nexus import browser_sso
        socket = unittest.mock.Mock()
        socket.recv.side_effect = [json.dumps({"success": True, "data": {"connection_token": "reconnect-token"}}), json.dumps({"success": True, "data": {"api_key": "returned-key"}})]
        websocket_module = unittest.mock.Mock()
        websocket_module.create_connection.return_value = socket
        websocket_module.WebSocketTimeoutException = TimeoutError
        websocket_module.WebSocketException = ConnectionError
        opened = []
        with patch.dict("sys.modules", {"websocket": websocket_module}):
            key = browser_sso("registered-test-slug", opened.append, threading.Event())
        self.assertEqual(key, "returned-key")
        self.assertIn("application=registered-test-slug", opened[0])
        self.assertEqual(json.loads(socket.send.call_args.args[0])["protocol"], 2)
        socket.close.assert_called_once()

    def test_sso_cancel_closes_socket(self):
        from re_manager.nexus import browser_sso
        event = threading.Event()
        event.set()
        websocket_module = unittest.mock.Mock()
        websocket_module.WebSocketTimeoutException = TimeoutError
        websocket_module.WebSocketException = ConnectionError
        with patch.dict("sys.modules", {"websocket": websocket_module}), self.assertRaisesRegex(ModError, "hủy"):
            browser_sso("registered-test-slug", lambda _: None, event)
        websocket_module.create_connection.return_value.close.assert_called_once()


@unittest.skipUnless(os.name == "nt", "Windows DPAPI")
class CredentialTests(unittest.TestCase):
    def test_dpapi_roundtrip(self):
        encoded = crypt(b"test-secret")
        self.assertNotIn(b"test-secret", encoded)
        self.assertEqual(crypt(encoded, decrypt=True), b"test-secret")

    def test_credential_store(self):
        with tempfile.TemporaryDirectory() as temp:
            store = CredentialStore(Path(temp) / "key")
            store.save("test-secret")
            self.assertEqual(store.load(), "test-secret")
            store.clear()
            self.assertEqual(store.load(), "")

    def test_nxm_inbox_is_encrypted_and_consumed(self):
        from re_manager.protocol import enqueue, receive
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            url = f"nxm://game/mods/1/files/2?key=private-token&expires={int(time.time()) + 3600}"
            enqueue(root, url)
            item = next((root / "inbox").glob("*.nxm"))
            self.assertNotIn(b"private-token", item.read_bytes())
            self.assertEqual(list(receive(root)), [url])
            self.assertEqual(list((root / "inbox").glob("*.nxm")), [])


if __name__ == "__main__":
    unittest.main()
