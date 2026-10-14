using System.Text.Json.Nodes;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace REmmanager;

sealed partial class MainWindow
{
    private ListView accountList = new();
    private void NexusContextChanged() { nexusItems = new(); filesMode = false; nexusMod = 0; }
    private string SelectedAccount => (accountList.SelectedItem as FrameworkElement)?.Tag?.ToString() ?? "";
    private ContentDialog BuildAccountsDialog()
    {
        var content = new StackPanel { Spacing = 12, Width = 440 };
        string active = S(state, "active_account");
        content.Children.Add(Text(state["account"] is null ? L("Chưa kết nối", "Not connected") : L("Đang dùng: ", "Using: ") + S(state["account"], "name"), 17, true));
        if (!string.IsNullOrEmpty(S(state, "accounts_error"))) content.Children.Add(Text(S(state, "accounts_error"), 12, false, "warning"));
        accountList = new ListView { SelectionMode = ListViewSelectionMode.Single, MaxHeight = 240, FontFamily = font };
        var dialog = new ContentDialog { XamlRoot = root.XamlRoot, Title = L("Tài khoản Nexus Mods", "Nexus Mods accounts"), Content = content,
            PrimaryButtonText = L("Thêm tài khoản", "Add account"), SecondaryButtonText = L("Dùng tài khoản", "Use account"),
            CloseButtonText = L("Đóng", "Close"), IsSecondaryButtonEnabled = false, RequestedTheme = root.RequestedTheme };
        var remove = Action(L("Xóa đăng nhập", "Remove login"), () => { dialog.Tag = "remove"; dialog.Hide(); return Task.CompletedTask; }, icon: "delete");
        remove.Foreground = Brush("error"); remove.IsEnabled = false;
        var disconnect = Action(L("Ngắt kết nối", "Disconnect"), () => { dialog.Tag = "disconnect"; dialog.Hide(); return Task.CompletedTask; }, icon: "dismiss");
        disconnect.IsEnabled = state["account"] is not null;
        accountList.SelectionChanged += (_, _) =>
        {
            remove.IsEnabled = !string.IsNullOrEmpty(SelectedAccount);
            dialog.IsSecondaryButtonEnabled = remove.IsEnabled && (state["account"] is null || SelectedAccount != active);
        };
        foreach (var account in (state["accounts"] as JsonArray ?? new()).OfType<JsonObject>())
        {
            string identity = S(account, "id");
            bool current = identity == active && state["account"] is not null;
            var labels = new StackPanel { Spacing = 3 };
            var name = Text(S(account, "name", ""), 14, true);
            if (string.IsNullOrEmpty(name.Text)) name.Text = L("Tài khoản từ bản cũ", "Previous account");
            name.MaxWidth = 340; name.TextTrimming = TextTrimming.CharacterEllipsis; name.MaxLines = 1;
            labels.Children.Add(name);
            string tier = identity == "legacy" ? L("Chờ xác thực", "Pending validation") : B(account, "is_premium") ? "Premium" : "Free";
            string storage = B(account, "remembered") ? L("Đã lưu • DPAPI", "Saved • DPAPI") : L("Chỉ phiên này", "This session only");
            labels.Children.Add(Text(tier + " • " + storage + (current ? L(" • Đang dùng", " • Current") : ""), 11, false, "onSurfaceVariant"));
            var icon = Fluent(current ? "check" : "person"); icon.Foreground = Brush(current ? "primary" : "onSurfaceVariant");
            var row = Row(icon, labels); row.Tag = identity; row.Padding = new Thickness(4, 8, 4, 8);
            accountList.Items.Add(row);
            if (identity == active) accountList.SelectedItem = row;
        }
        if (accountList.Items.Count == 0) content.Children.Add(Text(L("Chưa có tài khoản. Thêm API key để bắt đầu.", "No accounts yet. Add an API key to get started."), 13, false, "onSurfaceVariant"));
        else if (accountList.SelectedItem is null) accountList.SelectedIndex = 0;
        content.Children.Add(accountList);
        content.Children.Add(Row(remove, disconnect));
        content.Children.Add(Text(L("Ngắt kết nối giữ tài khoản đã lưu. Xóa đăng nhập chỉ quên key trên máy này, không xóa tài khoản Nexus.", "Disconnect keeps saved accounts. Remove login only forgets the local key; it does not delete your Nexus account."), 12, false, "onSurfaceVariant"));
        return dialog;
    }
    private async Task Account()
    {
        if (busy || engine is null) return;
        while (true)
        {
            var dialog = BuildAccountsDialog();
            dialogOpen = true; ContentDialogResult result;
            try { result = await dialog.ShowAsync(); } finally { dialogOpen = false; }
            string identity = SelectedAccount;
            string command = dialog.Tag?.ToString() ?? "";
            if (command == "remove")
            {
                if (await Dialog(L("Xóa đăng nhập đã chọn?", "Remove selected login?"), Text(L("Chỉ xóa API key đã lưu của tài khoản này. Các tài khoản khác được giữ nguyên.", "Remove only this account's saved API key. Other accounts are kept.")), L("Xóa", "Remove")) == ContentDialogResult.Primary)
                    await Run(L("Đang xóa đăng nhập…", "Removing login…"), async () => { SetState(await engine.Call("remove_account", new JsonObject { ["account"] = identity })); NexusContextChanged(); Render(); });
                continue;
            }
            if (command == "disconnect")
                await Run(L("Đang ngắt kết nối…", "Disconnecting…"), async () => { SetState(await engine.Call("logout")); NexusContextChanged(); Render(); });
            else if (result == ContentDialogResult.Primary) await LoginAccount();
            else if (result == ContentDialogResult.Secondary)
                await Run(L("Đang chuyển tài khoản…", "Switching accounts…"), async () => { SetState(await engine.Call("switch_account", new JsonObject { ["account"] = identity })); NexusContextChanged(); Render(); });
            return;
        }
    }
}
