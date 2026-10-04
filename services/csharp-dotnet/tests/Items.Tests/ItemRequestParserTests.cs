using System.Text;
using Items.Api;
using Items.Domain;

namespace Items.Tests;

public class ItemRequestParserTests
{
    private static Task<ItemInput> Parse(string json) =>
        ItemRequestParser.ParseAsync(new MemoryStream(Encoding.UTF8.GetBytes(json)), CancellationToken.None);

    [Fact]
    public async Task ParsesAValidBody() =>
        Assert.Equal(new ItemInput("Widget", "Blue", 1999, 5),
            await Parse("""{"name":"Widget","description":"Blue","price_cents":1999,"quantity":5}"""));

    [Theory]
    [InlineData("""{"name":"n","price_cents":1,"quantity":1}""")]
    [InlineData("""{"name":"n","description":null,"price_cents":1,"quantity":1}""")]
    public async Task DescriptionAbsentOrNullBecomesNull(string json) => Assert.Null((await Parse(json)).Description);

    [Fact]
    public async Task UnknownFieldsAreIgnored() =>
        Assert.Equal("n", (await Parse("""{"name":"n","price_cents":1,"quantity":1,"unknown":true,"id":9}""")).Name);

    [Fact]
    public async Task LargeIntegersWithinLongAreKept()
    {
        ItemInput input = await Parse("""{"name":"n","price_cents":9007199254740992,"quantity":2147483648}""");
        Assert.Equal(9_007_199_254_740_992L, input.PriceCents); // the domain rejects it, not the parser
        Assert.Equal(2_147_483_648L, input.Quantity);
    }

    [Theory]
    [InlineData("")]
    [InlineData("""{"name":""")]
    [InlineData("[]")]
    [InlineData("\"x\"")]
    [InlineData("null")]
    [InlineData("5")]
    [InlineData("""{"price_cents":1,"quantity":1}""")]
    [InlineData("""{"name":null,"price_cents":1,"quantity":1}""")]
    [InlineData("""{"name":5,"price_cents":1,"quantity":1}""")]
    [InlineData("""{"name":"n","description":5,"price_cents":1,"quantity":1}""")]
    [InlineData("""{"name":"n","quantity":1}""")]
    [InlineData("""{"name":"n","price_cents":"10","quantity":1}""")]
    [InlineData("""{"name":"n","price_cents":1.5,"quantity":1}""")]
    [InlineData("""{"name":"n","price_cents":null,"quantity":1}""")]
    [InlineData("""{"name":"n","price_cents":99999999999999999999,"quantity":1}""")]
    [InlineData("""{"name":"n","price_cents":1}""")]
    [InlineData("""{"name":"n","price_cents":1,"quantity":1.5}""")]
    [InlineData("""{"name":"n","price_cents":1,"quantity":"1"}""")]
    [InlineData("""{"name":"n","price_cents":true,"quantity":1}""")]
    public async Task RejectsInvalidBodies(string json) => await Assert.ThrowsAsync<ValidationException>(() => Parse(json));
}
