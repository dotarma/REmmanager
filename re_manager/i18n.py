"""Vietnamese/English UI catalog and localized controller feedback."""
from __future__ import annotations

import re

# Keys are stable; values are (Vietnamese, English).
STRINGS = {
    "library": ("Thư viện mod", "Mod library"), "games": ("GAME CỦA BẠN", "YOUR GAMES"),
    "workspace": ("WORKSPACE", "WORKSPACE"), "mods": ("Mod đã thêm", "Installed mods"),
    "nexus": ("Khám phá Nexus", "Discover Nexus"), "settings": ("Thiết lập", "Settings"),
    "appearance": ("Giao diện", "Appearance"), "personalize": ("Mang dấu ấn của bạn.", "Make it yours."),
    "appearance_hint": ("Màu sắc, không gian và ngôn ngữ — thay đổi ngay, tự động lưu.", "Color, surfaces and language — applied instantly, saved automatically."),
    "theme": ("Chế độ giao diện", "Theme mode"), "dark": ("Tối", "Dark"), "light": ("Sáng", "Light"), "oled": ("OLED đen", "OLED black"),
    "accent": ("Màu chủ đạo", "Accent color"), "presets": ("Bảng màu có sẵn", "Color presets"),
    "custom_color": ("Chọn màu tùy chỉnh", "Choose custom color"), "custom": ("Tùy chỉnh", "Custom"),
    "language": ("Ngôn ngữ", "Language"), "font": ("Phông chữ", "Typography"),
    "font_info": ("Google Sans Flex • được nạp riêng cho ứng dụng", "Google Sans Flex • loaded privately for this application"),
    "font_fallback": ("Google Sans Flex chưa nạp được; đang dùng {font}.", "Google Sans Flex could not load; using {font}."),
    "launch": ("Chạy trực tiếp", "Launch directly"), "launch_store": ("Chạy qua Steam", "Launch via Steam"),
    "launch_hint": ("Mở file chạy của game trong thư mục cài đặt.", "Open the game executable from its installation folder."),
    "add_game": ("Thêm game", "Add game"), "scan": ("Quét Steam / Epic", "Scan Steam / Epic"),
    "not_found": ("Chưa phát hiện", "Not detected"), "offline": ("Thư mục không khả dụng", "Folder unavailable"),
    "manual": ("Thủ công", "Manual"), "welcome": ("Sẵn sàng cho lần chơi tiếp theo.", "Ready for your next playthrough."),
    "choose_game": ("Chọn hoặc thêm một game để bắt đầu.", "Choose or add a game to get started."),
    "hero_label": ("RESIDENT EVIL / RE ENGINE", "RESIDENT EVIL / RE ENGINE"),
    "framework_detected": ("REFramework đã nhận diện", "REFramework detected"),
    "framework_missing": ("Chưa có REFramework", "REFramework missing"),
    "framework_unknown": ("Chưa xác minh dinput8.dll", "dinput8.dll not verified"),
    "loose_on": ("Loose files: Bật", "Loose files: On"), "loose_off": ("Loose files: Tắt", "Loose files: Off"),
    "recheck": ("Kiểm tra lại", "Check again"), "get_framework": ("Tải REFramework", "Get REFramework"),
    "library_count": ("Trong thư viện", "In library"), "enabled_count": ("Đang bật", "Enabled"), "file_count": ("File được quản lý", "Managed files"),
    "filter": ("Lọc tên mod", "Filter mods by name"), "add_mod": ("Thêm mod", "Add mod"), "add_folder": ("Thêm thư mục", "Add folder"),
    "name": ("TÊN MOD", "MOD NAME"), "kind": ("LOẠI", "TYPE"), "version": ("PHIÊN BẢN", "VERSION"),
    "source": ("NGUỒN", "SOURCE"), "state": ("TRẠNG THÁI", "STATUS"),
    "enable_mod": ("Bật mod", "Enable mod"), "disable_mod": ("Tắt mod", "Disable mod"), "remove_mod": ("Xóa khỏi thư viện", "Remove from library"),
    "open_game": ("Mở thư mục game", "Open game folder"),
    "empty_title": ("Một khởi đầu mới.", "A fresh start."),
    "empty_hint": ("Thêm file mod, chọn thư mục hoặc khám phá Nexus Mods.", "Add a mod file, choose a folder or discover Nexus Mods."),
    "no_results": ("Không có mod khớp bộ lọc.", "No mods match your filter."),
    "select_hint": ("Chọn một mod để xem chi tiết và bật/tắt.", "Select a mod to inspect it and enable or disable it."),
    "nexus_query": ("Mod ID hoặc URL Nexus Mods", "Mod ID or Nexus Mods URL"),
    "lookup": ("Tìm mod", "Find mod"), "trending": ("Xu hướng", "Trending"),
    "nexus_hint": ("Premium tải trực tiếp. Tài khoản Free dùng Download with Manager hoặc thêm file thủ công.", "Premium downloads directly. Free accounts use Download with Manager or add files manually."),
    "nxm_label": ("Liên kết Download with Manager (nxm://)", "Download with Manager link (nxm://)"),
    "download_nxm": ("Tải liên kết", "Download link"), "nexus_empty": ("Khám phá mod cho lần chơi của bạn.", "Discover mods for your playthrough."),
    "nexus_empty_hint": ("Kết nối Nexus, xem xu hướng hoặc tìm mod bằng ID/URL.", "Connect Nexus, browse trending mods or find a mod by ID/URL."),
    "storage": ("Thư mục dữ liệu", "Data directory"), "open_data": ("Mở thư mục dữ liệu", "Open data directory"),
    "integration": ("Tích hợp Nexus", "Nexus integration"), "register_nxm": ("Đăng ký nxm://", "Register nxm://"),
    "nxm_help": ("Nhận Download with Manager trong ứng dụng. Thao tác này thay ứng dụng đang xử lý liên kết Nexus của tài khoản Windows hiện tại.", "Receive Download with Manager links in this app. This replaces the current Nexus link handler for your Windows account."),
    "supported": ("Định dạng mod", "Supported mods"),
    "supported_info": ("Lua, plugin DLL và natives cần loader tương thích. PAK riêng: Requiem + REFramework PAK Directory Loading. ZIP/7z/RAR/thư mục được hỗ trợ.", "Lua, DLL plugins and natives need a compatible loader. Standalone PAK: Requiem + REFramework PAK Directory Loading. ZIP/7z/RAR/folders are supported."),
    "minimize": ("Thu nhỏ", "Minimize"), "maximize": ("Phóng to / Khôi phục", "Maximize / Restore"), "close": ("Đóng", "Close"),
    "ready": ("Sẵn sàng", "Ready"), "cancel": ("Hủy", "Cancel"),
    "theme_saved": ("Đã cập nhật giao diện.", "Appearance updated."),
    "language_saved": ("Đã chuyển sang tiếng Việt.", "Switched to English."),
    "launch_sent": ("Đã chạy trực tiếp {game}.", "Launched {game} directly."),
    "demo_launch": ("Demo: không chạy file game giả lập.", "Demo: sample game executables are not launched."),
    "busy_settings": ("Chờ thao tác hiện tại hoàn tất trước khi đổi giao diện.", "Wait for the current operation to finish before changing appearance."),
    "connect": ("Kết nối Nexus Mods", "Connect Nexus Mods"),
    "about_style": ("Material 3 Expressive • Desktop", "Material 3 Expressive • Desktop"),
    "custom_hex": ("Nhập mã màu #RRGGBB", "Enter a #RRGGBB color"), "apply": ("Áp dụng", "Apply"),
    "preview": ("Xem trước", "Preview"), "reduced_motion": ("Giảm chuyển động", "Reduce motion"),
    "no_animations": ("Hiệu ứng tĩnh; không có hoạt ảnh gây xao nhãng.", "Static transitions; no distracting animations."),
}

