using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

namespace DwhiePaint.Api.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "color_dictionary",
                columns: table => new
                {
                    id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    hex = table.Column<string>(type: "text", nullable: false),
                    lab_l = table.Column<float>(type: "real", nullable: false),
                    lab_a = table.Column<float>(type: "real", nullable: false),
                    lab_b = table.Column<float>(type: "real", nullable: false),
                    name_ru = table.Column<string>(type: "text", nullable: false),
                    name_en = table.Column<string>(type: "text", nullable: true),
                    source = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_color_dictionary", x => x.id);
                });

            migrationBuilder.CreateTable(
                name: "users",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false, defaultValueSql: "gen_random_uuid()"),
                    email = table.Column<string>(type: "text", nullable: false),
                    password_hash = table.Column<string>(type: "text", nullable: false),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_users", x => x.id);
                });

            migrationBuilder.CreateTable(
                name: "images",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false, defaultValueSql: "gen_random_uuid()"),
                    user_id = table.Column<Guid>(type: "uuid", nullable: false),
                    original_path = table.Column<string>(type: "text", nullable: false),
                    width = table.Column<int>(type: "integer", nullable: false),
                    height = table.Column<int>(type: "integer", nullable: false),
                    uploaded_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_images", x => x.id);
                    table.ForeignKey(
                        name: "fk_images_users_user_id",
                        column: x => x.user_id,
                        principalTable: "users",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "paintings",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false, defaultValueSql: "gen_random_uuid()"),
                    image_id = table.Column<Guid>(type: "uuid", nullable: false),
                    color_count = table.Column<int>(type: "integer", nullable: false),
                    status = table.Column<string>(type: "text", nullable: false, defaultValue: "pending"),
                    result_path = table.Column<string>(type: "text", nullable: true),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_paintings", x => x.id);
                    table.ForeignKey(
                        name: "fk_paintings_images_image_id",
                        column: x => x.image_id,
                        principalTable: "images",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "palette_colors",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false, defaultValueSql: "gen_random_uuid()"),
                    painting_id = table.Column<Guid>(type: "uuid", nullable: false),
                    color_index = table.Column<int>(type: "integer", nullable: false),
                    hex = table.Column<string>(type: "text", nullable: false),
                    lab_l = table.Column<float>(type: "real", nullable: false),
                    lab_a = table.Column<float>(type: "real", nullable: false),
                    lab_b = table.Column<float>(type: "real", nullable: false),
                    name_ru = table.Column<string>(type: "text", nullable: false),
                    name_en = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_palette_colors", x => x.id);
                    table.ForeignKey(
                        name: "fk_palette_colors_paintings_painting_id",
                        column: x => x.painting_id,
                        principalTable: "paintings",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "ix_images_user_id",
                table: "images",
                column: "user_id");

            migrationBuilder.CreateIndex(
                name: "ix_paintings_image_id",
                table: "paintings",
                column: "image_id");

            migrationBuilder.CreateIndex(
                name: "ix_palette_colors_painting_id",
                table: "palette_colors",
                column: "painting_id");

            migrationBuilder.CreateIndex(
                name: "ix_users_email",
                table: "users",
                column: "email",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "color_dictionary");

            migrationBuilder.DropTable(
                name: "palette_colors");

            migrationBuilder.DropTable(
                name: "paintings");

            migrationBuilder.DropTable(
                name: "images");

            migrationBuilder.DropTable(
                name: "users");
        }
    }
}
