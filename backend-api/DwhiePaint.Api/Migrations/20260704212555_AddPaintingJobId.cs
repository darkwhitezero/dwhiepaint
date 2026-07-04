using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace DwhiePaint.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddPaintingJobId : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "job_id",
                table: "paintings",
                type: "text",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "job_id",
                table: "paintings");
        }
    }
}
