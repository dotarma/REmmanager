# REmmanager 0.5.2

English | [Tiếng Việt](docs/README_VI.md)

A mod manager for Resident Evil RE Engine games, with a **native WinUI 3 interface** and a **Python engine**. It does not use Tkinter, Qt, or WebView.

## Run the app

Open **`dist/REmmanager.exe`** on Windows 10 version 2004 or later, or Windows 11, x64. Only one EXE is needed: Python, .NET, and the Windows App SDK are bundled. The runtime extracts itself and caches its files when the app starts; your mod library is stored separately and survives app updates. Development builds are unsigned.

The latest prebuilt version is **`releases/0.5.2/REmmanager.exe`**. Close any older instance before opening it; Windows cannot overwrite an executable that is running. You can copy the EXE alone to another folder. Paths and commands in this guide are relative to the project root.

The first launch offers a four-step introduction: add a game, optionally connect Nexus, then import and enable mods. Choose **Skip — I've used this before** to open the library directly next time. Existing users with a library or configured installations skip the introduction automatically. You can reopen it from Settings.

1. Scan Steam/Epic libraries or add the folder containing the game's executable.
2. Check the REFramework status. Its download button opens the official GitHub page. Select the correct loader for your game and its RT/non-RT branch.
3. Add a ZIP/7z/RAR archive, PAK, Lua, DLL, or folder, select the mod, then enable it. Manual imports do not require a Nexus account.
4. Launch the executable directly or use Steam. **Stop game** appears when the selected installation is running. Save your progress first: the manager requests a normal exit before offering a separate force-stop action.

Direct launch does not bypass a game's launcher requirements. Process control matches the complete executable path, rather than stopping every process with the same filename. Demo mode never launches or stops real games.

## Interface

- Banners display the complete image with Uniform scaling, preserving its aspect ratio when maximized or fullscreen. There is no left-side overlay or fixed 280 px height limit; the title, year, and launch controls sit below the image. Only the bottom 24 DIPs fade into the background. Very wide, short windows scale the whole image down to keep mod controls accessible.
- Microsoft Fluent System Icons are bundled as vectors with their MIT license. Icons do not use Unicode text substitutes.
- Google Sans Flex is bundled with its OFL license and is not installed into Windows.
- Dark, Light, and true-black OLED modes. The accent follows Windows Settings → Personalization → Colors and updates when Windows changes color. Custom accent pickers and presets have been removed; previously saved custom colors are replaced by the Windows accent on startup.
- **English is the first-launch default.** Vietnamese is available in Settings → Language. Language changes apply immediately, and an existing saved language choice is preserved.
- The title bar follows the app theme while retaining native Windows caption buttons and window dragging.
- Sliders, progress bars, dialogs, and file/folder pickers use WinUI/Windows controls.
- Spring motion follows Material 3 Expressive tokens. Reduced motion respects Windows and the app setting; a native slider adjusts animation speed.

This is a Material 3 Expressive design implemented on WinUI, rather than an official Material component library. The palette corrects text contrast and does not use Google's official HCT algorithm. See the [UI design notes](docs/UI_DESIGN.md).

## Games and mods

The catalog includes RE2 Remake, RE3 Remake, RE4 Remake, RE7 Biohazard, Village, and Requiem. The app discovers Steam/Epic installations, accepts manual paths, and supports multiple installations of the same game. RE HD Remaster, RE0, and RE4 (2005) do not use RE Engine and are outside this catalog.

Supported payloads include loose `natives/` files and REFramework scripts, plugins, and data. The manager reads `modinfo.ini`, detects destination conflicts, backs up and restores original files, checks SHA-256 hashes, and journals transactions for recovery after interruption. It blocks mod changes while the game is running and protects destination files changed by another tool.

```text
MyMod.zip
  modinfo.ini
  natives/stm/...
  reframework/autorun/example.lua
  reframework/plugins/example.dll
  reframework/data/...
```

A standalone Lua file goes into `reframework/autorun/`; a standalone DLL goes into `reframework/plugins/`, except `dinput8.dll`, which goes into the game root. Top-level `autorun/` and `plugins/` folders are mapped into `reframework/`. A wrapping directory around an archive's payload is removed automatically.

