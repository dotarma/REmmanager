"""Release numbering, version consistency and safe asset publication."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.publish_release import next_tag, publish, read_version


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        summary = patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': ''})
        summary.start()
        self.addCleanup(summary.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 're_manager').mkdir()
        (self.root / 'winui').mkdir()
        (self.root / 'pyproject.toml').write_text('[project]\nversion = "0.5.2"\n', encoding='utf-8')
        (self.root / 're_manager/__init__.py').write_text('__version__ = "0.5.2"\n', encoding='utf-8')
        (self.root / 'winui/REmmanager.csproj').write_text(
            '<Project><PropertyGroup><Version>0.5.2</Version></PropertyGroup></Project>', encoding='utf-8')
        self.directory = self.root / 'dist'
        self.directory.mkdir()
        (self.directory / 'REmmanager.exe').write_bytes(b'build fixture')

    def test_numbering_is_independent_for_version_and_configuration(self):
        existing = ['main-0.5.2-001', 'main-0.5.2-009', 'debug-0.5.2-018', 'main-0.5.1-099',
                    'main-0.5.2-123-extra', 'main-0.5.2-9']
        self.assertEqual(next_tag('Release', '0.5.2', existing), 'main-0.5.2-010')
        self.assertEqual(next_tag('Debug', '0.5.2', existing), 'debug-0.5.2-019')
        self.assertEqual(next_tag('Release', '0.5.3', existing), 'main-0.5.3-001')
        self.assertEqual(next_tag('Release', '0.5.2', ['main-0.5.2-999']), 'main-0.5.2-1000')

    def test_reject_invalid_tag_inputs(self):
        for configuration, version in [('Other', '0.5.2'), ('Debug', '0.5.2\nother'), ('Release', '../x')]:
            with self.assertRaises(ValueError):
                next_tag(configuration, version, [])

    def test_version_must_match_engine_and_frontend(self):
        self.assertEqual(read_version(self.root), '0.5.2')
        (self.root / 're_manager/__init__.py').write_text('__version__ = "0.5.1"', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Version mismatch'):
            read_version(self.root)
        (self.root / 're_manager/__init__.py').write_text('__version__ = "0.5.2"', encoding='utf-8')
        (self.root / 'winui/REmmanager.csproj').write_text(
            '<Project><PropertyGroup><Version>0.5.3</Version></PropertyGroup></Project>', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Version mismatch'):
            read_version(self.root)

    def test_release_uploads_both_assets_before_publishing_exact_commit(self):
        with patch('tools.publish_release.gh', side_effect=['main-0.5.2-001', 'main-0.5.2-002', '', '', '', 'https://example.test/release']) as api:
            tag = publish('Release', self.directory, 'dotarma/REmmanager', 'a' * 40, self.root)
        self.assertEqual(tag, 'main-0.5.2-003')  # draft 002 is reserved
        create, upload, edit = [call.args for call in api.call_args_list[2:5]]
        self.assertIn('--draft', create)
        self.assertEqual(create[create.index('--target') + 1], 'a' * 40)
        self.assertEqual(upload[:3], ('release', 'upload', tag))
        self.assertIn(str(self.directory / 'REmmanager.exe'), upload)
        self.assertIn(str(self.directory / 'REmmanager.sha256'), upload)
        self.assertIn('--draft=false', edit)
        self.assertIn('--latest=true', edit)
        self.assertNotIn('--prerelease', create)
        self.assertEqual((self.directory / 'REmmanager.sha256').read_text(encoding='utf-8'),
                         hashlib.sha256(b'build fixture').hexdigest() + '  REmmanager.exe\n')

    def test_debug_is_prerelease_and_does_not_replace_latest(self):
        with patch('tools.publish_release.gh', return_value='') as api:
            self.assertEqual(publish('Debug', self.directory, 'dotarma/REmmanager', 'b' * 40, self.root),
                             'debug-0.5.2-001')
        self.assertIn('--prerelease', api.call_args_list[2].args)
        self.assertIn('--latest=false', api.call_args_list[4].args)

    def test_failed_asset_upload_leaves_release_as_draft(self):
        failure = subprocess.CalledProcessError(1, ['gh', 'release', 'upload'])
        with patch('tools.publish_release.gh', side_effect=['', '', '', failure]) as api:
            with self.assertRaises(subprocess.CalledProcessError):
                publish('Release', self.directory, 'dotarma/REmmanager', 'a' * 40, self.root)
        self.assertFalse(any(call.args[:2] == ('release', 'edit') for call in api.call_args_list))

    def test_missing_binary_and_invalid_commit_do_not_create_release(self):
        with patch('tools.publish_release.gh') as api:
            with self.assertRaises(ValueError):
                publish('Debug', self.directory, 'dotarma/REmmanager', 'main', self.root)
            (self.directory / 'REmmanager.exe').unlink()
            with self.assertRaises(ValueError):
                publish('Debug', self.directory, 'dotarma/REmmanager', 'a' * 40, self.root)
        api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
