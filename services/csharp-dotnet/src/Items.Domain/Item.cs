namespace Items.Domain;

/// <summary>A stored item.</summary>
public sealed record Item(
    long Id,
    string Name,
    string? Description,
    long PriceCents,
    int Quantity,
    DateTime CreatedAt,
    DateTime UpdatedAt);
