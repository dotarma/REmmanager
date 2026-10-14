using Microsoft.UI.Dispatching;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using System.Security.Cryptography;
using System.Text;
using System.Runtime.InteropServices;

namespace REmmanager;

static class Program
{
    public static string[] Arguments = [];
    private static Mutex? instanceMutex;
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBoxW(IntPtr hwnd, string message, string title, uint type);
    [STAThread]
    public static void Main(string[] args)
    {
        Arguments = args;
        string? Arg(string key) { int index = Array.IndexOf(args, key); return index >= 0 && index + 1 < args.Length ? args[index + 1] : null; }
        string directory = Arg("--data-dir") ?? Backend.DefaultDataDir;
        if (Arg("--nxm") is { } link)
        {
            try { Backend.QueueNxm(directory, link); }
            catch (Exception error) { MessageBoxW(IntPtr.Zero, error.Message, "REmmanager", 0x10); return; }
        }
        if (!args.Contains("--demo"))
        {
            string key = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(Environment.UserName + Path.GetFullPath(directory))))[..24];
            instanceMutex = new Mutex(true, @"Local\REmmanager-" + key, out bool created);
            if (!created) return;
        }
        WinRT.ComWrappersSupport.InitializeComWrappers();
        Application.Start(initialization =>
        {
            SynchronizationContext.SetSynchronizationContext(new DispatcherQueueSynchronizationContext(DispatcherQueue.GetForCurrentThread()));
            var application = new REmApp();
        });
    }
}

sealed class REmApp : Application, Microsoft.UI.Xaml.Markup.IXamlMetadataProvider
{
    private MainWindow? window;
    private readonly Microsoft.UI.Xaml.XamlTypeInfo.XamlControlsXamlMetaDataProvider metadata = new();
    public Microsoft.UI.Xaml.Markup.IXamlType GetXamlType(Type type) => metadata.GetXamlType(type);
    public Microsoft.UI.Xaml.Markup.IXamlType GetXamlType(string name) => metadata.GetXamlType(name);
    public Microsoft.UI.Xaml.Markup.XmlnsDefinition[] GetXmlnsDefinitions() => metadata.GetXmlnsDefinitions();
    public REmApp()
    {
        UnhandledException += (_, e) =>
        {
            string folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "REmmanager");
            Directory.CreateDirectory(folder);
            File.AppendAllText(Path.Combine(folder, "startup.log"), DateTime.UtcNow + " " + e.Exception + Environment.NewLine);
        };
    }
    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        Resources.MergedDictionaries.Add(new XamlControlsResources());
        window = new MainWindow();
        window.Activate();
    }
}
