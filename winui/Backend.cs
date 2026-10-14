using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;

namespace REmmanager;

sealed class Backend : IDisposable
{
    private readonly Process process;
    private readonly ConcurrentDictionary<int, TaskCompletionSource<JsonNode>> pending = new();
    private readonly SemaphoreSlim writer = new(1);
    private int sequence;
    public event Action<JsonObject>? Event;
    public string DataDir { get; }
    public static string DefaultDataDir => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        Directory.Exists(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "REEngineModManager")) ? "REEngineModManager" : "REmmanager");

    public Backend(string dataDir, bool demo)
    {
        DataDir = dataDir;
        string root = ExtractRuntime();
        var start = new ProcessStartInfo(Path.Combine(root, "python.exe"))
        {
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardInputEncoding = new UTF8Encoding(false), StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8,
            WorkingDirectory = root
        };
        start.ArgumentList.Add("-m"); start.ArgumentList.Add("re_manager.service");
        start.ArgumentList.Add("--data-dir"); start.ArgumentList.Add(dataDir);
        if (demo) start.ArgumentList.Add("--demo");
        process = Process.Start(start) ?? throw new Exception("Could not start the Python engine.");
        _ = Task.Run(ReadOutput);
        _ = Task.Run(async () =>
        {
            string error = await process.StandardError.ReadToEndAsync();
            if (!string.IsNullOrWhiteSpace(error))
                foreach (var item in pending.Values) item.TrySetException(new Exception(error));
        });
    }

    public static string ExtractRuntime()
    {
        string zip = Path.Combine(AppContext.BaseDirectory, "Backend.zip");
        string hash = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(zip)))[..16];
        string root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "REmmanager", "runtime", hash);
        if (!File.Exists(Path.Combine(root, ".ready")))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(root)!);
            string temporary = root + "." + Guid.NewGuid().ToString("N");
            Directory.CreateDirectory(temporary);
            ZipFile.ExtractToDirectory(zip, temporary);
            File.WriteAllText(Path.Combine(temporary, ".ready"), hash);
            try { Directory.Move(temporary, root); }
            catch (IOException) when (Directory.Exists(root)) { Directory.Delete(temporary, true); }
        }
        return root;
    }
    public static void QueueNxm(string dataDir, string link)
    {
        string runtime = ExtractRuntime();
        var start = new ProcessStartInfo(Path.Combine(runtime, "python.exe"))
        {
            UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = runtime,
            RedirectStandardOutput = true, RedirectStandardError = true
        };
        foreach (string value in new[] { "-m", "re_manager.service", "--data-dir", dataDir, "--enqueue-nxm", link, "--enqueue-only" })
            start.ArgumentList.Add(value);
        using var queue = Process.Start(start) ?? throw new Exception("Could not queue the Nexus link.");
        if (!queue.WaitForExit(15000))
        {
            queue.Kill();
            throw new Exception("Nexus link processing timed out. Please try again.");
        }
        if (queue.ExitCode != 0) throw new Exception("The Nexus link is invalid or expired. Create a new Download with Manager link.");
    }

    public async Task<JsonNode> Call(string method, JsonObject? args = null)
    {
        int id = Interlocked.Increment(ref sequence);
        var completion = new TaskCompletionSource<JsonNode>(TaskCreationOptions.RunContinuationsAsynchronously);
        pending[id] = completion;
        var request = new JsonObject { ["id"] = id, ["method"] = method, ["args"] = args ?? new JsonObject() };
        try
        {
            await writer.WaitAsync();
            try { await process.StandardInput.WriteLineAsync(request.ToJsonString()); await process.StandardInput.FlushAsync(); }
            finally { writer.Release(); }
            return await completion.Task.WaitAsync(TimeSpan.FromMinutes(30));
        }
        finally { pending.TryRemove(id, out _); }
    }

    private async Task ReadOutput()
    {
        try
        {
            while (await process.StandardOutput.ReadLineAsync() is { } line)
            {
                if (JsonNode.Parse(line) is not JsonObject data) continue;
                if (data["id"] is not null && pending.TryGetValue((int)data["id"]!, out var completion))
                {
                    if (data["error"] is { } error) completion.TrySetException(new Exception(error.ToString()));
                    else completion.TrySetResult(data["result"] ?? new JsonObject());
                }
                else Event?.Invoke(data);
            }
        }
        catch (Exception exception) { foreach (var completion in pending.Values) completion.TrySetException(exception); }
        finally { foreach (var completion in pending.Values) completion.TrySetException(new Exception("The Python engine closed.")); }
    }

    public void Dispose()
    {
        try { process.StandardInput.Close(); }
        catch { }
        _ = Task.Run(() => { if (!process.WaitForExit(8000)) process.Kill(); process.Dispose(); });
    }
}
