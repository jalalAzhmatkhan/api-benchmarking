import assert from 'node:assert/strict';
import type { AddressInfo } from 'node:net';
import { describe, test } from 'node:test';

import { startServer } from './app.ts';
import type { Config } from './infrastructure/config.ts';
import type { ManagedPool } from './infrastructure/postgres.ts';

const TS = new Date('2026-10-03T10:00:00Z');

/** Counts warm-up queries and answers item lookups from a canned row. */
function fakePool() {
  const state = { warmups: 0, ended: false };
  const pool: ManagedPool = {
    async query({ text }) {
      if (text.includes('pg_sleep')) {
        state.warmups += 1;
        return { rows: [], rowCount: 0 };
      }
      return { rows: [{ id: 1, name: 'n', description: null, price_cents: 1, quantity: 1, created_at: TS, updated_at: TS }], rowCount: 1 };
    },
    async end() {
      state.ended = true;
    },
  };
  return { pool, state };
}

const config = (poolSize: number, workerPoolSize: number | null): Config => ({
  databaseUrl: 'postgres://unused', port: 0, poolSize, workers: 1, workerPoolSize,
});

describe('startServer', () => {
  test('pre-warms the whole pool, serves requests and shuts down cleanly', async () => {
    const { pool, state } = fakePool();
    let requested = { url: '', size: 0 };
    const server = await startServer(config(3, null), {
      createPool: (url, size) => {
        requested = { url, size };
        return pool;
      },
    });
    assert.deepEqual(requested, { url: 'postgres://unused', size: 3 });
    assert.equal(state.warmups, 3);

    const port = (server.app.server.address() as AddressInfo).port;
    const res = await fetch(`http://127.0.0.1:${port}/items/1`);
    assert.equal(res.status, 200);
    assert.equal(((await res.json()) as { name: string }).name, 'n');

    await server.close();
    assert.equal(state.ended, true);
  });

  test('a cluster worker uses its own share of the pool', async () => {
    const { pool, state } = fakePool();
    let size = 0;
    const server = await startServer(config(10, 5), { createPool: (_url, s) => ((size = s), pool) });
    assert.equal(size, 5);
    assert.equal(state.warmups, 5);
    await server.close();
  });

  test('uses the real pool factory by default', async () => {
    // Port 0 plus an unreachable database: the default pool factory is exercised and warm-up fails.
    await assert.rejects(startServer({ databaseUrl: 'postgres://bench:bench@127.0.0.1:1/bench', port: 0, poolSize: 1, workers: 1, workerPoolSize: null }));
  });
});
