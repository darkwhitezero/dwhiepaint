using System.Security.Claims;
using System.Text.Json.Nodes;
using DwhiePaint.Api.Auth;
using DwhiePaint.Api.Data;
using DwhiePaint.Api.Domain;
using DwhiePaint.Api.Services;
using Microsoft.EntityFrameworkCore;

namespace DwhiePaint.Api.Endpoints;

/// <summary>
/// Painting endpoints. Data/JSON routes require auth and are scoped to the current
/// user. Image-byte routes (previews, region maps, original thumbnails) are served
/// anonymously by unguessable UUID so plain &lt;img&gt; tags can load them.
/// </summary>
public static class PaintingEndpoints
{
    public record ColorsRequest(int K);

    public static IEndpointRouteBuilder MapPaintingEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/paintings").RequireAuthorization();

        group.MapPost("", CreatePainting).DisableAntiforgery();
        group.MapGet("", ListPaintings);
        group.MapGet("/{id:guid}", GetPainting);
        group.MapPatch("/{id:guid}/colors", SetColors);
        group.MapGet("/{id:guid}/export", ExportPainting);
        group.MapGet("/{id:guid}/result", DownloadResult);
        group.MapPost("/{id:guid}/share", CreateShareLink);
        group.MapDelete("/{id:guid}/share", RevokeShareLink);

        // Anonymous image bytes (opaque UUID).
        app.MapGet("/api/paintings/{id:guid}/original", GetOriginal);
        app.MapGet("/api/cv-cache/{id:guid}/{file}", GetCvCache);

        // Anonymous read-only access via a separate, revocable share token
        // (never the painting's own id, so a share link can't be guessed).
        // Serves the already-exported result, not a fresh cv-service render,
        // so a share link keeps working long after the cv-service's
        // in-memory session cache (~30 min TTL) has expired.
        app.MapGet("/api/shared/{token:guid}", GetShared);
        app.MapGet("/api/shared/{token:guid}/result", GetSharedResult);

