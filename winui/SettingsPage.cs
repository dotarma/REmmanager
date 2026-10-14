using System.Text.Json.Nodes;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;

namespace REmmanager;

sealed partial class MainWindow
{
    private void BuildSettings()
    {
        var page = new StackPanel { Spacing = 16, MaxWidth = 730, HorizontalAlignment = HorizontalAlignment.Left };
        page.Children.Add(Text(L("Gọn gàng. Theo cách của bạn.", "Compact. Your way."), 28, true));
        var mode = new ComboBox { Header = L("Giao diện", "Theme"), MinWidth = 220, FontFamily = font };
        foreach (var value in new[] { ("light", "Light"), ("dark", "Dark"), ("oled", "OLED black") }) mode.Items.Add(new ComboBoxItem { Content = value.Item2, Tag = value.Item1 });
        mode.SelectedIndex = S(state["preferences"], "mode") switch { "light" => 0, "oled" => 2, _ => 1 };
        mode.SelectionChanged += async (_, _) => { if (mode.SelectedItem is ComboBoxItem item) await SavePreferences(new JsonObject { ["mode"] = item.Tag!.ToString() }); };
        var lang = new ComboBox { Header = L("Ngôn ngữ", "Language"), MinWidth = 180, FontFamily = font };
        lang.Items.Add(new ComboBoxItem { Content = "Tiếng Việt", Tag = "vi" }); lang.Items.Add(new ComboBoxItem { Content = "English", Tag = "en" }); lang.SelectedIndex = language == "en" ? 1 : 0;
        lang.SelectionChanged += async (_, _) => { if (lang.SelectedItem is ComboBoxItem item) await SavePreferences(new JsonObject { ["language"] = item.Tag!.ToString() }); };
        page.Children.Add(Row(mode, lang));
        page.Children.Add(Row(Fluent("settings"), Text(L("Màu nhấn theo Windows", "Windows accent color"), 15, true)));
        page.Children.Add(Text(L("Tự đồng bộ với Settings → Personalization → Colors của Windows, kể cả khi app đang mở.", "Automatically follows Windows Settings > Personalization > Colors, including changes while the app is open."), 13, false, "onSurfaceVariant"));
        page.Children.Add(Action(L("Mở cài đặt màu Windows", "Open Windows color settings"), () => { OpenUrl("ms-settings:colors"); return Task.CompletedTask; }, icon: "open"));
        var reduced = new ToggleSwitch { Header = L("Giảm chuyển động", "Reduce motion"), IsOn = Motion.Reduced, FontFamily = font };
        reduced.Toggled += async (_, _) => await SavePreferences(new JsonObject { ["reduced_motion"] = reduced.IsOn }); page.Children.Add(reduced);
        var speed = new Slider { Header = L("Tốc độ animation", "Animation speed"), Minimum = 0.5, Maximum = 1.5, StepFrequency = 0.1, Value = Motion.Speed, Width = 360, HorizontalAlignment = HorizontalAlignment.Left };
        AutomationProperties.SetName(speed, L("Tốc độ animation", "Animation speed"));
        speed.AddHandler(UIElement.PointerCaptureLostEvent, new PointerEventHandler(async (_, _) => { if (speed.IsLoaded) await SaveMotionSpeed(speed.Value); }), true);
        speed.KeyUp += async (_, _) => await SaveMotionSpeed(speed.Value);
        page.Children.Add(speed);
        page.Children.Add(Text(L("Google Sans Flex • Tôn trọng cài đặt giảm animation của Windows.", "Google Sans Flex • Respects Windows animation accessibility settings."), 12, false, "onSurfaceVariant"));
        page.Children.Add(Action(L("Xem lại hướng dẫn", "Show introduction"), Onboarding, icon: "book"));
        page.Children.Add(Action(L("Đăng ký nxm://", "Register nxm://"), RegisterNxm, icon: "link"));
        page.Children.Add(Action(L("Mở thư mục dữ liệu", "Open data folder"), () => { OpenFolder(dataDir); return Task.CompletedTask; }, icon: "folder"));
        page.Children.Add(Text(L("PAK riêng: Requiem + REFramework PAK Directory Loading. Lua / DLL / natives cần loader tương thích. ZIP, 7z, RAR; RAR nén có thể cần UnRAR/7-Zip.", "Standalone PAK: Requiem + REFramework PAK Directory Loading. Lua / DLL / natives need a compatible loader. ZIP, 7z, RAR; compressed RAR may need UnRAR/7-Zip."), 12, false, "onSurfaceVariant"));
        body.Children.Add(new ScrollViewer { Content = page, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled });
    }
    private JsonObject Preferences(JsonObject changed)
    {
        var values = new JsonObject { ["mode"] = S(state["preferences"], "mode", "dark"), ["seed"] = WindowsAccent(), ["preset"] = "windows", ["language"] = language };
        foreach (var entry in changed) values[entry.Key] = entry.Value?.DeepClone();
        return values;
    }
    private async Task SavePreferences(JsonObject changed)
    {
        if (closing || busy || engine is null) return;
        await Run(L("Đang áp dụng…", "Applying…"), async () => { SetState(await engine.Call("preferences", Preferences(changed))); Render(); Motion.Enter(body); });
    }
    private async Task SaveMotionSpeed(double value)
    {
        if (closing || busy || engine is null) return;
        try
        {
            Motion.Speed = value;
            SetState(await engine.Call("preferences", Preferences(new JsonObject { ["motion_speed"] = value })));
        }
        catch (Exception error) { if (!closing) SetStatus(error.Message); }
    }
    private async Task LoginAccount()
    {
        if (busy) return;
        var content = new StackPanel { Spacing = 12, Width = 390 };
        content.Children.Add(Text(L("Dùng Personal API key từ trang API Access của Nexus.", "Use a Personal API key from Nexus API Access.")));
        content.Children.Add(Text(L("Thêm tài khoản mới hoặc cập nhật key của tài khoản đã lưu.", "Add another account or update a saved account's key."), 12, false, "onSurfaceVariant"));
        var key = new PasswordBox { Header = "Nexus API key" };
        var remember = new CheckBox { Content = L("Lưu tài khoản này bằng Windows DPAPI", "Save this account with Windows DPAPI"), IsChecked = true };
        content.Children.Add(key); content.Children.Add(remember);
        content.Children.Add(Action(L("Mở trang API key", "Get an API key"), () => { OpenUrl("https://www.nexusmods.com/users/myaccount?tab=api+access"); return Task.CompletedTask; }, icon: "open"));
        // Registered-app SSO is opt-in; API-key login always works without an application slug.
        bool sso = false;
        var dialog = new ContentDialog { XamlRoot = root.XamlRoot, Title = L("Thêm tài khoản Nexus", "Add Nexus account"), Content = content,
            PrimaryButtonText = L("Đăng nhập", "Sign in"), CloseButtonText = L("Hủy", "Cancel"), RequestedTheme = root.RequestedTheme };
        if (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RE_MANAGER_NEXUS_SSO_SLUG")))
        {
            dialog.SecondaryButtonText = "Browser SSO";
            dialog.SecondaryButtonClick += (_, _) => sso = true;
        }
        dialogOpen = true; ContentDialogResult result;
        try { result = await dialog.ShowAsync(); } finally { dialogOpen = false; }
        if (result is ContentDialogResult.Primary or ContentDialogResult.Secondary)
            await Run(L("Xác thực Nexus…", "Validating Nexus…"), async () =>
            {
                try { SetState(await engine!.Call(sso ? "sso" : "login", new JsonObject { ["key"] = key.Password, ["remember"] = remember.IsChecked == true })); NexusContextChanged(); Render(); }
                finally { key.Password = ""; }
            }, sso);
    }
    private Task Onboarding() => RunOnboarding();
    private async Task RunOnboarding(Func<ContentDialog, Task>? verifier = null)
    {
        int step = 0;
        var wizard = new ContentDialog { XamlRoot = root.XamlRoot, Title = "REmmanager", PrimaryButtonText = L("Tiếp tục", "Continue"),
            CloseButtonText = L("Bỏ qua — đã sử dụng", "Skip — I've used this before"), RequestedTheme = root.RequestedTheme };
        var content = new StackPanel { Spacing = 14, Width = 420 }; wizard.Content = content;
        void ShowStep()
        {
            content.Children.Clear();
            string[] titles = { L("Chào mừng đến REmmanager", "Welcome to REmmanager"), L("1. Thêm game", "1. Add your game"), L("2. Nexus Mods — tùy chọn", "2. Nexus Mods — optional"), L("3. Thêm và bật mod", "3. Add and enable mods") };
            string[] descriptions =
            {
                L("Quản lý mod Resident Evil gọn nhẹ. Vài bước này giúp bạn bắt đầu; lần sau app mở thẳng thư viện.", "A compact Resident Evil mod manager. These steps help you get started; next time the app opens directly to the library."),
                L("Quét Steam/Epic hoặc chọn thư mục chứa re2/re3/re4/re7/re8/re9.exe từ thanh bên.", "Scan Steam/Epic or choose the folder containing re2/re3/re4/re7/re8/re9.exe from the sidebar."),
                L("Kết nối bằng Personal API key. Free dùng Download with Manager hoặc tải thủ công; Premium tải trực tiếp. Mod thủ công không cần đăng nhập.", "Connect using a Personal API key. Free uses Download with Manager or manual downloads; Premium downloads directly. Manual mods need no sign-in."),
                L("Thêm ZIP/7z/RAR, PAK, Lua, DLL hoặc thư mục rồi Bật mod. PAK riêng cần Requiem + REFramework PAK Directory Loading. App sao lưu file gốc. Lưu game trước khi dùng Dừng game.", "Add ZIP/7z/RAR, PAK, Lua, DLL or a folder, then Enable mod. Standalone PAK requires Requiem + REFramework PAK Directory Loading. Original files are backed up. Save before using Stop game.")
            };
            content.Children.Add(Text(titles[step], 24, true)); content.Children.Add(Text(descriptions[step], 14));
            content.Children.Add(Text($"{step + 1} / 4", 11, false, "onSurfaceVariant"));
            if (step == 1)
            {
                var scanStatus = Text("");
                content.Children.Add(Action(L("Quét ngay", "Scan now"), async () =>
                {
                    try { SetState(await engine!.Call("scan")); scanStatus.Text = $"{state["installations"]!.AsArray().Count} " + L("bản cài đã nhận diện", "installations found"); }
                    catch (Exception e) { scanStatus.Text = e.Message; }
                }));
                content.Children.Add(scanStatus);
            }
            wizard.PrimaryButtonText = step == 3 ? L("Bắt đầu", "Get started") : L("Tiếp tục", "Continue");
            Motion.Enter(content, true);
        }
        ShowStep();
        wizard.PrimaryButtonClick += (_, args) => { if (step < 3) { args.Cancel = true; step++; ShowStep(); } };
        dialogOpen = true;
        try
        {
            var showing = wizard.ShowAsync();
            if (verifier is not null) await verifier(wizard);
            await showing;
        }
        finally { dialogOpen = false; }
        SetState(await engine!.Call("preferences", Preferences(new JsonObject { ["onboarding_done"] = true }))); await RefreshMods(); Render();
    }
}
