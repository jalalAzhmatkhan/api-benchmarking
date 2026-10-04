using System.Globalization;
using System.Text.Json.Serialization;
using Items.Domain;

namespace Items.Api;

/// <summary>Wire format of an item (snake_case names per the contract).</summary>
public sealed record ItemDto(
    [property: JsonPropertyName("id")] long Id,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("description")] string? Description,
    [property: JsonPropertyName("price_cents")] long PriceCents,
    [property: JsonPropertyName("quantity")] int Quantity,
    [property: JsonPropertyName("created_at")] string CreatedAt,
    [property: JsonPropertyName("updated_at")] string UpdatedAt)
{
    private static string Format(DateTime value) =>
        value.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss.FFFFFFF'Z'", CultureInfo.InvariantCulture);

    public static ItemDto From(Item item) => new(
        item.Id, item.Name, item.Description, item.PriceCents, item.Quantity, Format(item.CreatedAt), Format(item.UpdatedAt));
}

public sealed record ErrorDetail(
    [property: JsonPropertyName("code")] string Code,
    [property: JsonPropertyName("message")] string Message);

public sealed record ErrorBody([property: JsonPropertyName("error")] ErrorDetail Error);
