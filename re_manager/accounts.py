"""Multiple Nexus credentials, encrypted together with Windows user DPAPI."""
from copy import deepcopy
import json
from pathlib import Path

from .credentials import CredentialStore
from .safety import ModError


class NexusAccounts:
    def __init__(self, root: Path):
        self.store = CredentialStore(root / 'nexus.accounts')
        self.records = {}
        self.active = None
        self.error = ''
        self.blocked = False
        try:
            encoded = self.store.load()
            if encoded:
                data = json.loads(encoded)
                if data['schema'] != 1 or not isinstance(data['accounts'], dict):
                    raise ValueError('schema')
                for identity, record in data['accounts'].items():
                    account = self.public_account(record['account'], legacy=identity == 'legacy')
                    if identity != 'legacy' and identity != str(account['user_id']):
                        raise ValueError('identity')
                    if not isinstance(record['key'], str) or not record['key'].strip():
                        raise ValueError('key')
                    self.records[identity] = {'key': record['key'], 'account': account, 'remember': True}
                self.active = data.get('active')
                if self.active is not None and self.active not in self.records:
                    raise ValueError('active identity')
        except (OSError, ValueError, KeyError, TypeError, ModError):
            self.records, self.active, self.blocked = {}, None, True
            self.error = 'Không đọc được kho tài khoản Nexus. File được giữ nguyên; có thể đăng nhập chỉ trong phiên.'
            return
        # Import the previous single-account key without making a network request.
        legacy = CredentialStore(root / 'nexus.key')
        if legacy.path.exists():
            try:
                key = legacy.load()
                if key and not any(r['key'] == key for r in self.records.values()):
                    records = deepcopy(self.records)
                    records['legacy'] = {'key': key, 'account': self.public_account({}, legacy=True), 'remember': True}
                    self.commit(records, self.active or 'legacy')
                legacy.clear()  # Only after the encrypted vault is committed.
            except (OSError, ValueError, ModError):
                self.error = 'Chưa chuyển được đăng nhập Nexus cũ. Key cũ được giữ nguyên.'

    @staticmethod
    def public_account(account, legacy=False):
        if not isinstance(account, dict):
            raise ValueError('account')
        identity = None if legacy else int(account['user_id'])
        if identity is not None and identity <= 0:
            raise ValueError('user id')
        return {'user_id': identity, 'name': str(account.get('name') or '')[:160],
                'is_premium': bool(account.get('is_premium')), 'is_supporter': bool(account.get('is_supporter'))}

    def commit(self, records, active):
        saved = {identity: {'key': r['key'], 'account': r['account']} for identity, r in records.items() if r['remember']}
        old_saved = {identity: {'key': r['key'], 'account': r['account']} for identity, r in self.records.items() if r['remember']}
        saved_active = active if active in saved else None
        old_active = self.active if self.active in old_saved else None
        if self.blocked:
            # Allow session-only use while preserving an unreadable vault byte-for-byte.
            if saved or old_saved:
                raise ModError(self.error)
        elif saved != old_saved or saved_active != old_active:
            self.store.save(json.dumps({'schema': 1, 'active': saved_active, 'accounts': saved}, ensure_ascii=False))
        self.records, self.active = records, active

    def add(self, key, account, remember=True, replacing=None):
        public = self.public_account(account)
        identity = str(public['user_id'])
        records = deepcopy(self.records)
        if replacing == 'legacy' or records.get('legacy', {}).get('key') == key.strip():
            records.pop('legacy', None)
        records[identity] = {'key': key.strip(), 'account': public, 'remember': bool(remember)}
        self.commit(records, identity)
        return identity

    def get(self, identity):
        if identity not in self.records:
            raise ModError('Không tìm thấy tài khoản Nexus đã chọn. Thêm tài khoản lại.')
        return self.records[identity]

    def disconnect(self):
        records = deepcopy(self.records)
        if self.active in records and not records[self.active]['remember']:
            del records[self.active]
        self.commit(records, None)

    def remove(self, identity):
        self.get(identity)
        records = deepcopy(self.records)
        del records[identity]
        self.commit(records, None if self.active == identity else self.active)

    def public(self):
        return [{'id': identity, **r['account'], 'remembered': r['remember']} for identity, r in self.records.items()]
