using System.Text.Json.Nodes;
using DwhiePaint.Api.Services;

namespace DwhiePaint.Api.Endpoints;

/// <summary>
/// Phase 1 painting endpoints — thin proxies over the CV service, no persistence yet.
/// Cache URLs returned by cv-service are rewritten so the browser only ever talks
/// to the backend (which passes image bytes through /api/cv-cache).
/// </summary>
public static class PaintingEndpoints
{
    public record ColorsRequest(int K);

    public static IEndpointRouteBuilder MapPaintingEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/paintings");

        group.MapPost("", async (IFormFile file, CvClient cv, CancellationToken ct) =>
        {
            if (file.Length == 0)
                return Results.BadRequest(new { error = "empty file" });

            await using var stream = file.OpenReadStream();
            var result = await cv.AnalyzeAsync(stream, file.FileName, file.ContentType, ct);
            RewriteCacheUrl(result, "preview_url");
            return Results.Json(result);
        }).DisableAntiforgery();

        group.MapPatch("/{id}/colors", async (
            string id, ColorsRequest body, CvClient cv, CancellationToken ct) =>
        {
            var result = await cv.SegmentAsync(id, body.K, ct);
            RewriteCacheUrl(result, "region_map_url");
            return Results.Json(result);
        });

        group.MapGet("/{id}/export", async (
            string id, CvClient cv, CancellationToken ct, string pageSize = "A4") =>
        {
            var png = await cv.ExportAsync(id, pageSize, ct);
            return Results.File(png, "image/png", $"dwhiepaint-{id}.png");
        });

        // Passthrough for cv-service cache files (previews, region maps).
        app.MapGet("/api/cv-cache/{id}/{file}", async (
            string id, string file, CvClient cv, CancellationToken ct) =>
        {
            var (bytes, contentType) = await cv.GetCacheFileAsync(id, file, ct);
            return Results.File(bytes, contentType);
        });

        return app;
    }

    private static void RewriteCacheUrl(JsonNode? node, string field)
    {
        const string prefix = "/cache/";
        if (node?[field] is JsonValue value
            && value.TryGetValue<string>(out var url)
            && url.StartsWith(prefix, StringComparison.Ordinal))
        {
            node![field] = "/api/cv-cache/" + url[prefix.Length..];
        }
    }
}
