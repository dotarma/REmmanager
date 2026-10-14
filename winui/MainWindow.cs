using System.Diagnostics;
using System.Text.Json.Nodes;
using Microsoft.UI;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Windows.Foundation;
using Windows.Storage;
using Windows.UI;

namespace REmmanager;

sealed partial class MainWindow : Window
{
    private Backend? engine;
    private JsonObject state = new();
    private JsonArray mods = new(), nexusItems = new();
    private readonly Grid root = new();
    private Grid workspace = new(), body = new(), interaction = new();
    private TextBlock status = new(), framework = new(), detail = new(), heroTitle = new(), heroYear = new();
    private Border hero = new();
    private Grid heroArtwork = new(), heroCaption = new();
    private GradientStop bannerFadeStart = new();
    private Image bannerImage = new();
    private PathIcon frameworkIcon = new();
    private double bannerAspect = 1920.0 / 620;
    private ProgressBar progress = new();
    private Button launch = new(), stop = new(), toggle = new(), remove = new(), cancel = new();
    private ListView modList = new(), nexusList = new();
    private TextBox search = new(), nexusQuery = new(), nxmInput = new();
    private string game = "re2", installation = "", destination = "mods", language = "en";
    private string filter = "", query = "", nxm = "", selectedMod = "";
    private int nexusMod;
    private bool filesMode, busy, cancellable, running, polling, initialized, dialogOpen, closing;
    private JsonNode? frameworkData;
    private readonly bool demo;
    private readonly string dataDir;
    private readonly string? qaFolder;
    private readonly DispatcherTimer pollTimer = new() { Interval = TimeSpan.FromSeconds(2) };
    private readonly FontFamily font = new("ms-appx:///Assets/fonts/GoogleSansFlex.ttf#Google Sans Flex");
    private long bannerGeneration;

