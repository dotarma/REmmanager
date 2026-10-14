"""Multi-account isolation, DPAPI persistence, migration and failed-switch behavior."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from re_manager.accounts import NexusAccounts
from re_manager.credentials import CredentialStore
from re_manager.nexus import NexusClient, NxmLink
from re_manager.safety import ModError
from re_manager.service import Engine

A = {'user_id': 11, 'name': 'Survivor One', 'is_premium': True, 'is_supporter': False}
B = {'user_id': 22, 'name': 'Survivor Two', 'is_premium': False, 'is_supporter': False}


class FakeNexus:
    profiles = {'fixture-key-a': A, 'fixture-key-a2': A, 'fixture-key-b': B}
    def __init__(self, key=''):
        self.key = key.strip()
        self.account = None
    def login(self):
        if self.key not in self.profiles:
            raise ModError('invalid test key')
        self.account = dict(self.profiles[self.key])
        return self.account
    def list_mods(self, game):
        return [{'user_id': self.account['user_id']}]


@unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
class AccountVaultTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vault = NexusAccounts(self.root)

    def test_two_accounts_roundtrip_with_encrypted_keys(self):
        self.vault.add('fixture-key-a', A)
        self.vault.add('fixture-key-b', B)
        raw = (self.root / 'nexus.accounts').read_bytes()
        self.assertNotIn(b'fixture-key-a', raw)
        self.assertNotIn(b'fixture-key-b', raw)
        reopened = NexusAccounts(self.root)
        self.assertEqual(reopened.get('11')['key'], 'fixture-key-a')
        self.assertEqual(reopened.get('22')['key'], 'fixture-key-b')
        self.assertEqual(reopened.active, '22')

    def test_add_same_user_updates_key_without_duplicate(self):
        self.vault.add('fixture-key-a', A)
        self.vault.add('fixture-key-a2', A)
        self.assertEqual(len(self.vault.public()), 1)
        self.assertEqual(NexusAccounts(self.root).get('11')['key'], 'fixture-key-a2')

    def test_public_list_has_no_keys_or_extra_account_fields(self):
        self.vault.add('fixture-key-a', {**A, 'api_key': 'private', 'email': 'private'})
        public = json.dumps(self.vault.public())
        self.assertNotIn('key', public)
        self.assertNotIn('email', public)
        self.assertNotIn('private', public)

    def test_session_only_account_never_persists(self):
        self.vault.add('fixture-key-a', A, remember=False)
        self.assertFalse((self.root / 'nexus.accounts').exists())
        self.assertEqual(NexusAccounts(self.root).public(), [])
        self.vault.disconnect()
        self.assertEqual(self.vault.public(), [])

    def test_session_account_does_not_delete_other_saved_accounts(self):
        self.vault.add('fixture-key-a', A)
        self.vault.add('fixture-key-b', B, remember=False)
        reopened = NexusAccounts(self.root)
        self.assertEqual(set(reopened.records), {'11'})
        self.assertIsNone(reopened.active)

    def test_disconnect_preserves_saved_accounts_without_auto_login(self):
        self.vault.add('fixture-key-a', A)
        self.vault.disconnect()
        reopened = NexusAccounts(self.root)
        self.assertEqual(set(reopened.records), {'11'})
        self.assertIsNone(reopened.active)

    def test_remove_only_selected_account(self):
        self.vault.add('fixture-key-a', A)
        self.vault.add('fixture-key-b', B)
        self.vault.remove('11')
        reopened = NexusAccounts(self.root)
        self.assertEqual(set(reopened.records), {'22'})
        self.assertEqual(reopened.active, '22')

    def test_failed_save_preserves_previous_vault_and_active_account(self):
        self.vault.add('fixture-key-a', A)
        before = (self.root / 'nexus.accounts').read_bytes()
        with patch.object(self.vault.store, 'save', side_effect=OSError('disk failure')), self.assertRaises(OSError):
            self.vault.add('fixture-key-b', B)
        self.assertEqual(self.vault.active, '11')
        self.assertEqual(set(self.vault.records), {'11'})
        self.assertEqual((self.root / 'nexus.accounts').read_bytes(), before)

    def test_corrupt_vault_is_preserved_and_allows_session_signin(self):
        file = self.root / 'nexus.accounts'
        file.write_bytes(b'invalid encrypted vault')
        vault = NexusAccounts(self.root)
        self.assertTrue(vault.error)
        vault.add('fixture-key-a', A, remember=False)
        with self.assertRaises(ModError):
            vault.add('fixture-key-b', B, remember=True)
        self.assertEqual(file.read_bytes(), b'invalid encrypted vault')

    def test_legacy_key_migrates_without_network(self):
        legacy = CredentialStore(self.root / 'nexus.key')
        legacy.save('fixture-key-a')
        vault = NexusAccounts(self.root)
        self.assertEqual(vault.active, 'legacy')
        self.assertEqual(vault.get('legacy')['key'], 'fixture-key-a')
        self.assertFalse(legacy.path.exists())
        self.assertEqual(NexusAccounts(self.root).active, 'legacy')

    def test_failed_migration_keeps_legacy_key(self):
        legacy = CredentialStore(self.root / 'nexus.key')
        legacy.save('fixture-key-a')
        with patch.object(CredentialStore, 'save', side_effect=OSError('disk failure')):
            vault = NexusAccounts(self.root)
        self.assertTrue(vault.error)
        self.assertEqual(legacy.load(), 'fixture-key-a')


@unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
class EngineAccountTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        mock = patch('re_manager.service.NexusClient', FakeNexus)
        mock.start()
        self.addCleanup(mock.stop)
        self.engine = self.new_engine()

    def new_engine(self):
        engine = Engine(self.root)
        self.addCleanup(engine.library.close)
        return engine

    def login_two(self):
        self.engine.dispatch('login', {'key': 'fixture-key-a'})
        self.engine.dispatch('login', {'key': 'fixture-key-b'})

    def test_switch_uses_selected_credentials_and_updates_membership(self):
        self.login_two()
        result = self.engine.dispatch('switch_account', {'account': '11'})
        self.assertEqual(result['account'], A)
        self.assertEqual(self.engine.nexus.key, 'fixture-key-a')
        self.assertEqual(self.engine.dispatch('nexus_mods', {'game': 're2'}), [{'user_id': 11}])

    def test_failed_switch_keeps_current_account_and_saved_accounts(self):
        self.login_two()
        self.engine.accounts.records['11']['key'] = 'revoked-test-key'
        with self.assertRaises(ModError):
            self.engine.dispatch('switch_account', {'account': '11'})
        self.assertEqual(self.engine.nexus.account, B)
        self.assertEqual(self.engine.accounts.active, '22')

    def test_failed_new_login_does_not_replace_current_account(self):
        self.login_two()
        with self.assertRaises(ModError):
            self.engine.dispatch('login', {'key': 'invalid-test-key'})
        self.assertEqual(self.engine.nexus.account, B)
        self.assertEqual(len(self.engine.snapshot()['accounts']), 2)

    def test_restart_restores_last_selected_account(self):
        self.login_two()
        self.engine.dispatch('switch_account', {'account': '11'})
        self.engine.library.close()
        reopened = self.new_engine()
        self.assertEqual(reopened.dispatch('restore_login', {})['account'], A)

    def test_removing_active_account_disconnects_without_removing_other_accounts(self):
        self.login_two()
        result = self.engine.dispatch('remove_account', {'account': '22'})
        self.assertIsNone(result['account'])
        self.assertEqual([a['id'] for a in result['accounts']], ['11'])

    def test_legacy_login_resolves_identity_and_deduplicates(self):
        self.engine.library.close()
        CredentialStore(self.root / 'nexus.key').save('fixture-key-a')
        reopened = self.new_engine()
        result = reopened.dispatch('restore_login', {})
        self.assertEqual(result['account'], A)
        self.assertEqual([a['id'] for a in result['accounts']], ['11'])

    def test_state_never_contains_keys(self):
        self.login_two()
        snapshot = json.dumps(self.engine.snapshot())
        self.assertNotIn('fixture-key-a', snapshot)
        self.assertNotIn('fixture-key-b', snapshot)

    def test_nxm_for_different_account_is_rejected_before_network(self):
        self.login_two()
        client = NexusClient(self.engine.nexus.key)
        client.account = self.engine.nexus.account
        with patch.object(client, 'request') as request, self.assertRaisesRegex(ModError, 'tài khoản Nexus khác'):
            client.download_links(NxmLink('residentevil22019', 1, 2, user_id=11))
        request.assert_not_called()
