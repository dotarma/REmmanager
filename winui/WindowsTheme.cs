using System.Text.Json.Nodes;
using Windows.UI.ViewManagement;

namespace REmmanager;

sealed partial class MainWindow
{
    private readonly UISettings windowsColors = new();
    private bool accentDirty = true;
    private string WindowsAccent()
    {
        var color = windowsColors.GetColorValue(UIColorType.Accent);
        return $"#{color.R:X2}{color.G:X2}{color.B:X2}";
    }
    private void WindowsColorsChanged(UISettings sender, object args) => DispatcherQueue.TryEnqueue(() => accentDirty = true);
    private async Task SyncWindowsAccent()
    {
        if (engine is null) return;
        SetState(await engine.Call("preferences", Preferences(new JsonObject { ["seed"] = WindowsAccent(), ["preset"] = "windows" })));
        accentDirty = !string.Equals(S(state["preferences"], "seed"), WindowsAccent(), StringComparison.OrdinalIgnoreCase);
    }
}