    public MainWindow()
    {
        Title = "REmmanager";
        demo = Program.Arguments.Contains("--demo");
        string? Arg(string key) { int i = Array.IndexOf(Program.Arguments, key); return i >= 0 && i + 1 < Program.Arguments.Length ? Program.Arguments[i + 1] : null; }
        dataDir = Arg("--data-dir") ?? (demo ? Path.Combine(Path.GetTempPath(), "REmmanager-demo-" + Guid.NewGuid().ToString("N")) : Backend.DefaultDataDir);
        qaFolder = Arg("--qa");
        ExtendsContentIntoTitleBar = true;
        AppWindow.Resize(new Windows.Graphics.SizeInt32(1000, 740));
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(40) });
        root.RowDefinitions.Add(new RowDefinition());
        Content = root;
        root.Loaded += async (_, _) => { if (!initialized) { initialized = true; await Initialize(); } };
        AppWindow.Closing += (window, args) =>
        {
            if (busy) { args.Cancel = true; if (cancellable) _ = engine?.Call("cancel"); SetStatus(L("Chờ thao tác hoàn tất rồi đóng cửa sổ.", "Wait for the operation to finish before closing.")); }
        };
        windowsColors.ColorValuesChanged += WindowsColorsChanged;
        Closed += (_, _) => { closing = true; windowsColors.ColorValuesChanged -= WindowsColorsChanged; pollTimer.Stop(); engine?.Dispose(); Application.Current.Exit(); };
        pollTimer.Tick += async (_, _) => await Poll();
        Render();
    }

    private string L(string vi, string en) => language == "en" ? en : vi;
    private static string S(JsonNode? node, string key, string fallback = "") => node?[key]?.ToString() ?? fallback;
    private static bool B(JsonNode? node, string key) => node?[key]?.GetValue<bool>() ?? false;
    private JsonObject? CurrentInstall => (state["installations"] as JsonArray)?.OfType<JsonObject>().FirstOrDefault(i => S(i, "id") == installation);
    private JsonObject? CurrentGame => (state["games"] as JsonArray)?.OfType<JsonObject>().FirstOrDefault(g => S(g, "key") == game);
    private JsonObject? CurrentMod => mods.OfType<JsonObject>().FirstOrDefault(m => S(m, "id") == selectedMod);
    private static Color ColorOf(string value) => Color.FromArgb(255, Convert.ToByte(value[1..3], 16), Convert.ToByte(value[3..5], 16), Convert.ToByte(value[5..7], 16));
    private SolidColorBrush Brush(string role) => new(ColorOf(S(state["roles"], role, role == "onSurface" ? "#e9ede5" : "#141814")));
    private TextBlock Text(string value, double size = 13, bool emphasis = false, string role = "onSurface") => new()
    {
        Text = value, FontSize = size, FontFamily = font, Foreground = Brush(role), TextWrapping = TextWrapping.Wrap,
        FontWeight = emphasis ? Microsoft.UI.Text.FontWeights.SemiBold : Microsoft.UI.Text.FontWeights.Normal
    };
    private Button Action(string text, Func<Task> action, bool primary = false, string? icon = null)
    {
        var control = new Button { FontFamily = font, MinHeight = 34, VerticalContentAlignment = VerticalAlignment.Center, Padding = new Thickness(12, 6, 12, 6), CornerRadius = new CornerRadius(primary ? 16 : 8) };
        ButtonLabel(control, text, icon);
        if (primary) { control.Background = Brush("primary"); control.Foreground = Brush("onPrimary"); }
        control.Click += async (_, _) => { if (busy && !ReferenceEquals(control, cancel)) return; try { await action(); } catch (Exception e) { await Error(e.Message); } };
        AutomationProperties.SetName(control, text); Motion.WirePress(control);
        return control;
    }
    private StackPanel Row(params UIElement[] children)
    {
        var result = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8, VerticalAlignment = VerticalAlignment.Center };
        foreach (var child in children) result.Children.Add(child);
        return result;
    }
    private Grid Split(FrameworkElement left, FrameworkElement right)
    {
        var result = new Grid { ColumnSpacing = 12 };
        result.ColumnDefinitions.Add(new ColumnDefinition());
        result.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        result.Children.Add(left); Grid.SetColumn(right, 1); result.Children.Add(right);
        return result;
    }
    private void SetStatus(string text) => status.Text = text;

    private async Task Initialize()
    {
        try
        {
            SetStatus(L("Đang mở thư viện…", "Opening library…"));
            engine = await Task.Run(() => new Backend(dataDir, demo));
            engine.Event += data => DispatcherQueue.TryEnqueue(() =>
            {
                if (S(data, "event") == "progress")
                {
                    double total = data["total"]?.GetValue<double>() ?? 0, current = data["current"]?.GetValue<double>() ?? 0;
                    progress.IsIndeterminate = total <= 0;
                    if (total > 0) progress.Value = current / total * 100;
                    SetStatus($"{L("Đang tải", "Downloading")} • {current / 1048576:F1} / {total / 1048576:F1} MB");
                }
                else if (S(data, "event") == "browser") OpenUrl(S(data, "url"));
            });
            SetState(await engine.Call("state"));
            await SyncWindowsAccent();
            await RefreshMods(); Render();
            if (!B(state["settings"], "onboarding_done") && !demo && qaFolder is null) await Onboarding();
            if (!demo && qaFolder is null) await Run(L("Đang quét game…", "Scanning game libraries…"), async () =>
            {
                SetState(await engine.Call("scan"));
                try { SetState(await engine.Call("restore_login")); } catch (Exception e) { SetStatus(e.Message); }
                await RefreshMods(); Render();
            });
            pollTimer.Start();
            if (qaFolder is not null) await VerifyUi(qaFolder);
            else if (Program.Arguments.Contains("--smoke-test")) { await Task.Delay(2000); Close(); }
        }
        catch (Exception e)
        {
            File.WriteAllText(Path.Combine(Path.GetTempPath(), "REmmanager-startup-error.txt"), e.ToString());
            if (qaFolder is not null) { File.WriteAllText(Path.Combine(qaFolder, "error.txt"), e.ToString()); Application.Current.Exit(); }
            else await Error(e.Message);
        }
    }
    private void SetState(JsonNode value)
    {
        state = (JsonObject)value; language = S(state["preferences"], "language", "en");
        Motion.Reduced = B(state["settings"], "reduced_motion");
        Motion.Speed = Math.Clamp(state["settings"]?["motion_speed"]?.GetValue<double>() ?? 1, 0.5, 1.5);
        if (string.IsNullOrEmpty(installation) || CurrentInstall is null)
        {
            var installs = (state["installations"] as JsonArray)?.OfType<JsonObject>().ToList() ?? [];
            var chosen = installs.FirstOrDefault(i => S(i, "game") == S(state["settings"], "selected_game")) ?? installs.FirstOrDefault();
            installation = S(chosen, "id"); game = S(chosen, "game", game);
        }
    }
    private void Render()
    {
        root.Children.Clear();
        root.RequestedTheme = S(state["preferences"], "mode", "dark") == "light" ? ElementTheme.Light : ElementTheme.Dark;
        root.Background = Brush("surface");
        root.Resources["SystemAccentColor"] = ColorOf(WindowsAccent());
        root.Resources["AccentFillColorDefaultBrush"] = Brush("primary");
        var caption = new Grid { Background = Brush("surfaceContainerLow"), Padding = new Thickness(16, 0, 160, 0) };
        var brand = Text("REmmanager", 13, true); brand.VerticalAlignment = VerticalAlignment.Center; caption.Children.Add(brand);
        root.Children.Add(caption); SetTitleBar(caption);
        AppWindow.TitleBar.ButtonBackgroundColor = ColorOf(S(state["roles"], "surfaceContainerLow", "#171b17"));
        AppWindow.TitleBar.ButtonInactiveBackgroundColor = AppWindow.TitleBar.ButtonBackgroundColor;
        AppWindow.TitleBar.ButtonForegroundColor = ColorOf(S(state["roles"], "onSurface", "#e9ede5"));
        workspace = new Grid();
        workspace.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(182) }); workspace.ColumnDefinitions.Add(new ColumnDefinition());
        Grid.SetRow(workspace, 1); root.Children.Add(workspace);
        var navigation = new Grid { Background = Brush("surfaceContainerLowest"), Padding = new Thickness(10, 16, 10, 12), RowSpacing = 12 };
        navigation.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto }); navigation.RowDefinitions.Add(new RowDefinition()); navigation.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        navigation.Children.Add(Text("REmmanager", 20, true, "primary"));
        var sidebar = new StackPanel { Spacing = 4 };
        Grid.SetRow(sidebar, 1); navigation.Children.Add(sidebar);
        sidebar.Children.Add(Text(L("GAME CỦA BẠN", "YOUR GAMES"), 10, true, "onSurfaceVariant"));
        foreach (var item in (state["games"] as JsonArray ?? new()).OfType<JsonObject>())
        {
            string key = S(item, "key");
            var install = (state["installations"] as JsonArray)?.OfType<JsonObject>().FirstOrDefault(i => S(i, "game") == key);
            string name = S(item, "title").Replace("Resident Evil ", "RE ").Replace(": Biohazard", "");
            var entry = Action(name, async () =>
            {
                if (busy) return;
                game = key; installation = S(install, "id"); selectedMod = ""; mods = new(); nexusItems = new(); filesMode = false;
                destination = "mods"; running = false; await RefreshMods(); Render(); Motion.Enter(body);
            }, icon: game == key ? "check" : "games");
            entry.HorizontalAlignment = HorizontalAlignment.Stretch; entry.HorizontalContentAlignment = HorizontalAlignment.Left; entry.Margin = new Thickness(0, 3, 0, 0);
            if (game == key) { entry.Background = Brush("primaryContainer"); entry.Foreground = Brush("onPrimaryContainer"); }
            sidebar.Children.Add(entry);
            sidebar.Children.Add(Text(install is null ? L("Chưa phát hiện", "Not detected") : S(install, "source").Replace("Thủ công", L("Thủ công", "Manual")), 10, false, "onSurfaceVariant"));
        }
        var footerNav = new StackPanel { Spacing = 7 };
        footerNav.Children.Add(Action(L("Thêm game", "Add game"), AddGame, icon: "add"));
        var scanGames = Action(L("Quét game", "Scan games"), async () => await Run(L("Đang quét…", "Scanning…"), async () => { SetState(await engine!.Call("scan")); await RefreshMods(); Render(); }), icon: "refresh");
        ToolTipService.SetToolTip(scanGames, L("Quét thư viện Steam / Epic", "Scan Steam / Epic libraries"));
        footerNav.Children.Add(scanGames);
        footerNav.Children.Add(Action(L("Thiết lập", "Settings"), () => Navigate("settings"), icon: "settings"));
        footerNav.Children.Add(Text("v0.5.2", 10, false, "onSurfaceVariant"));
        Grid.SetRow(footerNav, 2); navigation.Children.Add(footerNav); workspace.Children.Add(navigation);
        var content = new Grid { Margin = new Thickness(20, 12, 20, 12), RowSpacing = 10 };
        content.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto }); content.RowDefinitions.Add(new RowDefinition()); content.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        Grid.SetColumn(content, 1); workspace.Children.Add(content);
        int accountCount = (state["accounts"] as JsonArray)?.Count ?? 0;
        string account = state["account"] is null ? (accountCount > 0 ? L("Tài khoản Nexus", "Nexus accounts") + $" ({accountCount})" : L("Kết nối Nexus", "Connect Nexus")) : S(state["account"], "name") + (B(state["account"], "is_premium") ? " / Premium" : " / Free");
        var accountButton = Action(account, Account, icon: "person");
        ToolTipService.SetToolTip(accountButton, L("Quản lý tài khoản Nexus", "Manage Nexus accounts") + $" ({accountCount})");
        content.Children.Add(Split(Text(destination == "settings" ? L("Thiết lập", "Settings") : L("Thư viện mod", "Mod library"), 24, true), accountButton));
        body = new Grid(); Grid.SetRow(body, 1); content.Children.Add(body);
        interaction = body;
        if (destination == "settings") BuildSettings();
        else
        {
            body.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto }); body.RowDefinitions.Add(new RowDefinition());
            BuildHero();
            body.SizeChanged += (_, _) => UpdateBannerLayout();
            var header = new StackPanel { Spacing = 8 }; header.Children.Add(hero);
            framework = Text(L("Chọn game để kiểm tra REFramework.", "Choose a game to check REFramework."), 12, false, "onSurfaceVariant"); framework.MaxWidth = 340;
            frameworkIcon = Fluent("info"); frameworkIcon.Foreground = Brush("onSurfaceVariant"); UpdateFramework();
            header.Children.Add(Split(Row(frameworkIcon, framework), Row(Action(L("Kiểm tra", "Refresh"), async () => { await RefreshMods(); UpdateFramework(); FillMods(); }, icon: "refresh"), Action("REFramework", () => { OpenUrl("https://github.com/praydog/REFramework/releases"); return Task.CompletedTask; }, icon: "open"))));
            header.Children.Add(Row(Action(L("Mod đã thêm", "Installed mods"), () => Navigate("mods"), icon: "library"), Action("Nexus Mods", () => Navigate("nexus"), icon: "download"))); body.Children.Add(header);
            var data = new Grid { Margin = new Thickness(0, 10, 0, 0), RowSpacing = 8 };
            Grid.SetRow(data, 1); body.Children.Add(data); if (destination == "mods") BuildMods(data); else BuildNexus(data);
        }
        status = Text(demo ? L("DEMO • Không chạy hoặc dừng game thật.", "DEMO • Real games are not launched or stopped.") : L("Sẵn sàng", "Ready"), 11, false, "onSurfaceVariant");
        status.MaxLines = 2; status.TextTrimming = TextTrimming.CharacterEllipsis;
        progress = new ProgressBar { Width = 108, Minimum = 0, Maximum = 100, VerticalAlignment = VerticalAlignment.Center, Visibility = busy ? Visibility.Visible : Visibility.Collapsed, IsIndeterminate = busy };
        AutomationProperties.SetName(progress, L("Tiến độ tác vụ", "Operation progress"));
        cancel = Action(L("Hủy", "Cancel"), async () => await engine!.Call("cancel"), icon: "dismiss"); cancel.Visibility = cancellable ? Visibility.Visible : Visibility.Collapsed;
        var footer = Split(status, Row(progress, cancel)); Grid.SetRow(footer, 2); content.Children.Add(footer);
        navigation.IsHitTestVisible = !busy; body.IsHitTestVisible = !busy;
    }

    private void BuildHero()
    {
        hero = new Border { Background = Brush("surface"), Child = new Grid { RowSpacing = 8 } };
        var grid = (Grid)hero.Child;
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        heroArtwork = new Grid { Height = 190, HorizontalAlignment = HorizontalAlignment.Center };
        bannerImage = new Image { Stretch = Stretch.Uniform, HorizontalAlignment = HorizontalAlignment.Stretch, VerticalAlignment = VerticalAlignment.Stretch };
        heroArtwork.Children.Add(bannerImage);
        grid.Children.Add(heroArtwork);
        var surface = ColorOf(S(state["roles"], "surface", "#141814"));
        var clear = Color.FromArgb(0, surface.R, surface.G, surface.B);
        var bottomFade = new LinearGradientBrush { StartPoint = new Point(0.5, 0), EndPoint = new Point(0.5, 1) };
        bottomFade.GradientStops.Add(new GradientStop { Color = clear, Offset = 0 });
        bannerFadeStart = new GradientStop { Color = clear, Offset = 0.9 };
        bottomFade.GradientStops.Add(bannerFadeStart);
        bottomFade.GradientStops.Add(new GradientStop { Color = surface, Offset = 1 });
        heroArtwork.Children.Add(new Border { Background = bottomFade, IsHitTestVisible = false });
        hero.SizeChanged += (_, _) => UpdateBannerLayout();
        heroCaption = new Grid { ColumnSpacing = 16 };
        heroCaption.ColumnDefinitions.Add(new ColumnDefinition()); heroCaption.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var labels = new StackPanel { Spacing = 3 };
        heroTitle = Text(S(CurrentGame, "title", "Resident Evil"), 24, true); heroTitle.LineHeight = 28; heroTitle.MaxLines = 2; heroTitle.TextTrimming = TextTrimming.CharacterEllipsis;
        heroTitle.HorizontalAlignment = HorizontalAlignment.Left; labels.Children.Add(heroTitle);
        heroYear = Text(S(CurrentGame, "year") + " / RE ENGINE", 11, false, "onSurfaceVariant"); heroYear.VerticalAlignment = VerticalAlignment.Center;
        labels.Children.Add(heroYear); heroCaption.Children.Add(labels);
        launch = Action(L("Chạy trực tiếp", "Launch directly"), async () => await LaunchGame(false), true, "play"); launch.IsEnabled = CurrentInstall is not null && B(CurrentInstall, "available") && !running;
        stop = Action(L("Dừng game", "Stop game"), StopGame, icon: "stop"); stop.Foreground = Brush("error"); stop.Visibility = running ? Visibility.Visible : Visibility.Collapsed;
        var steam = Action("Steam", async () => await LaunchGame(true), icon: "play"); steam.Visibility = S(CurrentInstall, "source") == "Steam" ? Visibility.Visible : Visibility.Collapsed;
        var actions = Row(steam, launch, stop); Grid.SetColumn(actions, 1); heroCaption.Children.Add(actions);
        Grid.SetRow(heroCaption, 1); grid.Children.Add(heroCaption);
        heroCaption.SizeChanged += (_, _) => UpdateBannerLayout();
        long generation = ++bannerGeneration; _ = LoadBanner(bannerImage, game, generation);
    }
    private void UpdateBannerLayout()
    {
        if (destination == "settings" || hero.ActualWidth <= 0 || body.ActualHeight <= 0) return;
        // Keep room for the caption, framework/tabs and usable mod controls.
        // On a tall/fullscreen window the image fills the available width;
        // short ultrawide windows fit the whole image without cropping.
        double captionHeight = Math.Max(46, heroCaption.ActualHeight);
        double availableHeight = Math.Max(80, body.ActualHeight - captionHeight - 8 - 84 - 190);
        double height = Math.Min(hero.ActualWidth / bannerAspect, availableHeight);
        double width = height * bannerAspect;
        if (Math.Abs(heroArtwork.Height - height) > 0.5) heroArtwork.Height = height;
        if (double.IsNaN(heroArtwork.Width) || Math.Abs(heroArtwork.Width - width) > 0.5) heroArtwork.Width = width;
        // Only soften the last 24 DIPs of the actual image, never its left side.
        bannerFadeStart.Offset = Math.Max(0, 1 - 24 / height);
    }
    private async Task LoadBanner(Image image, string key, long generation)
    {
        try
        {
            var file = await StorageFile.GetFileFromPathAsync(Path.Combine(AppContext.BaseDirectory, "Assets", "banners", key + ".jpg"));
            using var stream = await file.OpenReadAsync(); var source = new BitmapImage(); await source.SetSourceAsync(stream);
            if (generation == bannerGeneration)
            {
                image.Source = source;
                bannerAspect = source.PixelWidth / (double)source.PixelHeight;
                UpdateBannerLayout();
                Motion.Enter(hero);
            }
        }
        catch { }
    }
    private async Task RefreshMods()
    {
        if (engine is null || CurrentInstall is null) { mods = new(); frameworkData = null; return; }
        var response = await engine.Call("mods", Args()); mods = (JsonArray)response["mods"]!; frameworkData = response["framework"];
    }
    private void UpdateFramework()
    {
        if (frameworkData is null) return;
        string frameworkState = S(frameworkData, "state");
        var previousIcon = frameworkIcon;
        frameworkIcon = Fluent(frameworkState == "detected" ? "check" : "warning");
        if (VisualTreeHelper.GetParent(previousIcon) is Panel parent)
        {
            int index = parent.Children.IndexOf(previousIcon); parent.Children.RemoveAt(index); parent.Children.Insert(index, frameworkIcon);
        }
        frameworkIcon.Foreground = Brush(frameworkState == "detected" ? "primary" : "warning");
        framework.Text = frameworkState switch
        {
            "detected" => "REFramework • " + (B(frameworkData, "loose_files") ? "Loose: On" : "Loose: Off") + (B(frameworkData, "pak_directory") ? (B(frameworkData, "pak_enabled") ? " • PAK: On" : " • PAK: Off") : ""),
            "missing" => L("Chưa có REFramework", "REFramework missing"),
            _ => L("dinput8.dll chưa xác minh", "dinput8.dll not verified")
        };
    }
}
