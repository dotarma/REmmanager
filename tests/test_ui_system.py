"""Behavioral checks for preferences, accessible colors, localization and direct launch."""
import ast
from pathlib import Path
import string
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch, PropertyMock

from re_manager.processes import GameProcesses
from re_manager.games import CATALOG, Installation
from re_manager.i18n import LEGACY, STRINGS, Locale
from re_manager.theme import PRESETS, contrast, make_theme, read_preferences


class ThemeTests(unittest.TestCase):
    def test_text_and_action_contrast_for_presets_and_extreme_custom_colors(self):
        seeds = [seed for _, seed in PRESETS.values()] + ["#000000", "#ffffff", "#ffff00", "#00ffff", "#ff00ff", "#808080"]
        for mode in ("light", "dark", "oled"):
            for seed in seeds:
                theme = make_theme(mode, seed)
                for foreground, background in (("onSurface", "surface"), ("onSurfaceVariant", "surfaceContainerLow"),
                                                ("onPrimary", "primary"), ("onPrimaryContainer", "primaryContainer"),
                                                ("onSecondaryContainer", "secondaryContainer"), ("onErrorContainer", "errorContainer")):
                    with self.subTest(mode=mode, seed=seed, pair=(foreground, background)):
                        self.assertGreaterEqual(contrast(theme[foreground], theme[background]), 4.5)

    def test_oled_main_surface_is_true_black(self):
        theme = make_theme("oled")
        self.assertEqual(theme["surface"], "#000000")
        self.assertEqual(theme["surfaceContainerLowest"], "#000000")
        self.assertNotEqual(make_theme("dark")["surface"], "#000000")

    def test_custom_gray_remains_neutral(self):
        primary = make_theme("dark", "#808080")["primary"]
        self.assertEqual(primary[1:3], primary[3:5])
        self.assertEqual(primary[3:5], primary[5:7])

    def test_invalid_colors_and_modes_rejected(self):
        for color in ("red", "#fff", "#gggggg", "#12345678", "#fff; command"):
            with self.subTest(color=color), self.assertRaises(ValueError):
                make_theme("dark", color)
        with self.assertRaises(ValueError):
            make_theme("invalid")

    def test_preferences_upgrade_and_invalid_values(self):
        self.assertEqual(read_preferences({})["language"], "en")
        self.assertEqual(read_preferences({"language": "vi"})["language"], "vi")
        value = read_preferences({"appearance": {"mode": "bad", "seed": "bad"}, "language": "bad"})
        self.assertEqual(value["mode"], "dark")
        self.assertEqual(value["seed"], PRESETS["fern"][1])
        self.assertEqual(value["language"], "en")

    def test_custom_preferences_roundtrip(self):
        result = read_preferences({"appearance": {"mode": "oled", "seed": "#123abc", "preset": "custom"}, "language": "en"})
        self.assertEqual(result, {"mode": "oled", "seed": "#123abc", "preset": "custom", "language": "en"})


class LocalizationTests(unittest.TestCase):
    def test_catalog_has_matching_format_fields(self):
        formatter = string.Formatter()
        for key, (vi, en) in STRINGS.items():
            fields = lambda value: {field for _, field, _, _ in formatter.parse(value) if field is not None}
            with self.subTest(key=key):
                self.assertTrue(vi and en)
                self.assertEqual(fields(vi), fields(en))

    def test_language_switch_and_dynamic_feedback(self):
        self.assertEqual(Locale().t("launch"), "Launch directly")
        self.assertEqual(Locale("en").t("launch"), "Launch directly")
        self.assertEqual(Locale("vi").t("launch"), "Chạy trực tiếp")
        self.assertEqual(Locale("en").translate("Quét xong • Tìm thấy 3 bản cài Steam/Epic."), "Scan complete • Found 3 Steam/Epic installations.")
        self.assertEqual(Locale("en").translate("○  Kết nối Nexus Mods"), "○  Connect Nexus Mods")

    def test_external_mod_name_and_path_preserved(self):
        locale = Locale("en")
        path = "D:\\Trò chơi\\RE2\\mod.lua"
        self.assertEqual(locale.translate(path), path)
        result = locale.translate(f"Payload đã thay đổi: {path}. Nhập lại mod.")
        self.assertIn(path, result)
        self.assertIn("Import the mod again", result)

    def test_known_static_core_errors_have_english_translation(self):
        package = Path(__file__).resolve().parents[1] / "re_manager"
        locale = Locale("en")
        missing = []
        for file in ("archives.py", "library.py", "nexus.py", "credentials.py", "protocol.py", "safety.py"):
            module = ast.parse((package / file).read_text(encoding="utf-8"))
            for node in ast.walk(module):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ModError" and node.args:
                    argument = node.args[0]
                    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                        value = argument.value
                        if any(ord(c) > 127 for c in value) and locale.translate(value) == value:
                            missing.append((file, value))
        self.assertEqual(missing, [])


class DirectLaunchTests(unittest.TestCase):
    def manager(self):
        install = Installation(CATALOG["re2"], Path("D:/Trò chơi/Resident Evil 2"))
        manager = GameProcesses(SimpleNamespace(process_iter=lambda attrs: [], NoSuchProcess=ProcessLookupError, AccessDenied=PermissionError))
        return manager, install

    def test_direct_launch_uses_executable_and_game_working_directory(self):
        manager, install = self.manager()
        with patch.object(Installation, "available", new_callable=PropertyMock, return_value=True), patch("re_manager.processes.subprocess.Popen") as process:
            manager.launch(install)
        process.assert_called_once_with([str(install.path / "re2.exe")], cwd=install.path)

    def test_demo_never_executes_game(self):
        manager, install = self.manager()
        from re_manager.safety import ModError
        with patch("re_manager.processes.subprocess.Popen") as process, self.assertRaises(ModError):
            manager.launch(install, demo=True)
        process.assert_not_called()

    def test_launch_failure_is_reported(self):
        manager, install = self.manager()
        failure = OSError("test launch failure")
        with patch.object(Installation, "available", new_callable=PropertyMock, return_value=True), patch("re_manager.processes.subprocess.Popen", side_effect=failure), self.assertRaises(OSError):
            manager.launch(install)


if __name__ == "__main__":
    unittest.main()
