using System.Diagnostics;
using System.Text.Json.Nodes;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Windows.Storage.Pickers;
using WinRT.Interop;

namespace REmmanager;

sealed partial class MainWindow
{
    private JsonObject Args(JsonObject? extra = null)
    {
        var result = extra ?? new JsonObject(); result["installation"] = installation; result["game"] = game; return result;
    }
    private async Task Navigate(string value)
    {
        if (busy) return;
        destination = value; Render(); Motion.Enter(body); await Task.CompletedTask;
    }
    private async Task Run(string message, Func<Task> action, bool canCancel = false)
    {
        if (busy || engine is null) return;
        busy = true; cancellable = canCancel; SetStatus(message);
        workspace.Children[0].IsHitTestVisible = false; body.IsHitTestVisible = false;
        progress.Visibility = Visibility.Visible; progress.IsIndeterminate = true;
        cancel.Visibility = canCancel ? Visibility.Visible : Visibility.Collapsed; cancel.IsEnabled = canCancel;
        try { await action(); SetStatus(L("Đã hoàn tất.", "Completed.")); }
        catch (Exception e) { await Error(e.Message); }
        finally
        {
            busy = false; cancellable = false; workspace.Children[0].IsHitTestVisible = true; body.IsHitTestVisible = true;
            cancel.Visibility = Visibility.Collapsed; progress.IsIndeterminate = false; progress.Visibility = Visibility.Collapsed;
        }
    }
    private async Task<ContentDialogResult> Dialog(string title, UIElement content, string? primary = null)
    {
        dialogOpen = true;
        try
        {
            return await new ContentDialog { XamlRoot = root.XamlRoot, Title = title, Content = content, PrimaryButtonText = primary ?? "",
                CloseButtonText = L("Đóng", "Close"), DefaultButton = ContentDialogButton.Primary, RequestedTheme = root.RequestedTheme }.ShowAsync();
        }
        finally { dialogOpen = false; }
    }
    private async Task Error(string message)
    {
        SetStatus(message); if (!dialogOpen) await Dialog("REmmanager", Text(message));
    }
    private bool RequireGame()
    {
        if (CurrentInstall is not null && B(CurrentInstall, "available")) return true;
        SetStatus(L("Thêm/chọn thư mục game trước.", "Add or select a game folder first.")); return false;
    }
    private static void OpenUrl(string url) => Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
    private static void OpenFolder(string path)
    {
        var start = new ProcessStartInfo("explorer.exe") { UseShellExecute = false }; start.ArgumentList.Add(path); Process.Start(start);
    }
    private async Task<string?> PickFolder()
    {
        var picker = new FolderPicker(); picker.FileTypeFilter.Add("*");
        InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
        return (await picker.PickSingleFolderAsync())?.Path;
    }
    private async Task AddGame()
    {
        string? path = await PickFolder(); if (path is null) return;
        await Run(L("Đang nhận diện game…", "Identifying game…"), async () =>
        {
            var result = await engine!.Call("add_game", new JsonObject { ["path"] = path }); SetState(result["state"]!);
            installation = S(result, "installation"); game = S(CurrentInstall, "game", game); await RefreshMods(); Render();
        });
    }
    private async Task ImportMod(bool folder)
    {
        if (!RequireGame()) return;
        string? path;
        if (folder) path = await PickFolder();
        else
        {
            var picker = new FileOpenPicker();
            foreach (var extension in new[] { ".zip", ".7z", ".rar", ".lua", ".dll", ".pak" }) picker.FileTypeFilter.Add(extension);
            InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this)); path = (await picker.PickSingleFileAsync())?.Path;
        }
        if (path is null) return;
        await Run(L("Đang nhập mod…", "Importing mod…"), async () =>
        {
            var result = await engine!.Call("import", Args(new JsonObject { ["path"] = path })); selectedMod = S(result, "id"); await RefreshMods(); Render();
        });
    }
    private async Task ToggleMod()
    {
        var mod = CurrentMod; if (mod is null) return;
        await Run(L("Đang cập nhật mod…", "Updating mod…"), async () =>
        {
            await engine!.Call(B(mod, "enabled") ? "disable" : "enable", Args(new JsonObject { ["mod"] = selectedMod })); await RefreshMods(); FillMods();
        });
    }
    private async Task RemoveMod()
    {
        if (CurrentMod is null) return;
        if (await Dialog(L("Xóa mod?", "Remove mod?"), Text(L("Xóa payload khỏi thư viện; giữ lại bản sao lưu file gốc.", "Remove the payload from the library; keep original-file backups.")), L("Xóa", "Remove")) != ContentDialogResult.Primary) return;
        await Run(L("Đang xóa…", "Removing…"), async () =>
        {
            await engine!.Call("remove", new JsonObject { ["mod"] = selectedMod }); selectedMod = ""; await RefreshMods(); FillMods();
        });
    }
    private async Task LaunchGame(bool steam)
    {
        if (!RequireGame()) return;
        await Run(L("Đang chạy game…", "Launching game…"), async () => { await engine!.Call("launch", Args(new JsonObject { ["steam"] = steam })); await Task.Delay(800); await UpdateProcess(); });
    }
    private async Task UpdateProcess()
    {
        if (engine is null || CurrentInstall is null) return;
        var result = await engine.Call("process_status", Args()); running = B(result, "running");
        launch.IsEnabled = !running && B(CurrentInstall, "available"); stop.Visibility = running ? Visibility.Visible : Visibility.Collapsed;
    }
    private async Task StopGame()
    {
        if (!running || !RequireGame()) return;
        if (await Dialog(L("Dừng game?", "Stop the game?"), Text(L("Lưu tiến trình chơi trước. REmmanager chỉ đóng game ở đúng thư mục đang chọn.", "Save your progress first. Only the game from the selected installation will be closed.")), L("Dừng game", "Stop game")) != ContentDialogResult.Primary) return;
        await Run(L("Đang đóng game…", "Closing game…"), async () =>
        {
            var response = await engine!.Call("stop", Args());
            if (B(response, "needs_force") && await Dialog(L("Game chưa đóng", "Game is still running"), Text(L("Game chưa phản hồi. Buộc dừng sẽ mất tiến trình chưa lưu.", "The game did not respond. Force stop loses unsaved progress.")), L("Buộc dừng", "Force stop")) == ContentDialogResult.Primary)
                await engine.Call("stop", Args(new JsonObject { ["force"] = true }));
            await UpdateProcess();
        });
    }
    private async Task Poll()
    {
        if (polling || engine is null || dialogOpen) return;
        polling = true;
        try
        {
            if (!busy && accentDirty) await Run(L("Đang đồng bộ màu Windows…", "Syncing Windows color…"), async () => { await SyncWindowsAccent(); Render(); });
            if (!busy) await UpdateProcess();
            if (!busy && !demo)
                foreach (var link in (await engine.Call("inbox")).AsArray()) { nxm = link!.ToString(); await DownloadNexus(nxm); }
        }
        catch { }
        finally { polling = false; }
    }
    private async Task RegisterNxm()
    {
        if (await Dialog("nxm://", Text(L("Đặt REmmanager làm handler Download with Manager? Điều này thay handler Nexus hiện tại của tài khoản Windows.", "Set REmmanager as the Download with Manager handler? This replaces the current Nexus handler for this Windows account.")), L("Đăng ký", "Register")) != ContentDialogResult.Primary) return;
        using var key = Microsoft.Win32.Registry.CurrentUser.CreateSubKey(@"Software\Classes\nxm");
        key.SetValue("", "URL:Nexus Mod Protocol"); key.SetValue("URL Protocol", "");
        using var command = key.CreateSubKey(@"shell\open\command");
        command.SetValue("", $"\"{Environment.ProcessPath}\" --data-dir \"{dataDir}\" --nxm \"%1\"");
        SetStatus(L("Đã đăng ký nxm://.", "Registered nxm://."));
    }
}
