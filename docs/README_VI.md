# REmmanager 0.5.2

[English](../README.md) | Tiếng Việt

Mod manager cho Resident Evil RE Engine, dùng **WinUI 3 native** cho giao diện và **Python** cho xử lý mod. Không dùng Tkinter, Qt hay WebView.

## Chạy ứng dụng

Mở **`dist/REmmanager.exe`** trên Windows 10 2004 trở lên hoặc Windows 11, x64. Chỉ cần mang theo một EXE; Python, .NET và Windows App SDK đã được đóng gói. Khi chạy, runtime tự giải nén và lưu cache; dữ liệu mod vẫn được lưu riêng để giữ lại qua các lần cập nhật. Bản phát triển chưa ký số.

Bản 0.5.2 mới đã build sẵn ở **`releases/0.5.2/REmmanager.exe`**. Nếu đang mở EXE cũ, đóng bản cũ rồi chạy file này; Windows không cho ghi đè executable đang chạy. Có thể mang riêng file EXE sang thư mục khác. Các đường dẫn và lệnh trong tài liệu tính từ gốc dự án.

Lần đầu có hướng dẫn bốn bước: thêm game, kết nối Nexus tùy chọn, thêm và bật mod. Chọn **Bỏ qua — đã sử dụng** nếu đã quen; lần sau vào thẳng thư viện. Người có thư viện/bản cài từ phiên bản cũ được bỏ qua tự động. Có thể mở lại hướng dẫn trong Thiết lập.

1. Quét Steam/Epic hoặc thêm thư mục chứa executable game.
2. Xem trạng thái REFramework; nút tải mở GitHub chính thức. Chọn loader đúng game và đúng nhánh RT/non-RT.
3. Thêm file ZIP/7z/RAR, PAK, Lua, DLL hoặc thư mục; chọn mod rồi Bật. Mod thủ công không cần tài khoản Nexus.
4. Chạy trực tiếp executable hoặc chạy qua Steam. Khi game được nhận diện đang chạy, nút **Dừng game** xuất hiện. Lưu tiến trình chơi trước khi dừng; app yêu cầu đóng bình thường rồi mới cho chọn buộc dừng.

Chạy trực tiếp không thay thế yêu cầu launcher của game. Manager đối chiếu toàn bộ đường dẫn executable, không dừng mọi tiến trình cùng tên. Chế độ demo không chạy hoặc dừng game thật.

## Giao diện

- Banner hiển thị toàn bộ ảnh bằng Uniform, không crop hay giãn sai tỷ lệ khi phóng to/toàn màn hình. Bỏ lớp che bên trái và giới hạn cao 280 px; tên game/năm/nút chạy nằm dưới ảnh. Chỉ 24 px mép dưới mờ vào nền. Cửa sổ rất rộng nhưng thấp thu nhỏ toàn ảnh để giữ chỗ cho thao tác mod.
- Icon vector Fluent System Icons của Microsoft, đóng gói cùng giấy phép MIT; không dùng ký tự Unicode thay icon.
- Google Sans Flex đóng gói với giấy phép OFL, không cài font vào Windows.
- Dark, Light, OLED nền đen. Màu nhấn tự lấy từ Windows Settings → Personalization → Colors, cập nhật khi Windows đổi màu. Đã bỏ preset và bộ chọn màu riêng; màu tùy chỉnh cũ được thay bằng màu Windows khi mở app.
- English mặc định cho lần chạy đầu. Có thể đổi sang Tiếng Việt trong Settings → Language; app nhớ và giữ lựa chọn ngôn ngữ đã lưu.
- Title bar cùng theme, giữ nút caption và cơ chế kéo cửa sổ native của Windows.
- Slider, progress bar, hộp thoại và bộ chọn file/folder dùng WinUI/Windows.
- Chuyển động spring dựa trên token Material 3 Expressive; giảm chuyển động theo Windows hoặc thiết lập trong app. Có slider tốc độ animation.

