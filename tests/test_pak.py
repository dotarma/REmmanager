"""PAK deployment lifecycle; fixtures validate routing, not real game assets."""
from pathlib import Path
from unittest.mock import patch

from test_manager import Fixture
from re_manager.games import CATALOG, Installation, framework_status
from re_manager.safety import ModError, atomic_copy

PAK = b'KPKA' + bytes(12) + b'fixture, not game assets'


class PakTests(Fixture):
    def setUp(self):
        super().setUp()
        (self.game / 're2.exe').unlink()
        (self.game / 're9.exe').touch()
        (self.game / 'dinput8.dll').write_bytes(b'REFramework LoadPakDirectory pak_mods')
        self.install = Installation(CATALOG['re9'], self.game)

    def pak(self, name='appearance.pak'):
        path = self.root / name
        path.write_bytes(PAK)
        return self.lib.import_mod(path, self.install)

    def test_standalone_and_uppercase_extension_route_to_loader(self):
        mod = self.pak('appearance.PAK')
        self.assertEqual(mod['kind'], 'PAK')
        self.assertEqual(list(mod['files']), ['pak_mods/appearance.pak'])

    def test_archive_preserves_loader_subdirectories(self):
        mod = self.mod({'pak_mods/custom/appearance.PAK': PAK})
        self.assertIn('pak_mods/custom/appearance.pak', mod['files'])

    def test_wrapper_and_mixed_mod_route_correctly(self):
        mod = self.mod({'wrapper/appearance.pak': PAK, 'wrapper/autorun/test.lua': b'return 1'})
        self.assertEqual(mod['kind'], 'Mixed / PAK')
        self.assertEqual(set(mod['files']), {'pak_mods/appearance.pak', 'reframework/autorun/test.lua'})

    def test_header_validation_happens_before_staging_commit(self):
        for data in (b'KPKA', b'not an RE Engine pak' * 2):
            with self.subTest(data=data), self.assertRaisesRegex(ModError, 'KPKA'):
                self.mod({'appearance.pak': data})
        self.assertEqual(self.lib.state['mods'], {})

    def test_enable_disable_leaves_original_game_archive_untouched(self):
        original = self.game / 're_chunk_000.pak'
        original.write_bytes(b'original game archive')
        mod = self.pak()
        self.lib.enable(self.install, mod['id'])
        self.assertEqual((self.game / 'pak_mods/appearance.pak').read_bytes(), PAK)
        self.lib.disable(self.install, mod['id'])
        self.assertFalse((self.game / 'pak_mods/appearance.pak').exists())
        self.assertEqual(original.read_bytes(), b'original game archive')

    def test_preexisting_pak_is_backed_up_and_restored(self):
        target = self.game / 'pak_mods/appearance.pak'
        target.parent.mkdir()
        target.write_bytes(b'previous custom pak')
        mod = self.pak()
        self.lib.enable(self.install, mod['id'])
        self.lib.disable(self.install, mod['id'])
        self.assertEqual(target.read_bytes(), b'previous custom pak')

    def test_matching_destination_conflict_is_blocked(self):
        first = self.pak()
        second = self.pak()
        self.lib.enable(self.install, first['id'])
        with self.assertRaisesRegex(ModError, 'Xung đột'):
            self.lib.enable(self.install, second['id'])

    def test_external_edits_are_preserved(self):
        mod = self.pak()
        self.lib.enable(self.install, mod['id'])
        target = self.game / 'pak_mods/appearance.pak'
        target.write_bytes(b'external edit')
        with self.assertRaisesRegex(ModError, 'bên ngoài'):
            self.lib.disable(self.install, mod['id'])
        self.assertEqual(target.read_bytes(), b'external edit')

    def test_loader_disabled_in_config_is_blocked(self):
        (self.game / 're2_fw_config.txt').write_text('IntegrityCheckBypass_LoadPakDirectory=false')
        self.assertFalse(framework_status(self.game).pak_enabled)
        with self.assertRaisesRegex(ModError, 'Enable'):
            self.lib.enable(self.install, self.pak()['id'])

    def test_old_loader_is_blocked(self):
        (self.game / 'dinput8.dll').write_bytes(b'REFramework older build')
        with self.assertRaisesRegex(ModError, 'PAK Directory Loading'):
            self.lib.enable(self.install, self.pak()['id'])

    def test_universal_loader_strings_do_not_prove_older_game_support(self):
        (self.game / 're9.exe').unlink()
        (self.game / 're2.exe').touch()
        self.install = Installation(CATALOG['re2'], self.game)
        self.assertFalse(framework_status(self.game).pak_directory)
        with self.assertRaisesRegex(ModError, 'PAK Directory Loading'):
            self.lib.enable(self.install, self.pak()['id'])

    def test_partial_pak_copy_failure_rolls_back(self):
        mod = self.mod({'one.pak': PAK, 'two.pak': PAK})
        def fail_second(source, target):
            if target == self.game / 'pak_mods/two.pak':
                raise PermissionError('simulated disk failure')
            atomic_copy(source, target)
        with patch('re_manager.library.atomic_copy', side_effect=fail_second), self.assertRaises(PermissionError):
            self.lib.enable(self.install, mod['id'])
        self.assertFalse((self.game / 'pak_mods/one.pak').exists())
        self.assertNotIn(mod['id'], self.lib.active(self.install))
