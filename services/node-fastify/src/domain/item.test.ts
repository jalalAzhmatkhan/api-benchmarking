import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { NotFoundError, ValidationError } from './errors.ts';
import { MAX_ID, MAX_PRICE_CENTS, MAX_QUANTITY, validateId, validateInput } from './item.ts';
import type { ItemInput } from './item.ts';

const valid: ItemInput = { name: 'Widget', description: 'Blue', priceCents: 1999, quantity: 5 };
const invalid = (input: ItemInput) => assert.throws(() => validateInput(input), ValidationError);
const ok = (input: ItemInput) => assert.doesNotThrow(() => validateInput(input));

describe('validateId', () => {
  test('accepts 1..MAX_ID', () => {
    for (const id of [1, 100_001, MAX_ID]) assert.doesNotThrow(() => validateId(id));
  });
  test('rejects everything else', () => {
    for (const id of [0, -1, MAX_ID + 1, 1.5, Number.NaN, Number.POSITIVE_INFINITY]) {
      assert.throws(() => validateId(id), ValidationError);
    }
  });
});

describe('validateInput', () => {
  test('valid input and description variants', () => {
    ok(valid);
    for (const description of [null, '', 'd'.repeat(1000), 'é'.repeat(1000), '😀'.repeat(1000)]) {
      ok({ ...valid, description });
    }
    invalid({ ...valid, description: 'd'.repeat(1001) });
    invalid({ ...valid, description: '😀'.repeat(1001) });
  });

  test('name length counts code points', () => {
    for (const name of ['a', 'a'.repeat(100), 'é'.repeat(100), '😀'.repeat(100)]) ok({ ...valid, name });
    for (const name of ['', 'a'.repeat(101), '😀'.repeat(101)]) invalid({ ...valid, name });
  });

  test('price bounds and integrality', () => {
    for (const priceCents of [0, MAX_PRICE_CENTS]) ok({ ...valid, priceCents });
    for (const priceCents of [-1, MAX_PRICE_CENTS + 1, 1.5, 1e20]) invalid({ ...valid, priceCents });
  });

  test('quantity bounds and integrality', () => {
    for (const quantity of [0, MAX_QUANTITY]) ok({ ...valid, quantity });
    for (const quantity of [-1, MAX_QUANTITY + 1, 1.5]) invalid({ ...valid, quantity });
  });
});

describe('errors', () => {
  test('NotFoundError has a fixed message', () => {
    assert.equal(new NotFoundError().message, 'item not found');
    assert.ok(new NotFoundError() instanceof Error);
  });
});
