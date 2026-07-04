namespace DwhiePaint.Api.Domain;

public static class PaintingStatus
{
    public const string Pending = "pending";
    public const string Processing = "processing";
    public const string Done = "done";
    public const string Failed = "failed";
}

public class Painting
{
    public Guid Id { get; set; }
    public Guid ImageId { get; set; }
    public int ColorCount { get; set; }
    public string Status { get; set; } = PaintingStatus.Pending;
    public string? ResultPath { get; set; }
    public DateTimeOffset CreatedAt { get; set; }

    // Set when the owner shares this painting; a separate opaque value from
    // Id so a share link can't be guessed from a painting's own URL, and can
    // be revoked (set back to null) without touching the painting itself.
    public Guid? ShareToken { get; set; }

    public Image? Image { get; set; }
    public ICollection<PaletteColor> PaletteColors { get; set; } = new List<PaletteColor>();
}