# Existing core/controller messages stay in Vietnamese at their source; the UI translates them.
LEGACY = {
    "Không đọc được kho tài khoản Nexus. File được giữ nguyên; có thể đăng nhập chỉ trong phiên.": "Could not read the Nexus account vault. The file is preserved; session-only sign-in is available.",
    "Chưa chuyển được đăng nhập Nexus cũ. Key cũ được giữ nguyên.": "Could not migrate the previous Nexus login. The old key is preserved.",
    "Không tìm thấy tài khoản Nexus đã chọn. Thêm tài khoản lại.": "The selected Nexus account was not found. Add it again.",
    "API key đã lưu không thuộc tài khoản này. Thêm lại tài khoản bằng key mới.": "The saved API key belongs to a different account. Add the account again using a new key.",
    "File PAK không có header KPKA hợp lệ của RE Engine.": "The PAK file does not have a valid RE Engine KPKA header.",
    "PAK riêng cần REFramework có PAK Directory Loading cho Requiem. Game/loader này chưa hỗ trợ; dùng bản loose files tương thích.": "Standalone PAKs require REFramework PAK Directory Loading for Requiem. This game/loader is unsupported; use a compatible loose-files variant.",
    "Mở REFramework → PAK Directory Loading → Enable, đóng game rồi bật lại mod PAK.": "Open REFramework > PAK Directory Loading > Enable, close the game, then enable the PAK mod again.",
    "Sẵn sàng": "Ready", "Hủy": "Cancel", "Đã hoàn tất.": "Completed.",
    "CHẾ ĐỘ DEMO • File game và mod là dữ liệu kiểm thử.": "DEMO MODE • Sample games and mods are test fixtures.",
    "Đang quét thư viện Steam / Epic…": "Scanning Steam / Epic libraries…",
    "Đang xác thực tài khoản Nexus đã lưu…": "Validating the saved Nexus account…",
    "Chọn thư mục chứa re2.exe / re3.exe / re4.exe / re7.exe / re8.exe / re9.exe": "Choose the folder containing re2.exe / re3.exe / re4.exe / re7.exe / re8.exe / re9.exe",
    "Chưa nhận diện game": "Game not recognized", "Chọn thư mục gốc của game RE Engine, nơi có file .exe đúng game.": "Choose the RE Engine game's root folder containing its executable.",
    "Chọn game": "Choose a game", "Chọn hoặc thêm thư mục game trước.": "Choose or add a game folder first.",
    "Game không khả dụng": "Game unavailable", "Thư mục game không còn khả dụng. Kết nối lại ổ đĩa hoặc chọn lại thư mục.": "The game folder is unavailable. Reconnect the drive or choose the folder again.",
    "Thêm mod thủ công": "Add mods manually", "Tất cả file": "All files", "Chọn thư mục mod chứa natives hoặc reframework": "Choose a mod folder containing natives or reframework",
    "Đang kiểm tra và nhập mod…": "Checking and importing mod…", "Đang cài mod và sao lưu file gốc…": "Installing mod and backing up original files…",
    "Đang khôi phục file gốc…": "Restoring original files…", "Xóa mod": "Remove mod",
    "Xóa payload mod đã chọn khỏi thư viện? Bản sao lưu file gốc được giữ lại.": "Remove the selected mod payload from the library? Original-file backups will be kept.",
    "Đang xóa mod…": "Removing mod…", "Bật mod đã chọn": "Enable selected mod", "Tắt mod đã chọn": "Disable selected mod",
    "Kết nối Nexus Mods để khám phá và tải mod.": "Connect Nexus Mods to discover and download mods.",
    "Đang lấy mod xu hướng từ Nexus…": "Fetching trending mods from Nexus…", "Đang tìm mod…": "Finding mod…",
    "Xem file của mod": "View mod files", "Đang lấy danh sách file…": "Fetching files…", "Tải file đã chọn": "Download selected file",
    "Trên Nexus, chọn Download with Manager; mở/dán link NXM hoặc tải thủ công rồi thêm file.": "On Nexus, choose Download with Manager; open/paste the NXM link, or download manually and add the file.",
    "Thêm/chọn đúng bản cài game của liên kết Nexus trước khi tải.": "Add or select the matching game installation before downloading this Nexus link.",
    "Đã hủy. File tải hoàn tất được giữ trong downloads.": "Cancelled. The completed archive is kept in downloads.",
    "Đang tải mod từ Nexus…": "Downloading mod from Nexus…", "Kết nối Nexus Mods": "Connect Nexus Mods",
    "Dùng Personal API key từ trang API Access của Nexus.": "Use a Personal API key from Nexus API Access.",
    "Ghi nhớ đăng nhập bằng Windows DPAPI": "Remember login with Windows DPAPI", "Đăng nhập API key": "Sign in with API key",
    "Mở trang lấy API key ↗": "Get an API key ↗", "Đang xác thực Nexus API key…": "Validating Nexus API key…",
    "Đăng nhập qua trình duyệt (SSO)": "Sign in with browser (SSO)", "SSO cần application slug được Nexus cấp cho ứng dụng này.": "SSO requires an application slug assigned by Nexus to this application.",
    "Chờ xác nhận Nexus trong trình duyệt…": "Waiting for Nexus authorization in your browser…", "Đăng xuất": "Sign out",
    "Đăng ký nxm://": "Register nxm://", "Đặt RE Engine Mod Manager làm ứng dụng mở liên kết nxm:// cho tài khoản Windows hiện tại? Ứng dụng quản lý mod khác sẽ không còn nhận liên kết này.": "Set RE Engine Mod Manager as the nxm:// handler for this Windows account? Other mod managers will no longer receive these links.",
    "Đã đăng ký nxm://. Có thể dùng Download with Manager trên Nexus.": "Registered nxm://. You can now use Download with Manager on Nexus.",
    "Đã gửi lệnh chạy game.": "Game launch requested.", "Thao tác chưa hoàn tất. Xem thông báo để xử lý.": "The operation could not finish. See the message for recovery steps.",
    "Đang hoàn tất thao tác. Chờ xong rồi đóng cửa sổ.": "Finishing the current operation. Wait, then close the window.",
    "Không mở được Mod Manager": "Could not open Mod Manager", "Thủ công": "Manual", "● Đang bật": "● Enabled", "○ Đã tắt": "○ Disabled",
    "Chưa có thông tin": "Unknown", "Xung đột": "Conflicts",
    "Một phiên Mod Manager khác đang dùng thư viện này.": "Another Mod Manager instance is using this library.",
    "Không nhập thư mục chứa chính thư viện manager. Chọn thư mục mod riêng.": "Do not import a folder containing the manager's own library. Choose a separate mod folder.",
    "Không tìm thấy file chạy game. Chọn lại thư mục cài đặt.": "The game executable is missing. Choose the installation folder again.",
    "Hãy đóng game trước khi thay đổi mod.": "Close the game before changing mods.", "Mod thuộc game khác.": "This mod belongs to a different game.",
    "Cần REFramework đã nhận diện. Cài dinput8.dll đúng bản cho game trước.": "REFramework must be detected first. Install the correct dinput8.dll for this game.",
    "Mở game → REFramework → LooseFileLoader → Enable Loose File Loader, đóng game rồi thử lại. Mod texture còn phụ thuộc phiên bản loader.": "Open the game → REFramework → LooseFileLoader → Enable Loose File Loader, close the game, then try again. Texture mods also depend on the loader version.",
    "Tắt các mod khác trước khi tắt REFramework.": "Disable other mods before disabling REFramework.",
    "Tắt mod ở tất cả bản cài game trước khi xóa khỏi thư viện.": "Disable this mod in every game installation before removing it from the library.",
    "Đóng game rồi mở lại manager để phục hồi giao dịch dang dở.": "Close the game and reopen the manager to recover the interrupted transaction.",
    "Không kiểm tra được game đang chạy. Đóng game và thử lại.": "Could not check running games. Close the game and try again.",
    "Không nhập mod từ symbolic link.": "Cannot import a mod from a symbolic link.",
    "Thư mục mod chứa liên kết; hãy dùng thư mục file thật.": "The mod folder contains links. Use a folder with regular files.",
    "Archive chứa liên kết hoặc file đặc biệt.": "The archive contains links or special files.",
    "Archive vượt giới hạn số lượng hoặc dung lượng file.": "The archive exceeds the file-count or size limit.",
    "Tổng dữ liệu giải nén vượt giới hạn 16 GiB.": "Extracted data exceeds the 16 GiB limit.",
    "Cài phần mở rộng archives hoặc giải nén RAR rồi thêm thư mục.": "Install the archives extension, or extract the RAR and add its folder.",
    "Cài phần mở rộng archives hoặc giải nén 7z rồi thêm thư mục.": "Install the archives extension, or extract the 7z and add its folder.",
    "RAR chứa liên kết không được hỗ trợ.": "RAR links are not supported.", "7z chứa liên kết không được hỗ trợ.": "7z links are not supported.",
    "Không hỗ trợ archive có mật khẩu.": "Password-protected archives are not supported.",
    "Hỗ trợ ZIP, thư mục, Lua, DLL, PAK; 7z/RAR cần phần mở rộng archives.": "Supported inputs: ZIP, folders, Lua and DLL; 7z/RAR require the archives extension. Standalone PAK payloads need a supported loader layout.",
    "PAK cần quy tắc loader theo từng game. Bản này hỗ trợ natives/Lua/plugin; hãy dùng bản mod loose files.": "PAK installation needs game-specific loader rules. This version supports natives/Lua/plugins; use the loose-files variant.",
    "Không tìm thấy payload mod hợp lệ.": "No supported mod payload was found.",
    "Đường dẫn vượt ra ngoài thư mục cho phép.": "The path escapes the allowed directory.",
    "Cần đăng nhập bằng Nexus API key hợp lệ.": "Sign in with a valid Nexus API key.",
    "API key không hợp lệ hoặc đã bị thu hồi. Đăng nhập lại.": "The API key is invalid or revoked. Sign in again.",
    "Nexus từ chối truy cập. Tài khoản miễn phí cần liên kết NXM từ Download with Manager; Premium có thể tải trực tiếp.": "Nexus denied access. Free accounts need an NXM link from Download with Manager; Premium can download directly.",
    "Không tìm thấy game/mod/file trên Nexus Mods.": "The game, mod or file was not found on Nexus Mods.",
    "Đã chạm giới hạn API Nexus. Đợi rồi thử lại.": "The Nexus API rate limit was reached. Wait and try again.",
    "Không kết nối được Nexus Mods. Kiểm tra mạng và thử lại.": "Could not connect to Nexus Mods. Check your connection and try again.",
    "Nexus trả về dữ liệu không hợp lệ.": "Nexus returned invalid data.", "Phản hồi xác thực Nexus không hợp lệ.": "Nexus returned an invalid authentication response.",
    "Đăng nhập Nexus trước khi tải mod.": "Sign in to Nexus before downloading mods.",
    "Liên kết tải xuống thuộc tài khoản Nexus khác.": "This download link belongs to another Nexus account.",
    "Liên kết tải xuống đã hết hạn.": "This download link has expired.",
    "Tài khoản miễn phí: dùng Download with Manager trên Nexus rồi mở/dán liên kết nxm://, hoặc tải bằng trình duyệt và thêm mod thủ công.": "Free account: use Download with Manager on Nexus and open/paste the nxm:// link, or download in your browser and add the mod manually.",
    "Nexus chưa cung cấp máy chủ tải xuống.": "Nexus has not provided a download server.",
    "Định dạng file Nexus chưa được hỗ trợ.": "This Nexus file format is not supported.",
    "Đã hủy tải xuống.": "Download cancelled.", "Tải xuống chưa hoàn tất. Thử lại.": "Download incomplete. Try again.",
    "Tải xuống thất bại. Kiểm tra mạng hoặc tạo lại liên kết Nexus.": "Download failed. Check your connection or generate a new Nexus link.",
    "File vượt giới hạn tải xuống 16 GiB.": "The file exceeds the 16 GiB download limit.",
    "SSO cần application slug được Nexus cấp cho ứng dụng này.": "SSO requires an application slug assigned by Nexus to this application.",
    "Cài phần mở rộng sso để dùng đăng nhập trình duyệt.": "Install the sso extension to use browser sign-in.",
    "Nexus SSO từ chối phiên đăng nhập. Thử lại hoặc dùng API key.": "Nexus SSO rejected this session. Try again or use an API key.",
    "SSO đã hủy hoặc hết thời gian chờ.": "SSO was cancelled or timed out.",
    "Không kết nối được Nexus SSO. Thử lại hoặc đăng nhập API key.": "Could not connect to Nexus SSO. Try again or sign in with an API key.",
    "Windows không mã hóa/giải mã được thông tin đăng nhập.": "Windows could not encrypt/decrypt the credentials. Try signing in without remembering the key.",
    "Liên kết NXM đã hết hạn. Tạo lại từ Download with Manager.": "The NXM link expired. Generate a new one with Download with Manager.",
    "Liên kết NXM phải có cả key và expires, hoặc không có cả hai.": "An NXM link must contain both key and expires, or neither.",
    "URL mod thuộc game khác với game đang chọn.": "The mod URL belongs to a different game.",
    "Mod ID và File ID phải là số nguyên dương.": "Mod ID and File ID must be positive integers.", "ID phải lớn hơn 0.": "ID must be greater than zero.",
    "Liên kết NXM quá dài.": "The NXM link is too long.", "Bộ lọc Nexus không hợp lệ.": "Invalid Nexus filter.",
    "Liên kết cần có dạng nxm://game/mods/123/files/456?key=…&expires=…": "Use a link like nxm://game/mods/123/files/456?key=…&expires=…",
    "Nhập Mod ID hoặc URL https://www.nexusmods.com/<game>/mods/<id>.": "Enter a Mod ID or a URL like https://www.nexusmods.com/<game>/mods/<id>.",
    "Domain game Nexus không hợp lệ.": "Invalid Nexus game domain.",
    "API chuyển hướng ngoài dự kiến; đã dừng để bảo vệ API key.": "Unexpected API redirect; stopped to protect the API key.",
    "Phản hồi API vượt giới hạn dung lượng.": "The API response exceeds the size limit.",
    "Từ chối chuyển hướng tải xuống qua HTTP không mã hóa.": "An unencrypted HTTP download redirect was rejected.",
    "Nexus cung cấp URL tải xuống không hợp lệ.": "Nexus provided an invalid download URL.", "Tải xuống cần HTTPS.": "Downloads require HTTPS.",
    "Đăng ký nxm:// chỉ hỗ trợ Windows.": "Registering nxm:// is supported only on Windows.",
    "Lưu đăng nhập chỉ hỗ trợ Windows DPAPI; hệ điều hành khác dùng đăng nhập trong phiên.": "Remembering credentials requires Windows DPAPI. Other platforms use session-only sign-in.",
}

