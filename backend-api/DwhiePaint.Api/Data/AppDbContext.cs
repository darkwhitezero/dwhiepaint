using DwhiePaint.Api.Domain;
using Microsoft.EntityFrameworkCore;

namespace DwhiePaint.Api.Data;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<User> Users => Set<User>();
    public DbSet<Image> Images => Set<Image>();
    public DbSet<Painting> Paintings => Set<Painting>();
    public DbSet<PaletteColor> PaletteColors => Set<PaletteColor>();
    public DbSet<ColorDictionaryEntry> ColorDictionary => Set<ColorDictionaryEntry>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<User>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Id).HasDefaultValueSql("gen_random_uuid()");
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
            e.HasIndex(x => x.Email).IsUnique();
        });

        b.Entity<Image>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Id).HasDefaultValueSql("gen_random_uuid()");
            e.Property(x => x.UploadedAt).HasDefaultValueSql("now()");
            e.HasOne(x => x.User)
                .WithMany(u => u.Images)
                .HasForeignKey(x => x.UserId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        b.Entity<Painting>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Id).HasDefaultValueSql("gen_random_uuid()");
            e.Property(x => x.Status).HasDefaultValue(PaintingStatus.Pending);
            e.Property(x => x.CreatedAt).HasDefaultValueSql("now()");
            e.HasIndex(x => x.ShareToken).IsUnique();
            e.HasOne(x => x.Image)
                .WithMany(i => i.Paintings)
                .HasForeignKey(x => x.ImageId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        b.Entity<PaletteColor>(e =>
        {
            e.HasKey(x => x.Id);
            e.Property(x => x.Id).HasDefaultValueSql("gen_random_uuid()");
            e.HasOne(x => x.Painting)
                .WithMany(p => p.PaletteColors)
                .HasForeignKey(x => x.PaintingId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        b.Entity<ColorDictionaryEntry>(e =>
        {
            e.HasKey(x => x.Id);
        });
    }
}
