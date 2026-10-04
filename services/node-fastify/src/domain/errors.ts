/** A request violates a contract rule (maps to 400 VALIDATION_ERROR). */
export class ValidationError extends Error {}

/** The item does not exist (maps to 404 NOT_FOUND). */
export class NotFoundError extends Error {
  constructor() {
    super('item not found');
  }
}
