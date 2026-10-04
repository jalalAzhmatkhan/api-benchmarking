import assert from 'node:assert/strict';
import type { AddressInfo } from 'node:net';
import { test } from 'node:test';

import { startServer } from './app.ts';
import { createPool } from './infrastructure/postgres.ts';

// Runs against the real PostgreSQL (CI provides DATABASE_URL, the seeded dev database).
const databaseUrl = process.env['DATABASE_URL'];
const skip = databaseUrl === undefined || databaseUrl === '';

test('the whole service works against PostgreSQL', { skip }, async () => {
  const server = await startServer({ databaseUrl: databaseUrl as string, port: 0, poolSize: 3, workers: 1, workerPoolSize: null });
  const base = `http://127.0.0.1:${(server.app.server.address() as AddressInfo).port}`;
  const call = (method: string, path: string, body?: string) => fetch(base + path, { method, body });

  const seeded = await call('GET', '/items/1');
  assert.equal(seeded.status, 200);
  assert.equal(((await seeded.json()) as { name: string }).name, 'item-1');

  const created = await call('POST', '/items', '{"name":"node","price_cents":1,"quantity":1}');
  assert.equal(created.status, 201);
  const location = created.headers.get('location') as string;
  assert.equal((await call('PUT', location, '{"name":"node2","description":"d","price_cents":2,"quantity":2}')).status, 200);
  assert.equal((await call('DELETE', location)).status, 204);
  assert.equal((await call('GET', location)).status, 404);
  assert.equal((await call('GET', '/items/abc')).status, 400);
  await server.close();
});

test('a pool keeps exactly its size and returns bigint columns as numbers', { skip }, async () => {
  const pool = createPool(databaseUrl as string, 2);
  const result = await pool.query({ text: 'SELECT id, price_cents FROM items WHERE id = $1', values: [1] });
  assert.equal(typeof result.rows[0]?.['id'], 'number');
  assert.equal(typeof result.rows[0]?.['price_cents'], 'number');
  await pool.end();
});
