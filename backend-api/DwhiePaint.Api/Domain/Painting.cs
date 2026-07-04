namespace DwhiePaint.Api.Domain;

public static class PaintingStatus
{
    public const string Pending = "pending";
    public const string Processing = "processing";
    // Segmentation finished — palette persisted, ready to export.
    public const string Ready = "ready";
    // A result file has been exported (has_result == true).
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

    // Id of the in-flight async segmentation job (ARQ, in Redis). Set when a
    // /segment job is enqueued; polled via /segment status to stream progress
    // and to persist the palette once the job completes.
    public string? JobId { get; set; }

    // Set when the owner shares this painting; a separate opaque value from
    // Id so a share link can't be guessed from a painting's own URL, and can
    // be revoked (set back to null) without touching the painting itself.
    public Guid? ShareToken { get; set; }

    public Image? Image { get; set; }
    public ICollection<PaletteColor> PaletteColors { get; set; } = new List<PaletteColor>();
}
