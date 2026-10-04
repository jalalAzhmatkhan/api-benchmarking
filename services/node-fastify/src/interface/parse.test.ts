import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { ValidationError } from '../domain/errors.ts';
import { parseId, parseInput, toResponse } from './parse.ts';

const body = (json: string) => Buffer.from(json, 'utf8');

describe('parseId', () => {
  test('digits only', () => {
    assert.equal(parseId('7'), 7);
    assert.equal(parseId('9007199254740991'), 9_007_199_254_740_991);
    assert.equal(parseId('0'), 0); // range rules belong to the domain
  });
  test('rejects signs, fractions, exponents and text', () => {
    for (const raw of ['abc', '-1', '+5', '1.5', '1e3', '', ' 5', '٣']) {
      assert.throws(() => parseId(raw), ValidationError, raw);
    }
  });
});

describe('parseInput', () => {
  test('parses a valid body', () => {
    assert.deepEqual(parseInput(body('{"name":"Widget","description":"Blue","price_cents":1999,"quantity":5}')), {
      name: 'Widget', description: 'Blue', priceCents: 1999, quantity: 5,
    });
  });

  test('description absent or null becomes null; unknown fields are ignored', () => {
    assert.equal(parseInput(body('{"name":"n","price_cents":1,"quantity":1}')).description, null);
    assert.equal(parseInput(body('{"name":"n","description":null,"price_cents":1,"quantity":1,"x":true,"id":9}')).description, null);
  });

  test('large integers are kept (the domain rejects them)', () => {
    assert.equal(parseInput(body('{"name":"n","price_cents":9007199254740992,"quantity":2147483648}')).priceCents, 9_007_199_254_740_992);
  });

  test('rejects invalid bodies', () => {
    const bad: unknown[] = [
      undefined,
      'a string, not a buffer',
      body(''),
      body('{"name":'),
      body('[]'),
      body('"x"'),
      body('null'),
      body('5'),
      body('{"price_cents":1,"quantity":1}'),
      body('{"name":null,"price_cents":1,"quantity":1}'),
      body('{"name":5,"price_cents":1,"quantity":1}'),
      body('{"name":"n","description":5,"price_cents":1,"quantity":1}'),
      body('{"name":"n","quantity":1}'),
      body('{"name":"n","price_cents":"10","quantity":1}'),
      body('{"name":"n","price_cents":1.5,"quantity":1}'),
      body('{"name":"n","price_cents":null,"quantity":1}'),
      body('{"name":"n","price_cents":1}'),
      body('{"name":"n","price_cents":1,"quantity":1.5}'),
      body('{"name":"n","price_cents":1,"quantity":"1"}'),
      body('{"name":"n","price_cents":true,"quantity":1}'),
    ];
    for (const input of bad) assert.throws(() => parseInput(input), ValidationError, String(input));
  });
});

describe('toResponse', () => {
  test('snake_case names, ISO timestamps and an explicit null description', () => {
    const at = new Date('2026-10-03T10:00:00.123Z');
    assert.deepEqual(toResponse({ id: 1, name: 'n', description: null, priceCents: 2, quantity: 3, createdAt: at, updatedAt: at }), {
      id: 1, name: 'n', description: null, price_cents: 2, quantity: 3,
      created_at: '2026-10-03T10:00:00.123Z', updated_at: '2026-10-03T10:00:00.123Z',
    });
  });
});
