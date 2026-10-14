# REmmanager — WinUI 3 / Material 3 Expressive

Giao diện native C# WinUI 3 giao tiếp với engine Python qua JSON-lines. Không dùng Tkinter, Qt hoặc WebView. Thay đổi GUI không thay thế cơ chế triển khai/backup mod của engine.

App mặc định tiếng Anh khi chưa có ngôn ngữ hợp lệ đã lưu. Engine và WinUI cùng dùng fallback `en`; người dùng đã chọn `vi` vẫn giữ lựa chọn đó. Tài liệu tiếng Anh nằm ở [README.md](../README.md), bản tiếng Việt ở [README_VI.md](README_VI.md).

## Bố cục

Cửa sổ mặc định 1000 × 740; QA kiểm tra 940 × 700. Thanh bên 182 px chứa sáu game, thêm/quét game và Settings. Nội dung gồm banner, chọn bản cài, thư viện/Nexus, danh sách và hành động mod. Footer chứa trạng thái, ProgressBar và hủy tải. Settings cuộn riêng.

Hero có hàng ảnh và hàng thông tin riêng. Tên game tối đa hai dòng, năm ở dưới; nút Chạy trực tiếp và Dừng game ở bên phải theo trạng thái tiến trình. Thông tin không phủ lên ảnh.

Banner dùng `Image.Stretch=Uniform`, giữ toàn bộ tỷ lệ ảnh. Kích thước ảnh là `min(chiều rộng khả dụng / tỷ lệ nguồn, chiều cao còn lại sau khi dành chỗ cho caption và thao tác mod)`; không còn giới hạn cố định 280 px. Ảnh đầy chiều rộng khi đủ chỗ; cửa sổ ultrawide thấp thu toàn ảnh và căn giữa, không crop. Bỏ lớp che trái; tên/năm/nút chạy nằm dưới ảnh. Gradient chỉ áp dụng cho 24 DIP cuối của khung ảnh thực tế, lấy đúng surface của Light/Dark/OLED.

Title bar dùng `ExtendsContentIntoTitleBar` / `SetTitleBar`, màu caption khớp theme. Windows quản lý nút caption, kéo, phóng to và đóng. Google Sans Flex được nạp bằng URI asset; font và artwork không cần tải khi khởi động.

## Token và control

Vai trò màu: surface, surfaceContainerLowest/Low/High, onSurface, onSurfaceVariant, primary/onPrimary và primaryContainer/onPrimaryContainer. Python tạo palette từ Windows accent với hiệu chỉnh tương phản; không dùng HCT. WinUI đọc `UISettings.GetColorValue(UIColorType.Accent)`, lắng nghe `ColorValuesChanged`, đồng bộ trên UI thread khi hết tác vụ/hộp thoại. Light, Dark, OLED giữ nguyên; bỏ preset/custom. OLED dùng surface đen tuyệt đối. Màu Windows là seed, primary có điều chỉnh độ sáng theo theme để giữ tương phản.

Button, ListView, TextBox, ComboBox, ToggleSwitch, **Slider và ProgressBar là WinUI native**. File/folder picker dùng Windows, được gắn HWND. Icon dùng path vector từ [Microsoft Fluent System Icons](https://github.com/microsoft/fluentui-system-icons), render bằng PathIcon, không phụ thuộc font icon/glyph Unicode. SVG và MIT license đã vendored. Icon trang trí có AccessibilityView.Raw; nút giữ tên mô tả qua AutomationProperties.Name. Input/password dùng semantics native và focus của Windows. VI/EN dùng chung bố cục; tiêu đề dài được wrap hoặc giới hạn rõ ràng.

## Motion

Icon giữ khung nguồn SVG 20 × 20, căn giữa theo chiều ngang/dọc và dùng layout rounding. Không ép PathIcon về 16 × 16 vì đường vector vẫn theo tọa độ nguồn, gây cắt nét phải/dưới. Nội dung nút căn giữa theo chiều dọc; icon trang trí không nhận hit test.

`Motion.cs` ánh xạ token Material 3 Expressive sang Windows Composition:

| Token | Damping ratio | Stiffness |
| --- | ---: | ---: |
| Default spatial | 0.8 | 380 |
| Fast spatial | 0.6 | 800 |
| Default effects | 1.0 | 1600 |

Chu kỳ spring là `2π / sqrt(stiffness) / speed`. Chuyển trang dùng translation spring và opacity hiệu ứng tắt dần đơn điệu; nhấn nút scale phản hồi rồi hồi phục bằng fast spatial. Không làm opacity overshoot. Hướng dẫn lần đầu dùng motion cho vùng nội dung, không chạy animation toàn màn hình liên tục.

Tôn trọng `UISettings.AnimationsEnabled` và tùy chọn Reduce motion; khi giảm chuyển động thì dừng animation và áp dụng giá trị cuối. Slider tốc độ native từ 0.5 đến 1.5. Đây là ánh xạ theo token, không phải thư viện Material chính thức cho WinUI.

Nguồn: [Material 3 motion](https://m3.material.io/styles/motion/overview), [AndroidX ExpressiveMotionTokens](https://github.com/androidx/androidx/blob/androidx-main/compose/material3/material3/src/commonMain/kotlin/androidx/compose/material3/tokens/ExpressiveMotionTokens.kt), [Windows Composition springs](https://learn.microsoft.com/en-us/windows/apps/develop/composition/spring-animations).

## Onboarding và kiểm tra

Nút Nexus/tên tài khoản mở ContentDialog quản lý nhiều tài khoản. ListView chọn đơn hiển thị tên, Free/Premium, kiểu lưu và dấu Current; chọn dòng không tự chuyển. Primary là Add account, Secondary là Use account (vô hiệu hóa với tài khoản đang dùng), Close riêng. Remove login là hành động error có xác nhận; Disconnect giữ tài khoản đã lưu. Dialog thêm tài khoản chỉ yêu cầu API key, có tùy chọn DPAPI/session-only và SSO khi được cấu hình. Hộp thoại trước đóng rồi mới mở hộp tiếp theo, tránh modal lồng nhau. Chuyển thành công làm mới dữ liệu Nexus; lỗi giữ phiên hiện tại.

ContentDialog bốn bước có Tiếp tục/Bắt đầu và Bỏ qua. Hoàn tất hoặc bỏ qua lưu `onboarding_done`; người đã có thư viện bỏ qua tự động. Settings cho xem lại. Dừng game có xác nhận; buộc dừng là lựa chọn riêng khi game không phản hồi.

`VerifyUi.cs` render cây XAML với RenderTargetBitmap, kiểm tra bounds tên/năm RE7 ở sáu tổ hợp theme/ngôn ngữ, hành động thư viện ở cửa sổ gọn, Slider/ProgressBar native, reduced motion và giữ lựa chọn khi đổi màu. Unit test kiểm tra lưu onboarding và chống dừng sai bản cài/PID tái sử dụng. Không giả nhận thử nghiệm với game/tài khoản Nexus thật.