PATTERNS = [
    (r"Quét xong • Tìm thấy (\d+) bản cài Steam/Epic\.", r"Scan complete • Found \1 Steam/Epic installations."),
    (r"Đã thêm (.+)\. Chọn Bật mod để cài vào game\.", r"Added \1. Choose Enable mod to deploy it to the game."),
    (r"Tài khoản: (.+)", r"Account: \1"), (r"Đã kết nối Nexus • (.+)", r"Connected to Nexus • \1"),
    (r"Đang tải: (.+)", r"Downloading: \1"),
    (r"(\d+) file  •  (.+)  •  Tác giả: (.+)", r"\1 files  •  \2  •  Author: \3"),
    (r"Xung đột: (.+)", r"Conflicts: \1"),
    (r"Xung đột với: (.+)\. Tắt mod đó trước\.", r"Conflicts with: \1. Disable that mod first."),
    (r"Payload đã thay đổi: (.+)\. Nhập lại mod\.", r"Payload changed: \1. Import the mod again."),
    (r"Vị trí cài không phải file: (.+)", r"Installation target is not a file: \1"),
    (r"File đã bị thay đổi bên ngoài manager: (.+)\. Giữ nguyên file và bản sao lưu; khôi phục file mod đúng phiên bản trước khi tắt\.", r"File changed outside the manager: \1. File and backup are preserved; restore the correct mod file before disabling it."),
    (r"Bản sao lưu không hợp lệ: (.+)\. Dừng để bảo vệ file gốc\.", r"Invalid backup: \1. Stopped to protect original files."),
    (r"Bản phục hồi hỏng: (.+)", r"Recovery snapshot is damaged: \1"),
    (r"Cần kết nối lại game tại (.+) để phục hồi giao dịch dang dở\.", r"Reconnect the game at \1 to recover the interrupted transaction."),
    (r"Không đọc được thư viện (.+)\. Dữ liệu được giữ nguyên để phục hồi\.", r"Could not read the library at \1. Data is preserved for recovery."),
    (r"Giao dịch dang dở có file thay đổi ngoài manager: (.+)\. Bản phục hồi tại (.+)\.", r"An interrupted transaction has an externally changed file: \1. Recovery snapshots: \2."),
    (r"Đường dẫn không an toàn: (.+)", r"Unsafe path: \1"),
    (r"Từ chối liên kết trong đường dẫn: (.+)", r"Rejected a link in the path: \1"),
    (r"Archive có đường dẫn trùng nhau: (.+)", r"Archive contains duplicate paths: \1"),
    (r"Payload trùng đường dẫn: (.+)", r"Payload contains duplicate paths: \1"),
    (r"Chưa xác định được vị trí cài '(.+)'\. Chọn đúng thư mục biến thể chứa natives hoặc reframework\.", r"Unknown installation location for '\1'. Select the correct variant folder containing natives or reframework."),
    (r"Nexus API trả về lỗi HTTP (\d+)\.", r"Nexus API returned HTTP \1."),
]


class Locale:
    def __init__(self, language="en"):
        self.language = language if language in ("vi", "en") else "en"

    def t(self, key, **values):
        pair = STRINGS[key]
        return pair[self.language == "en"].format(**values)

    def translate(self, value):
        if not isinstance(value, str) or self.language != "en":
            return value
        if value in LEGACY:
            return LEGACY[value]
        for prefix in ("○  ", "●  ", "⚙  ", "+  ", "↻  "):
            if value.startswith(prefix):
                return prefix + self.translate(value[len(prefix):])
        for pair in STRINGS.values():
            if value == pair[0]:
                return pair[1]
        for pattern, replacement in PATTERNS:
            if re.fullmatch(pattern, value, re.DOTALL):
                return re.sub(pattern, replacement, value, flags=re.DOTALL)
        if "\n" in value:
            return "\n".join(self.translate(line) for line in value.splitlines())
        return value


