using Items.Application;
using Items.Domain;

namespace Items.Tests;

public class UseCasesTests
{
    /// <summary>Records calls; optionally fails every call with NotFoundException.</summary>
    private sealed class FakeRepository(bool missing) : IItemRepository
    {
        public List<string> Calls { get; } = [];

        private static Item Item(long id) => new(id, "n", null, 1, 1, DateTime.UnixEpoch, DateTime.UnixEpoch);

        private void Record(string call)
        {
            Calls.Add(call);
            if (missing)
            {
                throw new NotFoundException();
            }
        }

        public Task<Item> GetAsync(long id, CancellationToken ct) { Record("get"); return Task.FromResult(Item(id)); }
        public Task<Item> CreateAsync(ItemInput input, CancellationToken ct) { Record("create"); return Task.FromResult(Item(100_001)); }
        public Task<Item> ReplaceAsync(long id, ItemInput input, CancellationToken ct) { Record("replace"); return Task.FromResult(Item(id)); }
        public Task DeleteAsync(long id, CancellationToken ct) { Record("delete"); return Task.CompletedTask; }
    }

    private static readonly ItemInput Ok = new("n", null, 1, 1);
    private static readonly ItemInput Bad = new("", null, 1, 1);
    private static readonly CancellationToken Ct = CancellationToken.None;

    [Fact]
    public async Task GetItem()
    {
        var repo = new FakeRepository(false);
        Assert.Equal(7, (await new GetItem(repo).ExecuteAsync(7, Ct)).Id);
        await Assert.ThrowsAsync<ValidationException>(() => new GetItem(repo).ExecuteAsync(0, Ct));
        Assert.Equal(["get"], repo.Calls);
        await Assert.ThrowsAsync<NotFoundException>(() => new GetItem(new FakeRepository(true)).ExecuteAsync(1, Ct));
    }

    [Fact]
    public async Task CreateItem()
    {
        var repo = new FakeRepository(false);
        Assert.Equal(100_001, (await new CreateItem(repo).ExecuteAsync(Ok, Ct)).Id);
        await Assert.ThrowsAsync<ValidationException>(() => new CreateItem(repo).ExecuteAsync(Bad, Ct));
        Assert.Equal(["create"], repo.Calls);
    }

    [Fact]
    public async Task ReplaceItem()
    {
        var repo = new FakeRepository(false);
        Assert.Equal(5, (await new ReplaceItem(repo).ExecuteAsync(5, Ok, Ct)).Id);
        await Assert.ThrowsAsync<ValidationException>(() => new ReplaceItem(repo).ExecuteAsync(-1, Ok, Ct));
        await Assert.ThrowsAsync<ValidationException>(() => new ReplaceItem(repo).ExecuteAsync(1, Bad, Ct));
        Assert.Equal(["replace"], repo.Calls);
        await Assert.ThrowsAsync<NotFoundException>(() => new ReplaceItem(new FakeRepository(true)).ExecuteAsync(1, Ok, Ct));
    }

    [Fact]
    public async Task DeleteItem()
    {
        var repo = new FakeRepository(false);
        await new DeleteItem(repo).ExecuteAsync(9, Ct);
        await Assert.ThrowsAsync<ValidationException>(() => new DeleteItem(repo).ExecuteAsync(0, Ct));
        Assert.Equal(["delete"], repo.Calls);
        await Assert.ThrowsAsync<NotFoundException>(() => new DeleteItem(new FakeRepository(true)).ExecuteAsync(1, Ct));
    }
}