Đây là thiết kế M3 Expressive áp dụng trên WinUI; không phải thư viện component Material chính thức. Palette có hiệu chỉnh tương phản, không dùng thuật toán HCT chính thức. Chi tiết ở [UI_DESIGN.md](UI_DESIGN.md).

## Game và mod

Catalog gồm RE2 Remake, RE3 Remake, RE4 Remake, RE7 Biohazard, Village và Requiem. Tự quét thư viện Steam/Epic; cho thêm đường dẫn và chọn nhiều bản cài cùng game. RE HD Remaster, RE0 và RE4 2005 không thuộc RE Engine.

Hỗ trợ loose files `natives/` và REFramework scripts/plugins/data. Có đọc `modinfo.ini`, kiểm tra xung đột, sao lưu/khôi phục file gốc, kiểm tra SHA-256 và journal phục hồi khi gián đoạn. Chặn sửa mod khi game đang chạy và khi file đích đã bị công cụ khác thay đổi.

```text
MyMod.zip
  modinfo.ini
  natives/stm/...
  reframework/autorun/example.lua
  reframework/plugins/example.dll
  reframework/data/...
```

Lua đơn vào `reframework/autorun/`, DLL đơn vào `reframework/plugins/`; riêng `dinput8.dll` vào gốc game. Thư mục `autorun/` và `plugins/` ở gốc được đưa vào `reframework/`. Một lớp thư mục bọc ngoài archive được bỏ tự động.

**PAK riêng:** nhập `.pak` trực tiếp hoặc trong ZIP/7z/RAR/thư mục. App kiểm tra header KPKA, triển khai vào `pak_mods/`, giữ tên file và chuẩn hóa đuôi `.pak` viết thường. Bật/tắt có journal, sao lưu và khôi phục file tồn tại; không sửa archive gốc của game. Có chặn xung đột đường dẫn đích; không phân tích asset/hash bên trong PAK để phát hiện mod ghi đè cùng asset.

