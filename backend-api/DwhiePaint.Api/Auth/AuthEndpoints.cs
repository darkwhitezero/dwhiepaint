using System.Security.Claims;
using System.Text.RegularExpressions;
using DwhiePaint.Api.Data;
using DwhiePaint.Api.Domain;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;

namespace DwhiePaint.Api.Auth;

public static class AuthEndpoints
{
    public record AuthRequest(string Email, string Password);

    private static readonly PasswordHasher<User> Hasher = new();

    public static IEndpointRouteBuilder MapAuthEndpoints(this IEndpointRouteBuilder app)
    {
        // Stricter rate limit on auth to blunt credential stuffing / brute force.
        var group = app.MapGroup("/api/auth").RequireRateLimiting("auth");

        group.MapPost("/register", async (
            AuthRequest req, AppDbContext db, TokenService tokens) =>
        {
            var email = req.Email?.Trim().ToLowerInvariant() ?? "";
            if (!IsValidEmail(email))
                return Results.BadRequest(new { error = "invalid email" });
            if (string.IsNullOrWhiteSpace(req.Password) || req.Password.Length < 8)
                return Results.BadRequest(new { error = "password must be at least 8 characters" });

            if (await db.Users.AnyAsync(u => u.Email == email))
                return Results.Conflict(new { error = "email already registered" });

            var user = new User { Id = Guid.NewGuid(), Email = email };
            user.PasswordHash = Hasher.HashPassword(user, req.Password);
            db.Users.Add(user);
            await db.SaveChangesAsync();

            return Results.Ok(new { token = tokens.CreateToken(user), email = user.Email });
        });

        group.MapPost("/login", async (
            AuthRequest req, AppDbContext db, TokenService tokens) =>
        {
            var email = req.Email?.Trim().ToLowerInvariant() ?? "";
            var user = await db.Users.FirstOrDefaultAsync(u => u.Email == email);
            if (user is null)
                return Results.Unauthorized();

            var result = Hasher.VerifyHashedPassword(user, user.PasswordHash, req.Password);
            if (result == PasswordVerificationResult.Failed)
                return Results.Unauthorized();

            return Results.Ok(new { token = tokens.CreateToken(user), email = user.Email });
        });

        group.MapGet("/me", (ClaimsPrincipal principal) =>
            Results.Ok(new { email = principal.FindFirstValue(ClaimTypes.Email) }))
            .RequireAuthorization();

        return app;
    }

    private static bool IsValidEmail(string email) =>
        Regex.IsMatch(email, @"^[^@\s]+@[^@\s]+\.[^@\s]+$");
}
