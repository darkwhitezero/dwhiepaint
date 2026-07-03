namespace DwhiePaint.Api.Domain;

public class Image
{
    public Guid Id { get; set; }
    public Guid UserId { get; set; }
    public string OriginalPath { get; set; } = null!;
    public int Width { get; set; }
    public int Height { get; set; }
    public DateTimeOffset UploadedAt { get; set; }

    public User? User { get; set; }
    public ICollection<Painting> Paintings { get; set; } = new List<Painting>();
}
