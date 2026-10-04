import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { NotFoundError } from '../domain/errors.ts';
import {
  DELETE_SQL,
  INSERT_SQL,
  SELECT_SQL,
  UPDATE_SQL,
  createItemRepository,
  createPool,
  warmPool,
} from './postgres.ts';
import type { Queryable } from './postgres.ts';

const TS = new Date('2026-10-03T10:00:00Z');
const row = (id: number) => ({
  id,
  name: 'Widget',
  description: null,
  price_cents: 1999,
  quantity: 5,
  created_at: TS,
  updated_at: TS,
});

/** Records every query and answers with the supplied rows / rowCount. */
function fakeDb(rows: Record<string, unknown>[], rowCount: number | null) {
  const calls: { text: string; values: unknown[] }[] = [];
  const db: Queryable = {
    async query(config) {
      calls.push(config);
      return { rows, rowCount };
    },
  };
  return { db, calls };
}

describe('item repository (SQL and mapping)', () => {
  test('get maps the row and passes the id', async () => {
    const { db, calls } = fakeDb([row(7)], 1);
    const item = await createItemRepository(db).get(7);
    assert.deepEqual(item, {
      id: 7, name: 'Widget', description: null, priceCents: 1999, quantity: 5, createdAt: TS, updatedAt: TS,
    });
    assert.deepEqual(calls, [{ text: SELECT_SQL, values: [7] }]);
  });

  test('create and replace bind the canonical parameters in order', async () => {
    const input = { name: 'n', description: 'd', priceCents: 5, quantity: 2 };
    const created = fakeDb([row(100_001)], 1);
    assert.equal((await createItemRepository(created.db).create(input)).id, 100_001);
    assert.deepEqual(created.calls, [{ text: INSERT_SQL, values: ['n', 'd', 5, 2] }]);

    const replaced = fakeDb([row(9)], 1);
    assert.equal((await createItemRepository(replaced.db).replace(9, input)).id, 9);
    assert.deepEqual(replaced.calls, [{ text: UPDATE_SQL, values: [9, 'n', 'd', 5, 2] }]);
  });

  test('missing rows are NotFoundError', async () => {
    const input = { name: 'n', description: null, priceCents: 1, quantity: 1 };
    const repo = createItemRepository(fakeDb([], 0).db);
    await assert.rejects(repo.get(1), NotFoundError);
    await assert.rejects(repo.replace(1, input), NotFoundError);
    await assert.rejects(repo.delete(1), NotFoundError);
    await assert.rejects(createItemRepository(fakeDb([], null).db).delete(1), NotFoundError);
  });

  test('delete succeeds when a row was removed', async () => {
    const { db, calls } = fakeDb([], 1);
    await createItemRepository(db).delete(3);
    assert.deepEqual(calls, [{ text: DELETE_SQL, values: [3] }]);
  });

  test('driver errors propagate unchanged', async () => {
    const boom = new Error('db down');
    const db: Queryable = { query: () => Promise.reject(boom) };
    await assert.rejects(createItemRepository(db).get(1), boom);
  });
});

describe('warmPool', () => {
  test('runs the warm-up queries concurrently (one connection each)', async () => {
    let inFlight = 0;
    let peak = 0;
    const db: Queryable = {
      async query() {
        inFlight += 1;
        peak = Math.max(peak, inFlight);
        await new Promise((resolve) => setTimeout(resolve, 10));
        inFlight -= 1;
        return { rows: [], rowCount: 0 };
      },
    };
    await warmPool(db, 4);
    assert.equal(peak, 4);
  });

  test('a failing query fails the warm-up', async () => {
    await assert.rejects(warmPool({ query: () => Promise.reject(new Error('down')) }, 2), /down/);
  });
});

describe('createPool', () => {
  test('returns a managed pool that fails fast when the database is unreachable', async () => {
    const pool = createPool('postgres://bench:bench@127.0.0.1:1/bench', 2);
    await assert.rejects(pool.query({ text: 'SELECT 1', values: [] }));
    await pool.end();
  });
});