**Standalone PAK files:** import `.pak` directly or through a ZIP/7z/RAR archive or folder. The app checks the KPKA header, deploys into `pak_mods/`, preserves the filename, and normalizes the extension to lowercase `.pak`. Enable/disable operations use the transaction journal and back up/restore existing files without modifying the game's original archives. Destination-path conflicts are detected; internal PAK assets/hashes are not analyzed for conflicts between mods.

Within the current catalog, this feature requires **Requiem and REFramework with PAK Directory Loading**. The manager checks loader markers in the DLL and the `IntegrityCheckBypass_LoadPakDirectory` setting in `re2_fw_config.txt`. If disabled, open REFramework → PAK Directory Loading → Enable, close the game, then enable the mod. Upstream gates the feature at TDB ≥ 81; PAK strings in a universal DLL do not prove compatibility with older games. See the [REFramework source](https://github.com/praydog/REFramework/blob/master/src/mods/IntegrityCheckBypass.cpp).

For RE2/RE3/RE4/RE7/Village, use compatible loose-file variants. Fluffy-style modification/invalidation of game PAKs, FOMOD, repacking, and automatic variant selection are not supported. For archives containing several options, extract them and import the intended variant's folder. `natives` mods require a compatible loader and asset format; successfully copying files does not prove the game loaded the mod.

REFramework detection uses DLL/configuration markers. It does not certify an unidentified DLL as a compatible REFramework build. The app reads the Loose File Loader setting; enable the loader according to the [official REFramework instructions](https://github.com/praydog/REFramework). It does not automatically download/install the loader or execute installation scripts from archives.

ZIP and 7z extraction are bundled. Compressed RAR files may require UnRAR/7-Zip on PATH; alternatively, extract them with another tool and import the folder. Password-protected archives are not supported. The importer rejects traversal paths, symlinks, ADS, Windows device names, case-insensitive duplicate paths, and archives exceeding its limits.

## Nexus Mods

Open the Nexus account controls in the app, get a **Personal API key** from [API Access](https://www.nexusmods.com/users/myaccount?tab=api+access), paste it, and sign in. Do not enter your Nexus password into the app. Remembered credentials use Windows DPAPI, rather than plaintext storage.

**Multiple accounts:** click the Nexus button/current account name at the top → **Add account**. Each account has its own key and Free/Premium status. Select a row, then **Use account** to switch. The app revalidates the key before replacing the active account; a failed switch keeps the current session. Adding the same user ID again updates its key without creating a duplicate.

**Disconnect** keeps saved accounts. **Remove login** forgets only the selected account's local key. Uncheck DPAPI saving for a session-only login, which disappears when the app closes. Other accounts are preserved. The last selected account is restored on startup unless it was disconnected or used only for that session.

The `nexus.accounts` vault encrypts keys, account metadata, and the active selection together using DPAPI, bound to the current Windows user. A legacy `nexus.key` is migrated without requiring Internet; the old key is removed only after the encrypted vault is successfully saved. **Previous account** receives its name and Free/Premium status after validation. An unreadable vault is preserved rather than overwritten.

Downloads use the active account. Account switching is blocked during a download. NXM links belonging to a different account are rejected: select the correct account, then reopen/paste the link. The app does not rotate accounts automatically when an API limit is reached.

- Browse trending mods, open a mod by ID/URL, select a file, track progress, and cancel downloads.
- Premium accounts download directly through the API. Free accounts open the file page for Download with Manager or manual download.
- Optionally register `nxm://` in Settings or paste a valid, unexpired NXM link. Registration replaces the current Windows user's Nexus protocol handler only when explicitly selected.
- Links are passed to the running instance through an encrypted inbox. API keys are not sent to download CDNs.

Browser SSO requires an `application_slug` assigned to this app by Nexus. Once assigned, set `RE_MANAGER_NEXUS_SSO_SLUG` before starting the EXE to show the SSO button. The websocket library is bundled. See the [official SSO demo](https://github.com/Nexus-Mods/sso-integration-demo). API-key sign-in remains available without registered SSO.

## Data

The default location is `%LOCALAPPDATA%\REmmanager`. If `%LOCALAPPDATA%\REEngineModManager` already exists, the app continues using that library to preserve backups and deployment state. Runtime files are cached in `%LOCALAPPDATA%\REmmanager\runtime`.

```text
settings.json     game paths, theme, language, onboarding
library.json      mod catalog and file ownership by installation
nexus.accounts    multi-account vault encrypted with Windows DPAPI
nexus.key         legacy key, automatically migrated on upgrade
mods/             mod payloads
backups/          original-file backups
transactions/     recovery journals
downloads/        Nexus archives
inbox/            encrypted NXM links, removed after consumption
```

Use a different library location with `REmmanager.exe --data-dir "D:\REModLibrary"`. Do not delete the library while mods are enabled. If another tool changed a destination file, inspect it and its backup before recovery. Disable mods before updating the game.

## Build and verification

Building from source requires Windows x64, Python 3.11+ with pip, and Internet access. The script downloads the .NET SDK, embeddable CPython, and NuGet packages into `.build-tools`; it does not install an SDK system-wide.

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_winui.ps1
python tools/verify_ui.py --screenshots artifacts/winui
python tools/package_source.py
```

The build uses .NET SDK 8.0.425, Windows App SDK 2.5.1, Python 3.13.9, and the dependencies in `tools/backend-requirements.txt`. Output: `dist/REmmanager.exe`. For Debug, pass `-Configuration Debug`; use `-OutputDirectory artifacts/debug` to keep it separate. Debug disables managed optimizations and embeds managed debug symbols in the single EXE. `main.py` and `launch.bat` launch the built EXE; they are not a standalone Python GUI.

### GitHub Actions builds

Open **Actions → Build and publish → Run workflow**, select `main` or a version branch, and choose **Release** or **Debug**. The workflow runs only on manual dispatch; commits, pushes, pull requests, and tags do not trigger builds. See [GitHub's manual workflow guide](https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow).

After building and passing the tests on Windows x64, the workflow publishes `REmmanager.exe` and `REmmanager.sha256` to GitHub Releases. Version metadata must match in `pyproject.toml`, the Python engine, and the WinUI project. Tags use independent counters for each configuration and version:

- Release: `main-0.5.2-001`, `main-0.5.2-002`, …; published as a normal release and marked Latest.
- Debug: `debug-0.5.2-001`, `debug-0.5.2-002`, …; published as a pre-release without replacing Latest.

The tag targets the exact commit selected for the run. Publication is serialized across branches, and existing tags/releases are never overwritten. A failed upload leaves a draft for inspection and reserves that number; the next run uses a new number. The workflow uses the built-in `GITHUB_TOKEN` with `contents: write`; no personal token is needed. Building locally does not publish anything.

Run the backend tests using the bundled runtime:

```powershell
.\.build-tools\python\python.exe -c "import sys,unittest; sys.path.insert(0,'.'); r=unittest.TextTestRunner().run(unittest.defaultTestLoader.discover('tests')); sys.exit(not r.wasSuccessful())"
```

107 automated tests cover release numbering, failed uploads, version consistency, and multiple accounts, DPAPI, failed switches, account isolation, session-only logins, legacy-key migration, PAKs, backup/rollback, unsafe archives, mocked Nexus requests, installation-scoped process control, and onboarding. Language checks cover English defaults and preservation of saved Vietnamese preferences. WinUI QA checks the fresh English interface, three themes × two languages, all six banners, Fluent SVGs, Windows accent sync, compact layouts, maximized/fullscreen resizing, native controls, reduced motion, and the Vietnamese/English account picker. Images are rendered from the app's own XAML tree rather than captured from the desktop. Real-game mod loading and downloads using real Nexus accounts have not been tested; account QA uses simulated data.

Documentation lives in `docs/`; the English README remains at the project root. Artwork, fonts, and icons are bundled. Sources/hashes are listed in `re_manager/assets/sources.json`; the font license is `assets/fonts/OFL.txt`, and the icon license is `assets/icons/LICENSE.txt`. The runtime also includes Python and dependency licenses.
