using System.Globalization;
using Items.Application;
using Items.Domain;

namespace Items.Api;

/// <summary>The four endpoints of the contract. No SQL and no business rules here.</summary>
public static class ItemEndpoints
{
    public static IEndpointRouteBuilder MapItemEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapPost("/items", CreateAsync);
        app.MapGet("/items/{id}", GetAsync);
        app.MapPut("/items/{id}", ReplaceAsync);
        app.MapDelete("/items/{id}", DeleteAsync);
        return app;
    }

    /// <summary>Decimal digits only (no sign, exponent or fraction) that fit a long; range rules are the domain's.</summary>
    private static long ParseId(string raw) =>
        long.TryParse(raw, NumberStyles.None, CultureInfo.InvariantCulture, out long id)
            ? id
            : throw new ValidationException("invalid id");

    private static IResult Error(int status, string code, string message) =>
        Results.Json(new ErrorBody(new ErrorDetail(code, message)), statusCode: status);

    /// <summary>Maps domain errors to the contract's error body. Internal details are never exposed.</summary>
    private static async Task<IResult> Run(Func<Task<IResult>> action)
    {
        try
        {
            return await action();
        }
        catch (ValidationException e)
        {
            return Error(StatusCodes.Status400BadRequest, "VALIDATION_ERROR", e.Message);
        }
        catch (NotFoundException e)
        {
            return Error(StatusCodes.Status404NotFound, "NOT_FOUND", e.Message);
        }
        catch (Exception)
        {
            return Error(StatusCodes.Status500InternalServerError, "INTERNAL_ERROR", "internal error");
        }
    }

    private static Task<IResult> GetAsync(string id, GetItem useCase, CancellationToken ct) =>
        Run(async () => Results.Json(ItemDto.From(await useCase.ExecuteAsync(ParseId(id), ct))));

    private static Task<IResult> CreateAsync(HttpRequest request, CreateItem useCase, CancellationToken ct) =>
        Run(async () =>
        {
            Item item = await useCase.ExecuteAsync(await ItemRequestParser.ParseAsync(request.Body, ct), ct);
            return Results.Created($"/items/{item.Id}", ItemDto.From(item));
        });

    private static Task<IResult> ReplaceAsync(string id, HttpRequest request, ReplaceItem useCase, CancellationToken ct) =>
        Run(async () =>
        {
            long itemId = ParseId(id);
            Item item = await useCase.ExecuteAsync(itemId, await ItemRequestParser.ParseAsync(request.Body, ct), ct);
            return Results.Json(ItemDto.From(item));
        });

    private static Task<IResult> DeleteAsync(string id, DeleteItem useCase, CancellationToken ct) =>
        Run(async () =>
        {
            await useCase.ExecuteAsync(ParseId(id), ct);
            return Results.NoContent();
        });
}
