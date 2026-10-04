using Items.Domain;

namespace Items.Tests;

public class ItemInputTests
{
    private static ItemInput Input(string name = "Widget", string? description = "Blue", long price = 1999, long quantity = 5) =>
        new(name, description, price, quantity);

    [Fact]
    public void ValidInputPasses() => Input().Validate();

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    public void DescriptionMayBeNullOrEmpty(string? description) => Input(description: description).Validate();

    [Fact]
    public void DescriptionLengthCountsCodePoints()
    {
        Input(description: new string('d', 1000)).Validate();
        Input(description: string.Concat(Enumerable.Repeat("😀", 1000))).Validate();
        Assert.Throws<ValidationException>(() => Input(description: new string('d', 1001)).Validate());
        Assert.Throws<ValidationException>(() => Input(description: string.Concat(Enumerable.Repeat("😀", 1001))).Validate());
    }

    [Fact]
    public void NameLengthCountsCodePoints()
    {
        foreach (string name in new[] { "a", new string('a', 100), string.Concat(Enumerable.Repeat("😀", 100)) })
        {
            Input(name: name).Validate();
        }

        foreach (string name in new[] { "", new string('a', 101), string.Concat(Enumerable.Repeat("😀", 101)) })
        {
            Assert.Throws<ValidationException>(() => Input(name: name).Validate());
        }
    }

    [Theory]
    [InlineData(0L)]
    [InlineData(ItemInput.MaxPriceCents)]
    public void PriceWithinBoundsPasses(long price) => Input(price: price).Validate();

    [Theory]
    [InlineData(-1L)]
    [InlineData(ItemInput.MaxPriceCents + 1)]
    public void PriceOutOfBoundsFails(long price) =>
        Assert.Throws<ValidationException>(() => Input(price: price).Validate());

    [Theory]
    [InlineData(0L)]
    [InlineData(ItemInput.MaxQuantity)]
    public void QuantityWithinBoundsPasses(long quantity) => Input(quantity: quantity).Validate();

    [Theory]
    [InlineData(-1L)]
    [InlineData(ItemInput.MaxQuantity + 1)]
    public void QuantityOutOfBoundsFails(long quantity) =>
        Assert.Throws<ValidationException>(() => Input(quantity: quantity).Validate());

    [Theory]
    [InlineData(1L)]
    [InlineData(100_001L)]
    [InlineData(ItemInput.MaxId)]
    public void ValidIds(long id) => ItemInput.ValidateId(id);

    [Theory]
    [InlineData(0L)]
    [InlineData(-1L)]
    [InlineData(ItemInput.MaxId + 1)]
    public void InvalidIds(long id) =>
        Assert.Equal("invalid id", Assert.Throws<ValidationException>(() => ItemInput.ValidateId(id)).Message);

    [Fact]
    public void NotFoundHasAFixedMessage() => Assert.Equal("item not found", new NotFoundException().Message);

    [Fact]
    public void ItemExposesItsValues()
    {
        var created = new DateTime(2026, 10, 3, 10, 0, 0, DateTimeKind.Utc);
        var item = new Item(7, "Widget", null, 1999, 5, created, created.AddSeconds(1));
        Assert.Equal((7L, "Widget", null, 1999L, 5), (item.Id, item.Name, item.Description, item.PriceCents, item.Quantity));
        Assert.Equal(created, item.CreatedAt);
        Assert.Equal(created.AddSeconds(1), item.UpdatedAt);
    }
}
