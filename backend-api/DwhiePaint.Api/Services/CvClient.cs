using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace DwhiePaint.Api.Services;

/// <summary>
/// Thin typed client for the internal Python CV service. The backend is the only
/// component exposed to the frontend; it proxies image work to this service.
/// </summary>
public class CvClient(HttpClient http)
{
    public async Task<JsonNode> AnalyzeAsync(
        Stream file, string fileName, string contentType, CancellationToken ct)
    {
        using var form = new MultipartFormDataContent();
        var fileContent = new StreamContent(file);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue(
            string.IsNullOrWhiteSpace(contentType) ? "application/octet-stream" : contentType);
        form.Add(fileContent, "file", fileName);

        using var resp = await http.PostAsync("/analyze", form, ct);
        return await ReadJsonAsync(resp, ct);
    }

    public async Task<JsonNode> SegmentAsync(string imageId, int k, CancellationToken ct)
    {
        var payload = JsonSerializer.Serialize(new { image_id = imageId, k });
        using var content = new StringContent(payload, Encoding.UTF8, "application/json");
        using var resp = await http.PostAsync("/segment", content, ct);
        return await ReadJsonAsync(resp, ct);
    }

    public async Task<(byte[] Bytes, string ContentType)> ExportAsync(
        string imageId, string pageSize, bool includeLegend, string format, CancellationToken ct)
    {
        var payload = JsonSerializer.Serialize(new
        {
            image_id = imageId,
            page_size = pageSize,
            include_legend = includeLegend,
            format,
        });
        using var content = new StringContent(payload, Encoding.UTF8, "application/json");
        using var resp = await http.PostAsync("/export", content, ct);
        await EnsureOkAsync(resp, ct);
        var bytes = await resp.Content.ReadAsByteArrayAsync(ct);
        var type = resp.Content.Headers.ContentType?.ToString() ?? "application/pdf";
        return (bytes, type);
    }

    public async Task<(byte[] Bytes, string ContentType)> GetCacheFileAsync(
        string imageId, string file, CancellationToken ct)
    {
        using var resp = await http.GetAsync($"/cache/{imageId}/{file}", ct);
        await EnsureOkAsync(resp, ct);
        var bytes = await resp.Content.ReadAsByteArrayAsync(ct);
        var type = resp.Content.Headers.ContentType?.ToString() ?? "application/octet-stream";
        return (bytes, type);
    }

    private static async Task<JsonNode> ReadJsonAsync(HttpResponseMessage resp, CancellationToken ct)
    {
        await EnsureOkAsync(resp, ct);
        var stream = await resp.Content.ReadAsStreamAsync(ct);
        return await JsonNode.ParseAsync(stream, cancellationToken: ct)
               ?? throw new CvServiceException("cv-service returned empty body");
    }

    private static async Task EnsureOkAsync(HttpResponseMessage resp, CancellationToken ct)
    {
        if (resp.IsSuccessStatusCode) return;
        var detail = await resp.Content.ReadAsStringAsync(ct);
        throw new CvServiceException($"cv-service {(int)resp.StatusCode}: {detail}", resp.StatusCode);
    }
}

public class CvServiceException(string message, System.Net.HttpStatusCode? status = null)
    : Exception(message)
{
    public System.Net.HttpStatusCode? Status { get; } = status;
}
