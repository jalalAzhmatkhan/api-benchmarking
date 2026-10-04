package bench.items.domain;

import java.time.Instant;

/** A stored item. */
public record Item(
    long id,
    String name,
    String description,
    long priceCents,
    int quantity,
    Instant createdAt,
    Instant updatedAt) {}
