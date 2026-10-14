"""Build the Tk-free Python runtime payload and the WinUI SDK version props."""
import json
from pathlib import Path
import shutil
import zipfile

root = Path(__file__).resolve().parents[1]
tools = root / ".build-tools"
runtime = tools / "python"
package = runtime / "app/re_manager"
package.mkdir(parents=True, exist_ok=True)
modules = ("__init__", "games", "library", "archives", "safety", "nexus", "credentials", "accounts", "protocol", "processes", "service", "theme", "i18n", "demo")
for module in modules:
    shutil.copyfile(root / "re_manager" / f"{module}.py", package / f"{module}.py")
(runtime / "python313._pth").write_text("python313.zip\n.\napp\nlibs\nimport site\n", encoding="utf-8")
target = root / "winui/Backend.zip"
with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for file in runtime.rglob("*"):
        if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
            archive.write(file, file.relative_to(runtime))
versions = json.loads((tools / "versions.json").read_text(encoding="utf-8"))
(root / "winui/SdkVersion.props").write_text(f'<Project><PropertyGroup><WinAppSdkVersion>{versions["winappsdk"]}</WinAppSdkVersion></PropertyGroup></Project>\n', encoding="utf-8")
print("Backend packed:", target.stat().st_size, "bytes; no Tkinter runtime.")
