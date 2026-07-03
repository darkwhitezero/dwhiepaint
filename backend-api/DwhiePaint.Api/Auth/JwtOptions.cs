namespace DwhiePaint.Api.Auth;

public class JwtOptions
{
    public const string SectionName = "Jwt";

    public string Secret { get; set; } = null!;
    public string Issuer { get; set; } = "dwhiepaint";
    public string Audience { get; set; } = "dwhiepaint";
    public int ExpiryMinutes { get; set; } = 60 * 24;
}
