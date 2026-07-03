using System.Security.Claims;

namespace DwhiePaint.Api.Auth;

public static class ClaimsPrincipalExtensions
{
    public static Guid GetUserId(this ClaimsPrincipal principal)
    {
        var raw = principal.FindFirstValue(ClaimTypes.NameIdentifier)
                  ?? throw new UnauthorizedAccessException("missing subject claim");
        return Guid.Parse(raw);
    }
}
