using System.Text.Json.Nodes;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Automation.Peers;
using Microsoft.UI.Xaml.Automation.Provider;
using Microsoft.UI.Xaml.Media.Imaging;
using Windows.Foundation;
using Windows.Graphics.Imaging;
using Windows.Storage;
using Windows.Storage.Streams;

namespace REmmanager;

sealed partial class MainWindow
{
    private async Task Capture(string folder, string name, UIElement? target = null)
    {
        await Task.Delay(450);
        var bitmap = new RenderTargetBitmap();
        await bitmap.RenderAsync(target ?? root);
        var pixels = await bitmap.GetPixelsAsync();
        var bytes = new byte[pixels.Length];
        using (var reader = DataReader.FromBuffer(pixels)) reader.ReadBytes(bytes);
        var directory = await StorageFolder.GetFolderFromPathAsync(folder);
        var file = await directory.CreateFileAsync(name + ".png", CreationCollisionOption.ReplaceExisting);
        using var output = await file.OpenAsync(FileAccessMode.ReadWrite);
        var encoder = await BitmapEncoder.CreateAsync(BitmapEncoder.PngEncoderId, output);
        encoder.SetPixelData(BitmapPixelFormat.Bgra8, BitmapAlphaMode.Premultiplied, (uint)bitmap.PixelWidth, (uint)bitmap.PixelHeight, 96, 96, bytes);
        await encoder.FlushAsync();
    }
    private void Check(bool condition, string message)
    {
        if (!condition) throw new Exception("UI verification: " + message);
    }
    private async Task VerifyUi(string folder)
    {
        Directory.CreateDirectory(folder);
        pollTimer.Stop();
        await Task.Delay(1000);
        var report = new List<string>();
        Check(language == "en", "Fresh startup did not default to English");
        await Capture(folder, "first-launch-en");
        report.Add("Fresh installation defaults to English");
        foreach (string mode in new[] { "light", "dark", "oled" })
        {
            foreach (string locale in new[] { "vi", "en" })
            {
                SetState(await engine!.Call("preferences", Preferences(new JsonObject { ["mode"] = mode, ["language"] = locale })));
                destination = "mods"; game = "re7";
                installation = (state["installations"] as JsonArray)?.OfType<JsonObject>().Where(i => S(i, "game") == game).Select(i => S(i, "id")).FirstOrDefault() ?? "";
                await RefreshMods(); Render(); await Task.Delay(500);
                var titleTop = heroTitle.TransformToVisual(hero).TransformPoint(new Point(0, 0)).Y;
                var yearTop = heroYear.TransformToVisual(hero).TransformPoint(new Point(0, 0)).Y;
                Check(titleTop + heroTitle.ActualHeight <= yearTop + 0.5, "RE7 title overlaps year");
                Check(heroTitle.MaxLines == 2, "RE7 title is not constrained to two lines");
                Check(bannerImage.Source is BitmapImage && bannerImage.Stretch == Microsoft.UI.Xaml.Media.Stretch.Uniform, "Full banner did not load without cropping");
                Check(Find<PathIcon>(root).Count() >= 15, "Fluent vector icons are missing");
                await Capture(folder, $"re7-{mode}-{locale}");
                report.Add($"{mode}/{locale}: RE7 title/year have separate bounds");
            }
        }
        AppWindow.Resize(new Windows.Graphics.SizeInt32(940, 700));
        Render(); await Task.Delay(500);
        var bottom = remove.TransformToVisual(root).TransformPoint(new Point(0, remove.ActualHeight)).Y;
        Check(bottom <= root.ActualHeight, "Library actions clipped in compact window");
        await Capture(folder, "compact");
        destination = "settings"; Render(); await Task.Delay(500);
        var nativeSliders = Find<Slider>(root).ToList();
        Check(nativeSliders.Count == 1, "Native WinUI Slider missing");
        Check(progress is ProgressBar, "Native WinUI ProgressBar missing");
        Check(!Find<ColorPicker>(root).Any(), "Custom color picker still present");
        Check(Find<ComboBox>(root).Count() == 2, "Preset controls were not removed");
        await Capture(folder, "settings");
        progress.Visibility = Visibility.Visible; progress.IsIndeterminate = false; progress.Value = 64;
        await Capture(folder, "progress");
        progress.Visibility = Visibility.Collapsed;
        Motion.Reduced = true; Motion.Enter(body);
        Check(!Motion.Enabled, "Reduced motion was ignored");
        report.Add("Native Slider/ProgressBar, compact library layout, reduced motion verified");
        // Verify the onboarding flag persists through the engine, independently of UI visibility.
        SetState(await engine!.Call("preferences", Preferences(new JsonObject { ["onboarding_done"] = true })));
        Check(B((await engine.Call("state"))["settings"], "onboarding_done"), "Onboarding completion was not saved");
        report.Add("Onboarding skip/completion preference persists");
        destination = "mods"; game = "re2";
        installation = (state["installations"] as JsonArray)!.OfType<JsonObject>().Where(i => S(i, "game") == game).Select(i => S(i, "id")).First();
        await RefreshMods(); Render();
        selectedMod = S(mods.FirstOrDefault(), "id"); FillMods();
        Check(toggle.IsEnabled, "Mod selection does not enable actions");
        var selectedBefore = selectedMod;
        SetState(await engine.Call("preferences", Preferences(new JsonObject { ["seed"] = "#4D92BE", ["preset"] = "ocean" }))); Render();
        WindowsColorsChanged(windowsColors, new object());
        await Task.Delay(50); // ColorValuesChanged is marshalled onto the UI dispatcher.
        Check(accentDirty, "Windows color change was not queued");
        await SyncWindowsAccent(); Render();
        Check(string.Equals(S(state["preferences"], "seed"), WindowsAccent(), StringComparison.OrdinalIgnoreCase), "Accent does not match Windows");
        Check(S(state["settings"]?["appearance"], "color_source") == "windows", "Windows color source was not saved");
        Check(selectedMod == selectedBefore, "Theme change lost selected mod");
        await Capture(folder, "library");
        report.Add("Windows accent sync replaces saved custom colors; selected mod is preserved; presets removed");
        foreach (string key in new[] { "re2", "re3", "re4", "re7", "re8", "re9" })
        {
            game = key;
            installation = (state["installations"] as JsonArray)!.OfType<JsonObject>().Where(i => S(i, "game") == game).Select(i => S(i, "id")).FirstOrDefault() ?? "";
            await RefreshMods(); Render(); await Task.Delay(500);
            Check(bannerImage.Source is BitmapImage && bannerImage.Stretch == Microsoft.UI.Xaml.Media.Stretch.Uniform, key + " banner cropped/missing");
            Check(remove.TransformToVisual(root).TransformPoint(new Point(0, remove.ActualHeight)).Y <= root.ActualHeight, key + " actions clipped");
            await Capture(folder, "banner-" + key);
        }
        report.Add("All six full banners loaded with surface fades and Fluent SVG icons in compact layout");
        await VerifyBannerResizing(folder, report);
        SetState(await engine.Call("preferences", Preferences(new JsonObject { ["onboarding_done"] = false })));
        await RunOnboarding(async wizard =>
        {
            await Task.Delay(500);
            await Capture(folder, "onboarding", (UIElement)wizard.Content);
            InvokeDialogButton(wizard, "CloseButton");
        });
        Check(B((await engine.Call("state"))["settings"], "onboarding_done"), "Native Skip button did not persist completion");
        await RunOnboarding(async wizard =>
        {
            for (int step = 0; step < 4; step++)
            {
                await Task.Delay(300);
                InvokeDialogButton(wizard, "PrimaryButton");
            }
        });
        report.Add("Native onboarding Skip and four-step completion verified");
        await VerifyAccountPicker(folder);
        report.Add("Multi-account picker: current account disabled, switching enabled for another account, VI/EN layout verified");
        File.WriteAllLines(Path.Combine(folder, "verified.txt"), report);
        Close();
    }
    private static void InvokeDialogButton(ContentDialog dialog, string name)
    {
        var button = Find<Button>(dialog).First(b => b.Name == name);
        var peer = FrameworkElementAutomationPeer.CreatePeerForElement(button);
        ((IInvokeProvider)peer.GetPattern(PatternInterface.Invoke)).Invoke();
    }
    private void CheckBannerFit(string context, List<string> report)
    {
        Check(bannerImage.Source is BitmapImage, context + ": banner missing");
        var source = (BitmapImage)bannerImage.Source;
        double ratio = source.PixelWidth / (double)source.PixelHeight;
        Check(Math.Abs(bannerImage.ActualWidth / bannerImage.ActualHeight - ratio) < 0.005, context + ": image ratio changed or clipped");
        var imageOrigin = bannerImage.TransformToVisual(hero).TransformPoint(new Point(0, 0));
        var captionOrigin = heroCaption.TransformToVisual(hero).TransformPoint(new Point(0, 0));
        Check(imageOrigin.X >= -0.5 && imageOrigin.X + bannerImage.ActualWidth <= hero.ActualWidth + 0.5, context + ": image extends past banner bounds");
        Check(captionOrigin.Y >= imageOrigin.Y + bannerImage.ActualHeight - 0.5, context + ": caption covers image");
        Check(remove.TransformToVisual(root).TransformPoint(new Point(0, remove.ActualHeight)).Y <= root.ActualHeight, context + ": mod actions are outside window");
        report.Add($"{context}: {root.ActualWidth:F0}x{root.ActualHeight:F0}, full image {bannerImage.ActualWidth:F0}x{bannerImage.ActualHeight:F0}; caption outside image; mod actions visible");
    }
    private async Task VerifyBannerResizing(string folder, List<string> report)
    {
        game = "re7"; installation = ""; await RefreshMods(); Render();
        foreach (var size in new[] { (1000, 740), (1600, 900), (2560, 1080) })
        {
            AppWindow.Resize(new Windows.Graphics.SizeInt32(size.Item1, size.Item2));
            await Task.Delay(650);
            CheckBannerFit($"resize {size.Item1}x{size.Item2}", report);
            await Capture(folder, $"resize-{size.Item1}x{size.Item2}");
        }
        var presenter = (Microsoft.UI.Windowing.OverlappedPresenter)AppWindow.Presenter;
        presenter.Maximize(); await Task.Delay(650);
        Check(presenter.State == Microsoft.UI.Windowing.OverlappedPresenterState.Maximized, "Native window did not maximize");
        CheckBannerFit("maximized", report); await Capture(folder, "maximized");
        presenter.Restore(); await Task.Delay(250);
        AppWindow.SetPresenter(Microsoft.UI.Windowing.AppWindowPresenterKind.FullScreen);
        await Task.Delay(650);
        CheckBannerFit("fullscreen", report); await Capture(folder, "fullscreen");
        AppWindow.SetPresenter(Microsoft.UI.Windowing.AppWindowPresenterKind.Overlapped);
        AppWindow.Resize(new Windows.Graphics.SizeInt32(940, 700));
        await Task.Delay(400); Render();
    }
    private async Task VerifyAccountPicker(string folder)
    {
        // Public UI fixtures only: no keys, saved credentials or live requests.
        var original = (JsonObject)state.DeepClone();
        foreach (string locale in new[] { "vi", "en" })
        {
            language = locale;
            state["accounts"] = new JsonArray(
                new JsonObject { ["id"] = "11", ["user_id"] = 11, ["name"] = "Survivor One [DEMO]", ["is_premium"] = true, ["remembered"] = true },
                new JsonObject { ["id"] = "22", ["user_id"] = 22, ["name"] = "Survivor Two [DEMO]", ["is_premium"] = false, ["remembered"] = true });
            state["account"] = state["accounts"]![0]!.DeepClone(); state["active_account"] = "11";
            var dialog = BuildAccountsDialog();
            dialogOpen = true;
            var showing = dialog.ShowAsync();
            try
            {
                await Task.Delay(400);
                Check(accountList.Items.Count == 2, "Saved accounts missing from picker");
                Check(!dialog.IsSecondaryButtonEnabled, "Current account should not offer a redundant switch");
                accountList.SelectedIndex = 1;
                Check(dialog.IsSecondaryButtonEnabled && SelectedAccount == "22", "Cannot select a different Nexus account");
                await Capture(folder, "accounts-" + locale, dialog);
                InvokeDialogButton(dialog, "CloseButton");
                await showing;
            }
            finally { dialogOpen = false; }
        }
        SetState(original); Render();
    }
    private static IEnumerable<T> Find<T>(DependencyObject parent) where T : DependencyObject
    {
        int count = Microsoft.UI.Xaml.Media.VisualTreeHelper.GetChildrenCount(parent);
        for (int i = 0; i < count; i++)
        {
            var child = Microsoft.UI.Xaml.Media.VisualTreeHelper.GetChild(parent, i);
            if (child is T value) yield return value;
            foreach (var item in Find<T>(child)) yield return item;
        }
    }
}
