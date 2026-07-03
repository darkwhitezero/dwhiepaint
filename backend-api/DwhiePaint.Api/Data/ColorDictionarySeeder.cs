using System.Text.Json;
using DwhiePaint.Api.Domain;
using Microsoft.EntityFrameworkCore;

namespace DwhiePaint.Api.Data;

/// <summary>
/// Seeds the static color_dictionary reference table from Data/colors.json.
/// Lab values are derived from RGB (sRGB → D65 XYZ → Lab) so the table matches
/// the schema even though live color naming currently runs in the CV service.
/// </summary>
public static class ColorDictionarySeeder
{
    private record ColorRow(string Name, string Hex, int R, int G, int B);

    public static async Task SeedAsync(AppDbContext db, string contentRoot, ILogger logger, CancellationToken ct = default)
    {
        if (await db.ColorDictionary.AnyAsync(ct)) return;

        var path = Path.Combine(contentRoot, "Data", "colors.json");
        if (!File.Exists(path))
        {
            logger.LogWarning("colors.json not found at {Path}; skipping color_dictionary seed.", path);
            return;
        }

        await using var stream = File.OpenRead(path);
        var rows = await JsonSerializer.DeserializeAsync<List<ColorRow>>(
            stream, new JsonSerializerOptions { PropertyNameCaseInsensitive = true }, ct) ?? [];

        foreach (var row in rows)
        {
            var (l, a, b) = RgbToLab(row.R, row.G, row.B);
            db.ColorDictionary.Add(new ColorDictionaryEntry
            {
                Hex = row.Hex,
                LabL = (float)l, LabA = (float)a, LabB = (float)b,
                NameRu = row.Name, NameEn = null, Source = "colors.json",
            });
        }

        await db.SaveChangesAsync(ct);
        logger.LogInformation("Seeded {Count} color dictionary entries.", rows.Count);
    }

    private static (double L, double A, double B) RgbToLab(int r, int g, int b)
    {
        double rl = Linearize(r / 255.0), gl = Linearize(g / 255.0), bl = Linearize(b / 255.0);

        // sRGB → XYZ (D65)
        double x = rl * 0.4124 + gl * 0.3576 + bl * 0.1805;
        double y = rl * 0.2126 + gl * 0.7152 + bl * 0.0722;
        double z = rl * 0.0193 + gl * 0.1192 + bl * 0.9505;

        double fx = F(x / 0.95047), fy = F(y / 1.00000), fz = F(z / 1.08883);
        return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz));
    }

    private static double Linearize(double c) =>
        c > 0.04045 ? Math.Pow((c + 0.055) / 1.055, 2.4) : c / 12.92;

    private static double F(double t) =>
        t > 0.008856 ? Math.Cbrt(t) : 7.787 * t + 16.0 / 116.0;
}
