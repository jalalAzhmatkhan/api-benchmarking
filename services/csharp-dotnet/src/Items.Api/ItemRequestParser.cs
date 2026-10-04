using System.Text.Json;
using Items.Domain;

namespace Items.Api;

/// <summary>
/// Parses the request body strictly: syntax errors, wrong JSON types (a string where a number is
/// expected, a fraction where an integer is expected, a number above 64 bits) and missing required
/// fields are validation errors; unknown fields are ignored. Range rules live in the domain.
/// </summary>
public static class ItemRequestParser
{
    public static async Task<ItemInput> ParseAsync(Stream body, CancellationToken ct)
    {
        JsonDocument document;
        try
        {
            document = await JsonDocument.ParseAsync(body, cancellationToken: ct);
        }
        catch (JsonException)
        {
            throw new ValidationException("malformed JSON body");
        }

        using (document)
        {
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
            {
                throw new ValidationException("body must be a JSON object");
            }

            return new ItemInput(
                RequiredString(root, "name"),
                OptionalString(root, "description"),
                RequiredLong(root, "price_cents"),
                RequiredLong(root, "quantity"));
        }
    }

    private static string RequiredString(JsonElement root, string field) =>
        root.TryGetProperty(field, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()!
            : throw new ValidationException($"{field} is required and must be a string");

    private static string? OptionalString(JsonElement root, string field)
    {
        if (!root.TryGetProperty(field, out JsonElement value) || value.ValueKind == JsonValueKind.Null)
        {
            return null;
        }

        return value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : throw new ValidationException($"{field} must be a string or null");
    }

    private static long RequiredLong(JsonElement root, string field) =>
        root.TryGetProperty(field, out JsonElement value) && value.ValueKind == JsonValueKind.Number && value.TryGetInt64(out long number)
            ? number
            : throw new ValidationException($"{field} is required and must be an integer");
}