Trong catalog hiện tại, cơ chế này dành cho **Requiem + REFramework có PAK Directory Loading**. Manager kiểm tra dấu hiệu loader trong DLL và `IntegrityCheckBypass_LoadPakDirectory` trong `re2_fw_config.txt`; nếu tắt, mở REFramework → PAK Directory Loading → Enable, đóng game rồi bật mod. Upstream giới hạn tính năng này ở TDB ≥ 81; một DLL universal có chuỗi PAK không chứng minh game cũ tương thích. [Mã nguồn REFramework](https://github.com/praydog/REFramework/blob/master/src/mods/IntegrityCheckBypass.cpp).

RE2/RE3/RE4/RE7/Village dùng bản loose files tương thích. Chưa hỗ trợ sửa/vô hiệu hóa PAK kiểu Fluffy, FOMOD, repack hoặc tự chọn biến thể mod. Với archive nhiều lựa chọn, giải nén rồi nhập đúng thư mục biến thể. `natives` cần loader và định dạng asset tương thích; copy thành công không chứng minh game đã nạp mod.

Nhận diện REFramework dựa vào DLL/cấu hình; không khẳng định DLL chưa rõ nguồn là REFramework tương thích. Có đọc Loose File Loader; người dùng bật loader theo hướng dẫn [REFramework](https://github.com/praydog/REFramework). App không tự tải/cài loader và không chạy script cài đặt trong archive.

ZIP/7z đã có bộ giải nén kèm theo. RAR nén có thể cần UnRAR/7-Zip trên PATH; có thể giải nén bằng công cụ ngoài rồi thêm thư mục. Không hỗ trợ archive có mật khẩu. Chặn đường dẫn vượt thư mục, symlink, ADS, tên thiết bị Windows, tên trùng không phân biệt hoa/thường và archive vượt giới hạn.

## Nexus Mods

Mở tài khoản Nexus trong app, lấy **Personal API key** ở [API Access](https://www.nexusmods.com/users/myaccount?tab=api+access), dán và đăng nhập. Không nhập mật khẩu Nexus vào app. Tùy chọn ghi nhớ dùng Windows DPAPI, không lưu key dạng plaintext.

**Nhiều tài khoản:** bấm nút Nexus/tên tài khoản ở góc trên → **Thêm tài khoản**. Mỗi tài khoản có key riêng và hiển thị Free/Premium. Chọn một dòng rồi **Dùng tài khoản** để chuyển; app xác thực lại trước khi thay tài khoản đang dùng. Chuyển thất bại giữ nguyên phiên hiện tại. Thêm lại cùng user ID cập nhật key, không tạo bản trùng.

**Ngắt kết nối** giữ các tài khoản đã lưu; **Xóa đăng nhập** chỉ quên key của tài khoản được chọn trên máy này. Bỏ chọn lưu bằng DPAPI để đăng nhập chỉ trong phiên; tài khoản đó không tồn tại sau khi đóng app. Các tài khoản khác không bị xóa. Tài khoản được chọn gần nhất được khôi phục khi mở lại, trừ khi đã ngắt kết nối hoặc chỉ đăng nhập trong phiên.

Kho `nexus.accounts` mã hóa cả key, thông tin tài khoản và lựa chọn bằng DPAPI, gắn với Windows user hiện tại. `nexus.key` cũ được chuyển sang kho mới mà không cần Internet; key cũ chỉ được xóa sau khi ghi kho mã hóa thành công. Mục **Tài khoản từ bản cũ** nhận tên/Free/Premium sau khi xác thực. Kho lỗi được giữ nguyên, không tự ghi đè.

Tải mod dùng tài khoản đang chọn. Không đổi tài khoản trong lúc đang tải; link NXM thuộc tài khoản khác bị từ chối, hãy chọn đúng tài khoản và mở/dán lại link. Không tự xoay tài khoản khi gặp giới hạn API.

- Duyệt trending, mở mod bằng ID/URL, chọn file, theo dõi tiến độ và hủy tải.
- Premium tải trực tiếp qua API. Free mở trang file để dùng Download with Manager hoặc tải thủ công.
- Có thể đăng ký `nxm://` trong Thiết lập hoặc dán link NXM hợp lệ còn hạn. Đăng ký thay handler Nexus của tài khoản Windows hiện tại, chỉ thực hiện khi bạn chọn.
- Link chuyển đến phiên đang mở qua inbox mã hóa; không gửi API key sang CDN.

Browser SSO cần `application_slug` do Nexus cấp cho ứng dụng này. Khi được cấp, đặt `RE_MANAGER_NEXUS_SSO_SLUG` trước khi chạy EXE để hiện nút SSO. Thư viện websocket đã đóng gói. Tham khảo [SSO demo](https://github.com/Nexus-Mods/sso-integration-demo); bản hiện tại dùng API key nếu chưa đăng ký SSO.

## Dữ liệu

Mặc định `%LOCALAPPDATA%\REmmanager`. Nếu đã có `%LOCALAPPDATA%\REEngineModManager`, app tiếp tục dùng thư viện cũ để giữ backup và trạng thái triển khai. Runtime cache ở `%LOCALAPPDATA%\REmmanager\runtime`.

```text
settings.json     đường dẫn game, theme, ngôn ngữ, onboarding
library.json      catalog mod và quyền sở hữu file theo bản cài
nexus.accounts    kho nhiều tài khoản được Windows DPAPI mã hóa
nexus.key         key phiên bản cũ, chuyển tự động khi nâng cấp
mods/             payload mod
backups/          bản sao file gốc
transactions/     journal phục hồi
downloads/        archive Nexus
inbox/            link NXM mã hóa, xóa sau khi nhận
```

Chọn thư mục khác: `REmmanager.exe --data-dir "D:\REModLibrary"`. Không xóa thư viện trong lúc mod còn bật. Nếu file đã bị thay đổi ngoài manager, kiểm tra file và backup trước khi phục hồi. Tắt mod trước khi cập nhật game.

## Build và kiểm tra

Source build cần Windows x64, Python 3.11+ có pip và Internet. Script tải .NET SDK, CPython embeddable và NuGet vào `.build-tools`; không cài SDK toàn hệ thống.

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_winui.ps1
python tools/verify_ui.py --screenshots artifacts/winui
python tools/package_source.py
```

Build dùng .NET SDK 8.0.425, Windows App SDK 2.5.1, Python 3.13.9 và dependencies trong `tools/backend-requirements.txt`. Đầu ra `dist/REmmanager.exe`. Thêm `-Configuration Debug` để build Debug; dùng `-OutputDirectory artifacts/debug` để lưu riêng. Debug tắt tối ưu managed và nhúng symbol gỡ lỗi managed vào EXE. `main.py` và `launch.bat` là launcher của EXE đã build, không phải GUI Python độc lập.

### Build bằng GitHub Actions

Mở **Actions → Build and publish → Run workflow**, chọn nhánh `main` hoặc nhánh phiên bản, rồi chọn **Release** hay **Debug**. Workflow chỉ chạy thủ công; commit, push, pull request và tag không tự kích hoạt build. Xem [hướng dẫn chạy workflow của GitHub](https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow).

Sau khi build và vượt qua các test trên Windows x64, workflow đưa `REmmanager.exe` cùng `REmmanager.sha256` lên GitHub Releases. Phiên bản trong `pyproject.toml`, engine Python và project WinUI phải trùng nhau. Mỗi loại build và phiên bản có bộ đếm riêng:

- Release: `main-0.5.2-001`, `main-0.5.2-002`, …; bản chính thức, đánh dấu Latest.
- Debug: `debug-0.5.2-001`, `debug-0.5.2-002`, …; đánh dấu pre-release, giữ nguyên Latest.

Tag trỏ đúng commit được chọn lúc chạy. Các lượt xuất bản chạy lần lượt giữa các nhánh; không ghi đè tag hay release cũ. Nếu upload lỗi, release giữ ở dạng draft để kiểm tra và giữ số thứ tự đó; lượt sau dùng số mới. Workflow dùng `GITHUB_TOKEN` có sẵn với quyền `contents: write`, không cần token cá nhân. Build ở máy không tự xuất bản.

Ngoài 99 test backend, có 7 test xuất bản kiểm tra bộ đếm tag theo phiên bản/loại build, đồng bộ phiên bản, checksum, Debug pre-release và giữ draft nếu upload lỗi.

Kiểm thử core với runtime đóng gói:

```powershell
.\.build-tools\python\python.exe -c "import sys,unittest; sys.path.insert(0,'.'); r=unittest.TextTestRunner().run(unittest.defaultTestLoader.discover('tests')); sys.exit(not r.wasSuccessful())"
```

99 test backend đã qua, gồm nhiều tài khoản, DPAPI, chuyển lỗi, giữ các tài khoản khác, session-only và migration key cũ; cùng PAK/backup/rollback, archive không an toàn, Nexus mô phỏng, dừng đúng bản cài và onboarding. Có kiểm tra mặc định tiếng Anh và giữ lựa chọn tiếng Việt đã lưu. QA WinUI kiểm tra giao diện tiếng Anh khi khởi động mới, RE7 trên ba theme × hai ngôn ngữ, sáu banner, Fluent SVG, màu Windows, cửa sổ gọn, maximized/fullscreen, control native, reduced motion và hộp quản lý nhiều tài khoản Việt/Anh. Ảnh render từ cây XAML của app, không chụp desktop. Chưa kiểm tra nạp mod trong game thật hoặc tải Nexus bằng tài khoản thật; account QA dùng dữ liệu mô phỏng.

Tài liệu nằm trong `docs/`; README tiếng Anh giữ ở gốc dự án. Banner/artwork, font và icon đã đóng gói; nguồn/hash ở `re_manager/assets/sources.json`, giấy phép font ở `assets/fonts/OFL.txt`, icon ở `assets/icons/LICENSE.txt`. Runtime có giấy phép Python và các dependency kèm theo.
