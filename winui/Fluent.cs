using System.Xml.Linq;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Automation.Peers;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Markup;

namespace REmmanager;

sealed partial class MainWindow
{
    private static readonly Dictionary<string, string> iconPaths = new();
    private static PathIcon Fluent(string name)
    {
        if (!iconPaths.TryGetValue(name, out string? path))
        {
            var document = XDocument.Load(Path.Combine(AppContext.BaseDirectory, "Assets", "icons", name + ".svg"));
            path = "F1 " + string.Join(" ", document.Descendants().Where(e => e.Name.LocalName == "path").Select(e => e.Attribute("d")!.Value));
            iconPaths[name] = path;
        }
        var icon = (PathIcon)XamlReader.Load("<PathIcon xmlns=\"http://schemas.microsoft.com/winfx/2006/xaml/presentation\" Data=\"" + path + "\" />");
        // These paths use Microsoft's 20x20 SVG viewBox. PathIcon does not
        // scale that coordinate space when Width/Height are set to 16;
        // the right/bottom contours get clipped instead.
        icon.Width = 20; icon.Height = 20;
        icon.HorizontalAlignment = HorizontalAlignment.Center;
        icon.VerticalAlignment = VerticalAlignment.Center;
        icon.UseLayoutRounding = true;
        icon.IsHitTestVisible = false;
        AutomationProperties.SetAccessibilityView(icon, AccessibilityView.Raw);
        return icon;
    }
    private void ButtonLabel(Button button, string label, string? icon)
    {
        var text = new TextBlock { Text = label, FontFamily = font, VerticalAlignment = VerticalAlignment.Center };
        button.Content = icon is null ? text : Row(Fluent(icon), text);
        AutomationProperties.SetName(button, label);
    }
}
