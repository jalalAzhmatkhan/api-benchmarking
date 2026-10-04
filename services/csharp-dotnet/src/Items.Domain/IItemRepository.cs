namespace Items.Domain;

/// <summary>Persistence port, implemented by the infrastructure layer.</summary>
public interface IItemRepository
{
    /// <exception cref="NotFoundException">The item does not exist.</exception>
    Task<Item> GetAsync(long id, CancellationToken cancellationToken);

    Task<Item> CreateAsync(ItemInput input, CancellationToken cancellationToken);

    /// <exception cref="NotFoundException">The item does not exist.</exception>
    Task<Item> ReplaceAsync(long id, ItemInput input, CancellationToken cancellationToken);

    /// <exception cref="NotFoundException">The item does not exist.</exception>
    Task DeleteAsync(long id, CancellationToken cancellationToken);
}
