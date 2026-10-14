"""Behavior checks for installation-scoped stopping and persisted first-run state."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from re_manager.games import CATALOG, Installation
from re_manager.processes import GameProcesses
from re_manager.service import Engine


class ProcessControlTests(unittest.TestCase):
    def setUp(self):
        self.install = Installation(CATALOG['re2'], Path('C:/Games/RE2'))
        self.selected = Mock(pid=123)
        self.selected.info = {'exe': str(self.install.path / 're2.exe')}
        self.selected.create_time.return_value = 10
        self.selected.exe.return_value = str(self.install.path / 're2.exe')
        self.other = Mock(pid=456)
        self.other.info = {'exe': 'C:/Other/RE2/re2.exe'}
        self.api = SimpleNamespace(process_iter=Mock(return_value=[self.selected, self.other]),
                                   Process=Mock(return_value=self.selected),
                                   NoSuchProcess=ProcessLookupError, AccessDenied=PermissionError)
        self.manager = GameProcesses(self.api)

    def test_same_filename_in_other_installation_does_not_match(self):
        self.assertEqual(self.manager.status(self.install), {'running': True, 'pids': [123]})

    def test_force_stop_targets_only_the_selected_installation(self):
        self.api.process_iter.side_effect = [[self.selected, self.other], [self.other]]
        self.assertEqual(self.manager.stop(self.install, force=True), {'stopped': True})
        self.selected.terminate.assert_called_once()
        self.other.terminate.assert_not_called()

    def test_reused_pid_is_not_terminated(self):
        replacement = Mock()
        replacement.create_time.return_value = 11
        replacement.exe.return_value = str(self.install.path / 're2.exe')
        self.api.Process.return_value = replacement
        self.api.process_iter.side_effect = [[self.selected], []]
        self.manager.stop(self.install, force=True)
        replacement.terminate.assert_not_called()

    def test_changed_executable_is_not_terminated(self):
        replacement = Mock()
        replacement.create_time.return_value = 10
        replacement.exe.return_value = 'C:/Other/RE2/re2.exe'
        self.api.Process.return_value = replacement
        self.api.process_iter.side_effect = [[self.selected], []]
        self.manager.stop(self.install, force=True)
        replacement.terminate.assert_not_called()

    def test_already_running_game_is_not_launched_twice(self):
        with patch.object(Installation, 'available', True), patch('re_manager.processes.subprocess.Popen') as popen:
            self.assertTrue(self.manager.launch(self.install)['already_running'])
        popen.assert_not_called()


class FirstRunTests(unittest.TestCase):
    def engine(self, root):
        engine = Engine(root)
        self.addCleanup(engine.library.close)
        return engine

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_new_user_sees_onboarding(self):
        engine = self.engine(self.root)
        self.assertFalse(engine.snapshot()['settings'].get('onboarding_done', False))
        self.assertEqual(engine.snapshot()['settings']['language'], 'en')

    def test_skip_is_remembered_across_restarts(self):
        engine = self.engine(self.root)
        engine.dispatch('preferences', {'onboarding_done': True, 'language': 'vi'})
        engine.library.close()
        restored = self.engine(self.root).snapshot()['settings']
        self.assertTrue(restored['onboarding_done'])
        self.assertEqual(restored['language'], 'vi')

    def test_existing_installation_skips_onboarding(self):
        install = Installation(CATALOG['re7'], self.root / 'RE7')
        (self.root / 'settings.json').write_text(json.dumps({'installations': [install.serialize()]}), encoding='utf-8')
        self.assertTrue(self.engine(self.root).snapshot()['settings']['onboarding_done'])

    def test_demo_cannot_stop_real_games(self):
        engine = self.engine(self.root)
        engine.demo = True
        with patch.object(engine.processes, 'stop') as stop, self.assertRaisesRegex(Exception, 'Demo'):
            engine.dispatch('stop', {})
        stop.assert_not_called()


if __name__ == '__main__':
    unittest.main()
