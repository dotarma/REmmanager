"""JSON-lines Python engine for the native WinUI shell. No GUI toolkit dependency."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import webbrowser

from .accounts import NexusAccounts
from .games import CATALOG, GAMES, Installation, discover, framework_status, identify
from .i18n import Locale
from .library import Library, default_data_dir
from .nexus import NexusClient, NxmLink, browser_sso, download, parse_nxm, parse_mod_input
from .processes import GameProcesses
from .protocol import enqueue, receive
from .safety import ModError, atomic_json
from .theme import make_theme, read_preferences


class Engine:
    def __init__(self, root: Path, demo=False, event=lambda data: None):
        self.root, self.demo, self.event = root, demo, event
        root.mkdir(parents=True, exist_ok=True)
        self.library = Library(root)
        self.settings_file = root / "settings.json"
        self.settings = {}
        try:
            self.settings = json.loads(self.settings_file.read_text(encoding="utf-8"))
            if not isinstance(self.settings, dict):
                self.settings = {}
        except (OSError, ValueError):
            pass
        if demo:
            from .demo import populate
            if not self.library.state["mods"]:
                populate(self.library)
            self.settings = json.loads(self.settings_file.read_text(encoding="utf-8"))
        self.settings['language'] = read_preferences(self.settings)['language']
        self.installs = {}
        for value in self.settings.get("installations", []):
            try:
                install = Installation.deserialize(value)
                self.installs[install.id] = install
            except (ValueError, KeyError, TypeError):
                continue
        # Existing users retain their library path and do not get first-run onboarding again.
        if "onboarding_done" not in self.settings and (self.installs or self.library.state["mods"]):
            self.settings["onboarding_done"] = True
        self.accounts = NexusAccounts(root)
        self.nexus = NexusClient()
        self.processes = GameProcesses()
        self.cancel = threading.Event()
        self.save()

    def save(self):
        self.settings["installations"] = [i.serialize() for i in self.installs.values()]
        atomic_json(self.settings_file, self.settings)

    def installation(self, args):
        key = args.get("installation")
        if key not in self.installs:
            raise ModError("Choose an installed game first.")
        return self.installs[key]

    def snapshot(self):
        preferences = read_preferences(self.settings)
        palette = make_theme(preferences["mode"], preferences["seed"])
        return {"games": [asdict(g) for g in GAMES], "installations": [{**i.serialize(), "id": i.id, "available": i.available} for i in self.installs.values()],
                "settings": self.settings, "preferences": preferences, "roles": palette.roles,
                "account": self.nexus.account, "accounts": self.accounts.public(), "active_account": self.accounts.active,
                "accounts_error": Locale(self.settings.get('language', 'en')).translate(self.accounts.error), "data_dir": str(self.root), "demo": self.demo}

    def dispatch(self, method, args):
        if method == "state":
            return self.snapshot()
        if method == "scan":
            if not self.demo:
                self.installs.update({i.id: i for i in discover()})
            self.save()
            return self.snapshot()
        if method == "add_game":
            install = identify(Path(args["path"]))
            if not install:
                raise ModError("Choose the game folder containing re2/re3/re4/re7/re8/re9.exe.")
            self.installs[install.id] = install
            self.save()
            return {"state": self.snapshot(), "installation": install.id}
        if method == "preferences":
            mode = args.get("mode", read_preferences(self.settings)["mode"])
            seed = args.get("seed", read_preferences(self.settings)["seed"])
            palette = make_theme(mode, seed)
            self.settings["appearance"] = {"mode": mode, "seed": seed, "preset": "windows", "color_source": "windows"}
            if args.get("language") in ("vi", "en"):
                self.settings["language"] = args["language"]
            for key in ("onboarding_done", "reduced_motion", "motion_speed", "selected_game"):
                if key in args:
                    self.settings[key] = args[key]
            self.save()
            return self.snapshot()
        if method == "mods":
            install = self.installation(args)
            status = framework_status(install.path)
            return {"mods": [{**mod, "enabled": mod["id"] in self.library.active(install), "conflicts": self.library.conflicts(install, mod["id"])} for mod in self.library.mods_for(install)], "framework": asdict(status)}
        if method == "import":
            return self.library.import_mod(Path(args["path"]), self.installation(args))
        if method in ("enable", "disable"):
            getattr(self.library, method)(self.installation(args), args["mod"])
            return {"ok": True}
        if method == "remove":
            self.library.remove(args["mod"])
            return {"ok": True}
        if method == "restore_login":
            if self.accounts.active:
                return self.dispatch('switch_account', {'account': self.accounts.active})
            return self.snapshot()
        if method in ("login", "sso"):
            key = args.get("key", "")
            if method == "sso":
                key = browser_sso(os.environ.get("RE_MANAGER_NEXUS_SSO_SLUG", ""), lambda url: self.event({"event": "browser", "url": url}), self.cancel)
            client = NexusClient(key)
            client.login()
            self.accounts.add(client.key, client.account, args.get('remember', True))
            self.nexus = client
            return self.snapshot()
        if method == 'switch_account':
            identity = str(args['account'])
            record = self.accounts.get(identity)
            client = NexusClient(record['key'])
            client.login()
            if identity != 'legacy' and str(client.account['user_id']) != identity:
                raise ModError('API key đã lưu không thuộc tài khoản này. Thêm lại tài khoản bằng key mới.')
            self.accounts.add(client.key, client.account, record['remember'], replacing=identity)
            self.nexus = client
            return self.snapshot()
        if method == 'remove_account':
            identity = str(args['account'])
            was_active = identity == self.accounts.active
            self.accounts.remove(identity)
            if was_active:
                self.nexus = NexusClient()
            return self.snapshot()
        if method == "logout":
            self.accounts.disconnect()
            self.nexus = NexusClient()
            return self.snapshot()
        if method == "nexus_mods":
            game = CATALOG[args["game"]]
            if args.get("query"):
                mod_id = parse_mod_input(args["query"], game.nexus)
                return [self.nexus.mod_info(game.nexus, mod_id)]
            return self.nexus.list_mods(game.nexus)
        if method == "nexus_files":
            return self.nexus.files(CATALOG[args["game"]].nexus, args["mod"])
        if method == "download":
            install = self.installation(args)
            link = parse_nxm(args["nxm"]) if args.get("nxm") else NxmLink(install.game.nexus, int(args["mod"]), int(args["file"]))
            if link.game != install.game.nexus:
                raise ModError("This Nexus link belongs to another game.")
            links = self.nexus.download_links(link)
            info = self.nexus.file_info(link.game, link.mod_id, link.file_id)
            last = [0.0]
            def progress(current, total):
                if time.monotonic() - last[0] > 0.12:
                    last[0] = time.monotonic()
                    self.event({"event": "progress", "current": current, "total": total})
            path = download(links[0]["URI"], self.root / "downloads", info["file_name"], self.cancel, progress)
            return self.library.import_mod(path, install, {"domain": link.game, "mod_id": link.mod_id, "file_id": link.file_id})
        if method == "launch":
            return self.processes.launch(self.installation(args), steam=args.get("steam", False), demo=self.demo)
        if method == "process_status":
            return self.processes.status(self.installation(args))
        if method == "stop":
            if self.demo:
                raise ModError("Demo does not stop real game processes.")
            return self.processes.stop(self.installation(args), force=args.get("force", False))
        if method == "inbox":
            return list(receive(self.root))
        raise ModError("Unknown engine method.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--enqueue-nxm")
    parser.add_argument("--enqueue-only", action="store_true")
    args = parser.parse_args()
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    if args.enqueue_nxm:
        enqueue(args.data_dir, args.enqueue_nxm)
        if args.enqueue_only:
            return
    output_lock = threading.Lock()
    def send(data):
        with output_lock:
            print(json.dumps(data, ensure_ascii=False), flush=True)
    engine = Engine(args.data_dir, args.demo, send)
    busy = threading.Lock()
    workers = []
    def handle(request):
        try:
            result = engine.dispatch(request["method"], request.get("args", {}))
            response = {"id": request["id"], "result": result}
        except Exception as exc:
            language = engine.settings.get("language", "en")
            response = {"id": request["id"], "error": Locale(language).translate(str(exc))}
        finally:
            busy.release()
        send(response)
    try:
        for line in sys.stdin:
            request = json.loads(line)
            method = request.get("method")
            if method == "cancel":
                engine.cancel.set()
                send({"id": request["id"], "result": {"ok": True}})
            elif method in ("process_status", "inbox"):
                try:
                    send({"id": request["id"], "result": engine.dispatch(method, request.get("args", {}))})
                except Exception as exc:
                    send({"id": request["id"], "error": str(exc)})
            elif busy.acquire(blocking=False):
                engine.cancel.clear()
                worker = threading.Thread(target=handle, args=(request,))
                worker.start()
                workers.append(worker)
            else:
                send({"id": request["id"], "error": "Another operation is still running."})
    finally:
        engine.cancel.set()
        for worker in workers:
            worker.join()
        engine.library.close()


if __name__ == "__main__":
    main()
