using System.Text.Json.Nodes;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace REmmanager;

sealed partial class MainWindow
{
    private void BuildMods(Grid data)
    {
        data.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        data.RowDefinitions.Add(new RowDefinition());
        data.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        data.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        search = new TextBox { Header = L("Lọc mod theo tên", "Filter mods by name"), Text = filter, FontFamily = font, MinWidth = 160 };
        search.TextChanged += (_, _) => { filter = search.Text; FillMods(); };
        data.Children.Add(Split(search, Row(Action(L("Thêm thư mục", "Add folder"), () => ImportMod(true), icon: "folder"), Action(L("Thêm mod", "Add mod"), () => ImportMod(false), true, "add"))));
        modList = new ListView { SelectionMode = ListViewSelectionMode.Single, FontFamily = font };
        modList.SelectionChanged += (_, _) => { if (modList.SelectedItem is FrameworkElement row) selectedMod = row.Tag?.ToString() ?? ""; UpdateSelection(); };
        Grid.SetRow(modList, 1); data.Children.Add(modList);
        detail = Text(L("Chọn mod để bật/tắt. File gốc được sao lưu.", "Select a mod to enable/disable. Original files are backed up."), 11, false, "onSurfaceVariant");
        detail.MaxLines = 2; Grid.SetRow(detail, 2); data.Children.Add(detail);
        toggle = Action(L("Bật mod", "Enable mod"), ToggleMod, icon: "check");
        remove = Action(L("Xóa khỏi thư viện", "Remove from library"), RemoveMod, icon: "delete"); remove.Foreground = Brush("error");
        var actions = Split(Row(toggle, remove), Action(L("Mở thư mục", "Open folder"), () => { if (CurrentInstall is not null) OpenFolder(S(CurrentInstall, "path")); return Task.CompletedTask; }, icon: "folder"));
        Grid.SetRow(actions, 3); data.Children.Add(actions);
        FillMods();
    }
    private void FillMods()
    {
        if (destination != "mods") return;
        modList.Items.Clear();
        foreach (var item in mods.OfType<JsonObject>().Where(m => S(m, "name").Contains(filter, StringComparison.OrdinalIgnoreCase)))
        {
            var row = new Grid { Padding = new Thickness(4, 7, 4, 7), ColumnSpacing = 12, Tag = S(item, "id"), HorizontalAlignment = HorizontalAlignment.Stretch };
            row.ColumnDefinitions.Add(new ColumnDefinition());
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(75) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(92) });
            var title = new StackPanel { Spacing = 2 };
            title.Children.Add(Text(S(item, "name"), 13, true));
            title.Children.Add(Text(S(item, "kind") + " • " + (item["nexus"] is not null ? "Nexus" : L("Thủ công", "Manual")), 11, false, "onSurfaceVariant")); row.Children.Add(title);
            var version = Text(S(item, "version"), 12, false, "onSurfaceVariant"); Grid.SetColumn(version, 1); row.Children.Add(version);
            var enabledIcon = Fluent(B(item, "enabled") ? "check" : "circle"); enabledIcon.Foreground = Brush(B(item, "enabled") ? "primary" : "onSurfaceVariant");
            var enabled = Row(enabledIcon, Text(B(item, "enabled") ? L("Đang bật", "Enabled") : L("Đã tắt", "Disabled"), 12, false, B(item, "enabled") ? "primary" : "onSurfaceVariant"));
            enabled.Spacing = 4; Grid.SetColumn(enabled, 2); row.Children.Add(enabled); modList.Items.Add(row);
            if (S(item, "id") == selectedMod) modList.SelectedItem = row;
        }
        if (modList.Items.Count == 0) modList.Items.Add(new ListViewItem
        {
            Content = Text(CurrentInstall is null ? L("Thêm thư mục game để bắt đầu.", "Add a game folder to get started.") : L("Thêm PAK, ZIP, 7z, RAR, Lua, DLL hoặc thư mục mod.", "Add PAK, ZIP, 7z, RAR, Lua, DLL or a mod folder."), 13, false, "onSurfaceVariant"),
            IsEnabled = false
        });
        UpdateSelection();
    }
    private void UpdateSelection()
    {
        var mod = CurrentMod;
        toggle.IsEnabled = mod is not null; remove.IsEnabled = mod is not null && !B(mod, "enabled");
        ButtonLabel(toggle, B(mod, "enabled") ? L("Tắt mod", "Disable mod") : L("Bật mod", "Enable mod"), B(mod, "enabled") ? "dismiss" : "check");
        if (mod is not null)
        {
            int files = (mod["files"] as JsonObject)?.Count ?? 0;
            detail.Text = $"{files} files • {S(mod, "author", "—")} • {S(mod, "name")}";
            if ((mod["conflicts"] as JsonArray)?.Count > 0)
                detail.Text += " • " + L("Xung đột: ", "Conflicts: ") + string.Join(", ", mod["conflicts"]!.AsArray().Select(n => n!.ToString()));
            if (S(mod, "kind").Contains("PAK")) detail.Text += " • " + L("PAK Directory Loading; không kiểm tra asset bên trong PAK.", "PAK Directory Loading; internal asset conflicts are not checked.");
        }
    }
    private void BuildNexus(Grid data)
    {
        data.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto }); data.RowDefinitions.Add(new RowDefinition());
        data.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto }); data.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        nexusQuery = new TextBox { Header = L("Mod ID hoặc URL Nexus", "Mod ID or Nexus URL"), Text = query, FontFamily = font };
        nexusQuery.TextChanged += (_, _) => query = nexusQuery.Text;
        data.Children.Add(Split(nexusQuery, Row(Action(L("Tìm", "Find"), () => LoadNexus(true), icon: "search"), Action(L("Xu hướng", "Trending"), () => LoadNexus(false), true, "library"))));
        nexusList = new ListView { SelectionMode = ListViewSelectionMode.Single, FontFamily = font };
        Grid.SetRow(nexusList, 1); data.Children.Add(nexusList); FillNexus();
        var choose = Action(filesMode ? L("Tải file", "Download file") : L("Xem file", "View files"), NexusAction, icon: filesMode ? "download" : "folder");
        Grid.SetRow(choose, 2); data.Children.Add(choose);
        nxmInput = new TextBox { Header = "Download with Manager (nxm://)", Text = nxm, FontFamily = font };
        nxmInput.TextChanged += (_, _) => nxm = nxmInput.Text;
        var downloadRow = Split(nxmInput, Action(L("Tải link", "Download link"), () => DownloadNexus(nxm), true, "download"));
        Grid.SetRow(downloadRow, 3); data.Children.Add(downloadRow);
    }
    private void FillNexus()
    {
        nexusList.Items.Clear();
        foreach (var item in nexusItems.OfType<JsonObject>())
        {
            var row = new StackPanel { Spacing = 3, Padding = new Thickness(4, 7, 4, 7), Tag = item };
            row.Children.Add(Text(S(item, "name", S(item, "file_name")), 13, true));
            row.Children.Add(Text(S(item, filesMode ? "category_name" : "author") + " • " + S(item, "version"), 11, false, "onSurfaceVariant"));
            nexusList.Items.Add(row);
        }
        if (nexusItems.Count == 0) nexusList.Items.Add(new ListViewItem
        {
            Content = Text(L("Kết nối Nexus để khám phá mod. Free dùng link NXM; Premium tải trực tiếp.", "Connect Nexus to discover mods. Free uses NXM links; Premium downloads directly."), 13, false, "onSurfaceVariant"),
            IsEnabled = false
        });
    }
    private async Task LoadNexus(bool lookup)
    {
        if (state["account"] is null) { await Account(); if (state["account"] is null) return; }
        await Run(L("Đang lấy mod…", "Loading mods…"), async () =>
        {
            nexusItems = (JsonArray)await engine!.Call("nexus_mods", new JsonObject { ["game"] = game, ["query"] = lookup ? query : "" });
            filesMode = false; Render();
        });
    }
    private async Task NexusAction()
    {
        if (nexusList.SelectedItem is not FrameworkElement row || row.Tag is not JsonObject selected) return;
        if (!filesMode)
        {
            nexusMod = selected["mod_id"]!.GetValue<int>();
            await Run(L("Đang lấy file…", "Loading files…"), async () =>
            {
                var files = (JsonArray)await engine!.Call("nexus_files", new JsonObject { ["game"] = game, ["mod"] = nexusMod });
                nexusItems = new JsonArray(files.Where(f => S(f, "category_id") is not "6" and not "7").Select(f => f!.DeepClone()).ToArray());
                filesMode = true; Render();
            });
        }
        else if (!B(state["account"], "is_premium"))
        {
            OpenUrl($"https://www.nexusmods.com/{S(CurrentGame, "nexus")}/mods/{nexusMod}?tab=files&file_id={S(selected, "file_id")}");
            SetStatus(L("Chọn Download with Manager hoặc tải thủ công rồi thêm file.", "Use Download with Manager, or download manually and add the file."));
        }
        else await DownloadNexus("", selected["file_id"]!.GetValue<int>());
    }
    private async Task DownloadNexus(string link, int file = 0)
    {
        if (!string.IsNullOrWhiteSpace(link) && Uri.TryCreate(link, UriKind.Absolute, out var uri))
        {
            var matching = (state["games"] as JsonArray)?.OfType<JsonObject>().FirstOrDefault(g => S(g, "nexus") == uri.Host);
            var install = (state["installations"] as JsonArray)?.OfType<JsonObject>().FirstOrDefault(i => S(i, "game") == S(matching, "key"));
            if (install is not null) { game = S(install, "game"); installation = S(install, "id"); }
        }
        if (!RequireGame()) return;
        if (state["account"] is null) { await Account(); if (state["account"] is null) return; }
        await Run(L("Đang tải mod…", "Downloading mod…"), async () =>
        {
            await engine!.Call("download", Args(new JsonObject { ["nxm"] = link, ["mod"] = nexusMod, ["file"] = file }));
            destination = "mods"; await RefreshMods(); Render();
        }, true);
    }
}
