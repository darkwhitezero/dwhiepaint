namespace DwhiePaint.Api.Domain;

public class User
{
    public Guid Id { get; set; }
    public string Email { get; set; } = null!;
    public string PasswordHash { get; set; } = null!;
    public DateTimeOffset CreatedAt { get; set; }

    public ICollection<Image> Images { get; set; } = new List<Image>();
}
