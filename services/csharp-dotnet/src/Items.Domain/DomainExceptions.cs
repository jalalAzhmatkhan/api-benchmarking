namespace Items.Domain;

/// <summary>A request violates a contract rule (maps to 400 VALIDATION_ERROR).</summary>
public sealed class ValidationException(string message) : Exception(message);

/// <summary>The item does not exist (maps to 404 NOT_FOUND).</summary>
public sealed class NotFoundException() : Exception("item not found");
