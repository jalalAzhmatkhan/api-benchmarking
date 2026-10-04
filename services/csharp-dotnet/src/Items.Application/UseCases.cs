using Items.Domain;

namespace Items.Application;

/// <summary>Use case: load one item.</summary>
public sealed class GetItem(IItemRepository repository)
{
    public Task<Item> ExecuteAsync(long id, CancellationToken cancellationToken)
    {
        ItemInput.ValidateId(id);
        return repository.GetAsync(id, cancellationToken);
    }
}

/// <summary>Use case: validate and create an item.</summary>
public sealed class CreateItem(IItemRepository repository)
{
    public Task<Item> ExecuteAsync(ItemInput input, CancellationToken cancellationToken)
    {
        input.Validate();
        return repository.CreateAsync(input, cancellationToken);
    }
}

/// <summary>Use case: validate id and input, then replace the whole item.</summary>
public sealed class ReplaceItem(IItemRepository repository)
{
    public Task<Item> ExecuteAsync(long id, ItemInput input, CancellationToken cancellationToken)
    {
        ItemInput.ValidateId(id);
        input.Validate();
        return repository.ReplaceAsync(id, input, cancellationToken);
    }
}

/// <summary>Use case: delete an item.</summary>
public sealed class DeleteItem(IItemRepository repository)
{
    public Task ExecuteAsync(long id, CancellationToken cancellationToken)
    {
        ItemInput.ValidateId(id);
        return repository.DeleteAsync(id, cancellationToken);
    }
}
