"""Smoke test the actual embedded runtime before publishing it."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psutil
import py7zr
import rarfile
import websocket
from re_manager.archives import unpack

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'mod.lua').write_text('return 42', encoding='utf-8')
    with py7zr.SevenZipFile(root / 'sample.7z', 'w') as archive:
        archive.write(root / 'mod.lua', 'reframework/autorun/mod.lua')
    unpack(root / 'sample.7z', root / 'out')
    assert (root / 'out/reframework/autorun/mod.lua').read_text(encoding='utf-8') == 'return 42'
assert 'tkinter' not in sys.modules
print('Embedded runtime imports and 7z extraction: OK')
