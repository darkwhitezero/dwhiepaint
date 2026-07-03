namespace DwhiePaint.Api.Domain;

/// <summary>
/// Static reference table for color naming. No FK to user data.
/// Seeded from cv-service/data/colors.json (Russian color names).
/// </summary>
public class ColorDictionaryEntry
{
    public int Id { get; set; }
    public string Hex { get; set; } = null!;
    public float LabL { get; set; }
    public float LabA { get; set; }
    public float LabB { get; set; }
    public string NameRu { get; set; } = null!;
    public string? NameEn { get; set; }
    public string? Source { get; set; }
}
