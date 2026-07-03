using DwhiePaint.Api.Data;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenApi();

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("Default"))
           .UseSnakeCaseNamingConvention());

builder.Services.AddCors(options =>
    options.AddDefaultPolicy(policy =>
        policy.WithOrigins(builder.Configuration["Cors__Origin"] ?? "http://localhost:5173")
              .AllowAnyHeader()
              .AllowAnyMethod()));

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

app.UseCors();

// Apply migrations on startup (Postgres may still be booting → retry).
await ApplyMigrationsAsync(app);

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

app.MapGet("/health/db", async (AppDbContext db) =>
{
    var canConnect = await db.Database.CanConnectAsync();
    return canConnect ? Results.Ok(new { status = "ok", db = "up" })
                      : Results.StatusCode(503);
});

app.Run();

static async Task ApplyMigrationsAsync(WebApplication app)
{
    using var scope = app.Services.CreateScope();
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    var logger = scope.ServiceProvider.GetRequiredService<ILogger<Program>>();

    for (var attempt = 1; attempt <= 10; attempt++)
    {
        try
        {
            await db.Database.MigrateAsync();
            logger.LogInformation("Database migrations applied.");
            return;
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Migration attempt {Attempt}/10 failed; retrying in 3s.", attempt);
            await Task.Delay(TimeSpan.FromSeconds(3));
        }
    }

    logger.LogError("Could not apply migrations after 10 attempts.");
}
