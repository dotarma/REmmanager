"""Vendor Microsoft's MIT-licensed Fluent System Icons as vector assets."""
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import json

root = Path(__file__).resolve().parents[1] / 're_manager/assets'
icons = {
    'add': ('Add', 'add'), 'folder': ('Folder Open', 'folder_open'),
    'refresh': ('Arrow Sync', 'arrow_sync'), 'settings': ('Settings', 'settings'),
    'play': ('Play', 'play'), 'stop': ('Stop', 'stop'), 'delete': ('Delete', 'delete'),
    'download': ('Arrow Download', 'arrow_download'), 'check': ('Checkmark Circle', 'checkmark_circle'),
    'circle': ('Circle', 'circle'), 'warning': ('Warning', 'warning'), 'open': ('Open', 'open'),
    'person': ('Person', 'person'), 'library': ('Library', 'library'),
    'search': ('Search', 'search'), 'games': ('Games', 'games'),
    'info': ('Info', 'info'), 'dismiss': ('Dismiss', 'dismiss'),
    'link': ('Link', 'link'), 'book': ('Book Open', 'book_open'),
}
destination = root / 'icons'
destination.mkdir(exist_ok=True)
records = []
base = 'https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/'
for key, (folder, stem) in icons.items():
    url = base + f'assets/{folder.replace(" ", "%20")}/SVG/ic_fluent_{stem}_20_regular.svg'
    with urlopen(Request(url, headers={'User-Agent': 'REmmanager-Assets/0.4'}), timeout=30) as response:
        data = response.read()
    (destination / f'{key}.svg').write_bytes(data)
    records.append({'asset': f'icons/{key}.svg', 'source': url, 'sha256': hashlib.sha256(data).hexdigest()})
with urlopen(base + 'LICENSE', timeout=30) as response:
    (destination / 'LICENSE.txt').write_bytes(response.read())
sources = root / 'sources.json'
existing = json.loads(sources.read_text(encoding='utf-8'))
sources.write_text(json.dumps([r for r in existing if not r['asset'].startswith('icons/')] + records, indent=2), encoding='utf-8')
print(f'Vendored {len(records)} Fluent vector icons with MIT license.')
