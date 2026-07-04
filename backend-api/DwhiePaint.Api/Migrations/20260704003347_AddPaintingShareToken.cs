using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace DwhiePaint.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddPaintingShareToken : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<Guid>(
                name: "share_token",
                table: "paintings",
                type: "uuid",
                nullable: true);

            migrationBuilder.CreateIndex(
                name: "ix_paintings_share_token",
                table: "paintings",
                column: "share_token",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_paintings_share_token",
                table: "paintings");

            migrationBuilder.DropColumn(
                name: "share_token",
                table: "paintings");
        }
    }
}
