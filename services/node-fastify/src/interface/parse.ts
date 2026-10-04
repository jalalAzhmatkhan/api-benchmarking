import { ValidationError } from '../domain/errors.ts';
import type { Item, ItemInput } from '../domain/item.ts';

const malformed = () => new ValidationError('malformed JSON body');

/** Decimal digits only (no sign, exponent or fraction); range rules are the domain's. */
export function parseId(raw: string): number {
  if (!/^[0-9]+$/.test(raw)) {
    throw new ValidationError('invalid id');
  }
  return Number(raw);
}

/**
 * Parses the raw request body strictly: syntax errors, non-objects, wrong JSON types and missing
 * required fields are validation errors; unknown fields are ignored. JSON numbers that are
 * mathematically integers (1.0, 1e3) are accepted as integers (JSON.parse cannot tell them apart).
 */
export function parseInput(body: unknown): ItemInput {
  if (!Buffer.isBuffer(body) || body.length === 0) {
    throw malformed();
  }
  let json: unknown;
  try {
    json = JSON.parse(body.toString('utf8'));
  } catch {
    throw malformed();
  }
  if (typeof json !== 'object' || json === null || Array.isArray(json)) {
    throw new ValidationError('body must be a JSON object');
  }
  const fields = json as Record<string, unknown>;
  const { name, description } = fields;
  if (typeof name !== 'string') {
    throw new ValidationError('name is required and must be a string');
  }
  if (description !== undefined && description !== null && typeof description !== 'string') {
    throw new ValidationError('description must be a string or null');
  }
  return {
    name,
    description: description ?? null,
    priceCents: integer(fields, 'price_cents'),
    quantity: integer(fields, 'quantity'),
  };
}

function integer(fields: Record<string, unknown>, key: string): number {
  const value = fields[key];
  if (typeof value !== 'number' || !Number.isInteger(value)) {
    throw new ValidationError(`${key} is required and must be an integer`);
  }
  return value;
}

/** Wire format of an item (snake_case names per the contract). */
export function toResponse(item: Item) {
  return {
    id: item.id,
    name: item.name,
    description: item.description,
    price_cents: item.priceCents,
    quantity: item.quantity,
    created_at: item.createdAt.toISOString(),
    updated_at: item.updatedAt.toISOString(),
  };
}
