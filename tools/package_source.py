"""Create a clean source distribution without dependencies or user data."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
target = root / "REmmanager-source.zip"
files = [root / name for name in ("README.md", "pyproject.toml", "main.py", "launch.bat", ".gitignore")]
files.extend((root / 'docs').rglob('*.md'))
for directory in ("re_manager", "tests", "tools"):
    files.extend((root / directory).rglob("*.py"))
files.extend(p for p in (root / "tools").iterdir() if p.suffix in (".ps1", ".txt"))
files.extend(p for p in (root / "winui").iterdir() if p.suffix in (".cs", ".csproj", ".props", ".manifest"))
files.extend(p for p in (root / "re_manager/assets").rglob("*") if p.is_file())
with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(files):
        archive.write(file, Path("REmmanager") / file.relative_to(root))
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert not any(".test-deps" in name or "__pycache__" in name or "nexus.key" in name for name in archive.namelist())
    assert "REmmanager/re_manager/assets/fonts/GoogleSansFlex.ttf" in archive.namelist()
    assert "REmmanager/re_manager/assets/fonts/OFL.txt" in archive.namelist()
    assert "REmmanager/winui/REmmanager.csproj" in archive.namelist()
    assert "REmmanager/docs/README_VI.md" in archive.namelist()
    assert "REmmanager/docs/UI_DESIGN.md" in archive.namelist()
    assert "REmmanager/re_manager/assets/icons/LICENSE.txt" in archive.namelist()
    assert sum(name.endswith('.svg') and '/assets/icons/' in name for name in archive.namelist()) == 20
    assert sum(name.startswith("REmmanager/re_manager/assets/banners/") and name.endswith(".jpg") for name in archive.namelist()) == 6
print(f"Packaged {len(files)} files: {target.name} ({target.stat().st_size:,} bytes)")
