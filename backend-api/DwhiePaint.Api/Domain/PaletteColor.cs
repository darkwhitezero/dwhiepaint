namespace DwhiePaint.Api.Domain;

public class PaletteColor
{
    public Guid Id { get; set; }
    public Guid PaintingId { get; set; }
    public int ColorIndex { get; set; }
    public string Hex { get; set; } = null!;
    public float LabL { get; set; }
    public float LabA { get; set; }
    public float LabB { get; set; }
    public string NameRu { get; set; } = null!;
    public string? NameEn { get; set; }

    public Painting? Painting { get; set; }
}
