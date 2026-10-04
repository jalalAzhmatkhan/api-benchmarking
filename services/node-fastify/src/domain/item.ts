import { ValidationError } from './errors.ts';

// Limits from the API contract (Documentation/specs/api-contract.md).
export const MAX_ID = 9_007_199_254_740_991;
export const MAX_PRICE_CENTS = 9_007_199_254_740_991;
export const MAX_QUANTITY = 2_147_483_647;
export const MAX_NAME_LENGTH = 100;
export const MAX_DESCRIPTION_LENGTH = 1000;

export interface Item {
  id: number;
  name: string;
  description: string | null;
  priceCents: number;
  quantity: number;
  createdAt: Date;
  updatedAt: Date;
}

export interface ItemInput {
  name: string;
  description: string | null;
  priceCents: number;
  quantity: number;
}

/** Persistence port, implemented by the infrastructure layer. Missing items reject with NotFoundError. */
export interface ItemRepository {
  get(id: number): Promise<Item>;
  create(input: ItemInput): Promise<Item>;
  replace(id: number, input: ItemInput): Promise<Item>;
  delete(id: number): Promise<void>;
}

/** Lengths are counted in Unicode code points, not UTF-16 units. */
function codePoints(text: string): number {
  return Array.from(text).length;
}

export function validateId(id: number): void {
  if (!Number.isInteger(id) || id < 1 || id > MAX_ID) {
    throw new ValidationError('invalid id');
  }
}

/** Applies the contract's field rules. */
export function validateInput(input: ItemInput): void {
  const nameLength = codePoints(input.name);
  if (nameLength < 1 || nameLength > MAX_NAME_LENGTH) {
    throw new ValidationError('name must be 1-100 characters');
  }
  if (input.description !== null && codePoints(input.description) > MAX_DESCRIPTION_LENGTH) {
    throw new ValidationError('description must be at most 1000 characters');
  }
  if (!Number.isInteger(input.priceCents) || input.priceCents < 0 || input.priceCents > MAX_PRICE_CENTS) {
    throw new ValidationError('price_cents must be an integer in 0..9007199254740991');
  }
  if (!Number.isInteger(input.quantity) || input.quantity < 0 || input.quantity > MAX_QUANTITY) {
    throw new ValidationError('quantity must be an integer in 0..2147483647');
  }
}