        return app;
    }

    private static async Task<IResult> CreatePainting(
        IFormFile file, ClaimsPrincipal principal, CvClient cv, AppDbContext db,
        FileStorage storage, CancellationToken ct)
    {
        if (file.Length == 0) return Results.BadRequest(new { error = "empty file" });

        var userId = principal.GetUserId();
        // The JWT can outlive the user row (e.g. account removed, dev DB reset);
        // fail fast with 401 instead of a 500 on the FK constraint below.
        if (!await db.Users.AnyAsync(u => u.Id == userId, ct))
            return Results.Unauthorized();

        byte[] bytes;
        await using (var ms = new MemoryStream())
        {
            await file.CopyToAsync(ms, ct);
            bytes = ms.ToArray();
        }

        var result = await cv.AnalyzeAsync(new MemoryStream(bytes), file.FileName, file.ContentType, ct);
        var imageId = Guid.Parse(result["image_id"]!.GetValue<string>());
        var predictedK = result["predicted_k"]!.GetValue<int>();
        var width = result["width"]!.GetValue<int>();
        var height = result["height"]!.GetValue<int>();

        var originalPath = await storage.SaveOriginalAsync(imageId, bytes, file.FileName, ct);

        db.Images.Add(new Image
        {
            Id = imageId, UserId = userId, OriginalPath = originalPath,
            Width = width, Height = height,
        });
        db.Paintings.Add(new Painting
        {
            Id = imageId, ImageId = imageId, ColorCount = predictedK,
            Status = PaintingStatus.Processing,
        });
        await db.SaveChangesAsync(ct);

        RewriteCacheUrl(result, "preview_url");
        return Results.Json(result);
    }

    private static async Task<IResult> SetColors(
        Guid id, ColorsRequest body, ClaimsPrincipal principal,
        CvClient cv, AppDbContext db, CancellationToken ct)
    {
        var painting = await OwnedPainting(db, id, principal.GetUserId(), ct);
        if (painting is null) return Results.NotFound();

        var result = await cv.SegmentAsync(id.ToString(), body.K, ct);

        var existing = db.PaletteColors.Where(p => p.PaintingId == painting.Id);
        db.PaletteColors.RemoveRange(existing);

        foreach (var node in result["palette"]!.AsArray())
        {
            var lab = node!["lab"]!.AsArray();
            db.PaletteColors.Add(new PaletteColor
            {
                PaintingId = painting.Id,
                ColorIndex = node["index"]!.GetValue<int>(),
                Hex = node["hex"]!.GetValue<string>(),
                LabL = (float)lab[0]!.GetValue<double>(),
                LabA = (float)lab[1]!.GetValue<double>(),
                LabB = (float)lab[2]!.GetValue<double>(),
                NameRu = node["name_ru"]!.GetValue<string>(),
                NameEn = node["name_en"]?.GetValue<string?>(),
            });
        }

        painting.ColorCount = result["k"]!.GetValue<int>();
        await db.SaveChangesAsync(ct);

        RewriteCacheUrl(result, "region_map_url");
        RewriteCacheUrl(result, "painted_preview_url");
        RewriteCacheUrl(result, "svg_url");
        return Results.Json(result);
    }

    private static async Task<IResult> ExportPainting(
        Guid id, ClaimsPrincipal principal, CvClient cv, AppDbContext db,
        FileStorage storage, CancellationToken ct,
        string pageSize = "A4", bool includeLegend = true, string format = "pdf")
    {
        var painting = await OwnedPainting(db, id, principal.GetUserId(), ct);
        if (painting is null) return Results.NotFound();

        var (bytes, contentType) = await cv.ExportAsync(id.ToString(), pageSize, includeLegend, format, ct);
        var ext = FileStorage.ExtForContentType(contentType);
        painting.ResultPath = await storage.SaveResultAsync(id, bytes, ext, ct);
        painting.Status = PaintingStatus.Done;
        await db.SaveChangesAsync(ct);

        return Results.File(bytes, contentType, $"dwhiepaint-{id}{ext}");
    }

    private static async Task<IResult> DownloadResult(
        Guid id, ClaimsPrincipal principal, AppDbContext db, CancellationToken ct)
    {
        var painting = await OwnedPainting(db, id, principal.GetUserId(), ct);
        return await ResultFile(painting, id, ct);
    }

    private static async Task<IResult> GetSharedResult(Guid token, AppDbContext db, CancellationToken ct)
    {
        var painting = await db.Paintings.FirstOrDefaultAsync(p => p.ShareToken == token, ct);
        return await ResultFile(painting, painting?.ImageId ?? Guid.Empty, ct);
    }

    /// <summary>Shared by the owner's and the share-link's result-download routes.</summary>
    private static async Task<IResult> ResultFile(Painting? painting, Guid id, CancellationToken ct)
    {
        if (painting?.ResultPath is null || !File.Exists(painting.ResultPath))
            return Results.NotFound();

        var bytes = await File.ReadAllBytesAsync(painting.ResultPath, ct);
        var contentType = FileStorage.GuessContentType(painting.ResultPath);
        var ext = Path.GetExtension(painting.ResultPath);
        return Results.File(bytes, contentType, $"dwhiepaint-{id}{ext}");
    }

    private static async Task<IResult> ListPaintings(
        ClaimsPrincipal principal, AppDbContext db, CancellationToken ct)
    {
        var userId = principal.GetUserId();
        var items = await (
            from p in db.Paintings
            join img in db.Images on p.ImageId equals img.Id
            where img.UserId == userId
            orderby p.CreatedAt descending
            select new
            {
                image_id = p.ImageId,
                color_count = p.ColorCount,
                status = p.Status,
                created_at = p.CreatedAt,
                has_result = p.ResultPath != null,
                original_url = $"/api/paintings/{p.ImageId}/original",
                share_url = p.ShareToken == null ? null : "/s/" + p.ShareToken,
            }).ToListAsync(ct);

        return Results.Ok(items);
    }

    private static async Task<IResult> GetPainting(
        Guid id, ClaimsPrincipal principal, AppDbContext db, CancellationToken ct)
    {
        var userId = principal.GetUserId();
        var painting = await OwnedPainting(db, id, userId, ct);
        if (painting is null) return Results.NotFound();

        var palette = await db.PaletteColors
            .Where(c => c.PaintingId == painting.Id)
            .OrderBy(c => c.ColorIndex)
            .Select(c => new
            {
                index = c.ColorIndex, hex = c.Hex,
                lab = new[] { c.LabL, c.LabA, c.LabB },
                name_ru = c.NameRu, name_en = c.NameEn,
            })
            .ToListAsync(ct);

        return Results.Ok(new
        {
            image_id = painting.ImageId,
            color_count = painting.ColorCount,
            status = painting.Status,
            has_result = painting.ResultPath != null,
            original_url = $"/api/paintings/{painting.ImageId}/original",
            share_url = painting.ShareToken == null ? null : $"/s/{painting.ShareToken}",
            palette,
        });
    }

    private static async Task<IResult> CreateShareLink(
        Guid id, ClaimsPrincipal principal, AppDbContext db, CancellationToken ct)
    {
        var painting = await OwnedPainting(db, id, principal.GetUserId(), ct);
        if (painting is null) return Results.NotFound();

        painting.ShareToken ??= Guid.NewGuid();
        await db.SaveChangesAsync(ct);

        return Results.Ok(new { share_url = $"/s/{painting.ShareToken}" });
    }

    private static async Task<IResult> RevokeShareLink(
        Guid id, ClaimsPrincipal principal, AppDbContext db, CancellationToken ct)
    {
        var painting = await OwnedPainting(db, id, principal.GetUserId(), ct);
        if (painting is null) return Results.NotFound();

        painting.ShareToken = null;
        await db.SaveChangesAsync(ct);

        return Results.NoContent();
    }

    private static async Task<IResult> GetShared(Guid token, AppDbContext db, CancellationToken ct)
    {
        var painting = await db.Paintings.FirstOrDefaultAsync(p => p.ShareToken == token, ct);
        if (painting is null) return Results.NotFound();

        var palette = await db.PaletteColors
            .Where(c => c.PaintingId == painting.Id)
            .OrderBy(c => c.ColorIndex)
            .Select(c => new
            {
                index = c.ColorIndex, hex = c.Hex,
                lab = new[] { c.LabL, c.LabA, c.LabB },
                name_ru = c.NameRu, name_en = c.NameEn,
            })
            .ToListAsync(ct);

        return Results.Ok(new
        {
            image_id = painting.ImageId,
            color_count = painting.ColorCount,
            status = painting.Status,
            has_result = painting.ResultPath != null,
            original_url = $"/api/paintings/{painting.ImageId}/original",
            palette,
        });
    }

    private static async Task<IResult> GetOriginal(Guid id, AppDbContext db, CancellationToken ct)
    {
        var image = await db.Images.FirstOrDefaultAsync(i => i.Id == id, ct);
        if (image is null || !File.Exists(image.OriginalPath)) return Results.NotFound();

        var bytes = await File.ReadAllBytesAsync(image.OriginalPath, ct);
        return Results.File(bytes, FileStorage.GuessContentType(image.OriginalPath));
    }

    private static async Task<IResult> GetCvCache(Guid id, string file, CvClient cv, CancellationToken ct)
    {
        var (bytes, contentType) = await cv.GetCacheFileAsync(id.ToString(), file, ct);
        return Results.File(bytes, contentType);
    }

    private static Task<Painting?> OwnedPainting(AppDbContext db, Guid imageId, Guid userId, CancellationToken ct) =>
        (from p in db.Paintings
         join img in db.Images on p.ImageId equals img.Id
         where p.ImageId == imageId && img.UserId == userId
         select p).FirstOrDefaultAsync(ct);

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
