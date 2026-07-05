namespace DwhiePaint.Api.Services;

/// <summary>Persists original uploads and exported results on a mounted volume.</summary>
public class FileStorage
{
    private readonly string _root;

    public FileStorage(IConfiguration config)
    {
        _root = config["Storage:UploadsPath"] ?? "/data/uploads";
        Directory.CreateDirectory(_root);
    }

    public async Task<string> SaveOriginalAsync(Guid imageId, byte[] bytes, string? originalName, CancellationToken ct)
    {
        var ext = Path.GetExtension(originalName ?? "").ToLowerInvariant();
        if (string.IsNullOrWhiteSpace(ext) || ext.Length > 6) ext = ".img";
        var path = Path.Combine(_root, $"{imageId}{ext}");
        await File.WriteAllBytesAsync(path, bytes, ct);
        return path;
    }

    public async Task<string> SaveResultAsync(Guid imageId, byte[] bytes, string ext, CancellationToken ct)
    {
        var path = Path.Combine(_root, $"{imageId}-result{ext}");
        await File.WriteAllBytesAsync(path, bytes, ct);
        return path;
    }

    public static string GuessContentType(string path) => Path.GetExtension(path).ToLowerInvariant() switch
    {
        ".png" => "image/png",
        ".jpg" or ".jpeg" => "image/jpeg",
        ".webp" => "image/webp",
        ".gif" => "image/gif",
        ".pdf" => "application/pdf",
        ".svg" => "image/svg+xml",
        ".zip" => "application/zip",
        _ => "application/octet-stream",
    };

    public static string ExtForContentType(string contentType) => contentType switch
    {
        "application/pdf" => ".pdf",
        "image/png" => ".png",
        "image/svg+xml" => ".svg",
        "application/zip" => ".zip",
        _ => ".bin",
    };
}
