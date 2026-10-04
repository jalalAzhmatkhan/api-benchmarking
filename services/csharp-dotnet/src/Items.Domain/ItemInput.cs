namespace Items.Domain;

/// <summary>
/// The payload for creating or replacing an item. Lengths are counted in Unicode code points
/// (Documentation/specs/api-contract.md).
/// </summary>
public sealed record ItemInput(string Name, string? Description, long PriceCents, long Quantity)
{
    public const long MaxId = 9_007_199_254_740_991;
    public const long MaxPriceCents = 9_007_199_254_740_991;
    public const long MaxQuantity = 2_147_483_647;
    public const int MaxNameLength = 100;
    public const int MaxDescriptionLength = 1000;

    /// <summary>Applies the contract's field rules.</summary>
    public void Validate()
    {
        int nameLength = Name.EnumerateRunes().Count();
        if (nameLength < 1 || nameLength > MaxNameLength)
        {
            throw new ValidationException("name must be 1-100 characters");
        }

        if (Description is not null && Description.EnumerateRunes().Count() > MaxDescriptionLength)
        {
            throw new ValidationException("description must be at most 1000 characters");
        }

        if (PriceCents < 0 || PriceCents > MaxPriceCents)
        {
            throw new ValidationException("price_cents must be an integer in 0..9007199254740991");
        }

        if (Quantity < 0 || Quantity > MaxQuantity)
        {
            throw new ValidationException("quantity must be an integer in 0..2147483647");
        }
    }

    /// <summary>Checks that <paramref name="id"/> is within 1..MaxId.</summary>
    public static void ValidateId(long id)
    {
        if (id < 1 || id > MaxId)
        {
            throw new ValidationException("invalid id");
        }
    }
}
