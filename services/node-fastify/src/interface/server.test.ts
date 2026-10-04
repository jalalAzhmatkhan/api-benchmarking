import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import type { FastifyInstance } from 'fastify';

import { createUseCases } from '../application/use-cases.ts';
import { NotFoundError } from '../domain/errors.ts';
import type { Item, ItemRepository } from '../domain/item.ts';
import { buildServer } from './server.ts';

const VALID = '{"name":"Widget","description":"Blue","price_cents":1999,"quantity":5}';
const TS = new Date('2026-10-03T10:00:00Z');
const item = (id: number, description: string | null): Item => ({ id, name: 'Widget', description, priceCents: 1999, quantity: 5, createdAt: TS, updatedAt: TS });

/** Canned repository: every call rejects with `failure` when given. */
function app(failure?: Error): FastifyInstance {
  const fail = async () => {
    if (failure) throw failure;
  };
  const repository: ItemRepository = {
    async get(id) { await fail(); return item(id, null); },
    async create() { await fail(); return item(100_001, 'Blue'); },
    async replace(id) { await fail(); return item(id, 'Red'); },
    async delete() { await fail(); },
  };
  return buildServer(createUseCases(repository));
}

async function send(server: FastifyInstance, method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH', url: string, payload?: string | Buffer) {
  return server.inject({ method, url, payload, headers: payload === undefined ? {} : { 'content-type': 'application/json' } });
}

const errorCode = (body: string): string => {
  const parsed = JSON.parse(body) as { error: { code: string; message: string } };
  assert.ok(parsed.error.message.length > 0, body);
  return parsed.error.code;
};

describe('HTTP layer', () => {
  test('GET returns the item with an explicit null description and no caching headers', async () => {
    const server = app();
    const res = await send(server, 'GET', '/items/7');
    assert.equal(res.statusCode, 200);
    assert.match(String(res.headers['content-type']), /^application\/json/);
    assert.deepEqual(res.json(), {
      id: 7, name: 'Widget', description: null, price_cents: 1999, quantity: 5,
      created_at: '2026-10-03T10:00:00.000Z', updated_at: '2026-10-03T10:00:00.000Z',
    });
    for (const header of ['etag', 'cache-control', 'last-modified', 'content-encoding']) {
      assert.equal(res.headers[header], undefined, header);
    }
    await server.close();
  });

  test('invalid ids are 400', async () => {
    const server = app();
    for (const id of ['abc', '0', '-1', '1.5', '1e3', '+5', '9007199254740992', '99999999999999999999']) {
      for (const method of ['GET', 'DELETE', 'PUT'] as const) {
        const res = await send(server, method, `/items/${id}`, method === 'PUT' ? VALID : undefined);
        assert.equal(res.statusCode, 400, `${method} ${id}`);
        assert.equal(errorCode(res.body), 'VALIDATION_ERROR');
      }
    }
    await server.close();
  });

  test('POST returns 201 with a Location header', async () => {
    const server = app();
    const res = await send(server, 'POST', '/items', VALID);
    assert.equal(res.statusCode, 201);
    assert.equal(res.headers['location'], '/items/100001');
    assert.equal(res.json<{ id: number; description: string }>().description, 'Blue');
    await server.close();
  });

  test('invalid bodies are 400 on POST and PUT, whatever the content type', async () => {
    const server = app();
    for (const body of ['{"name":', '[]', '{"price_cents":1,"quantity":1}', '{"name":"","price_cents":1,"quantity":1}', '{"name":"n","price_cents":-1,"quantity":1}', '{"name":"n","price_cents":1,"quantity":2147483648}']) {
      for (const [method, url] of [['POST', '/items'], ['PUT', '/items/5']] as const) {
        const res = await send(server, method, url, body);
        assert.equal(res.statusCode, 400, `${method} ${body}`);
        assert.equal(errorCode(res.body), 'VALIDATION_ERROR');
      }
    }
    // no body at all, and a non-JSON content type
    assert.equal((await send(server, 'POST', '/items')).statusCode, 400);
    assert.equal((await send(server, 'PUT', '/items/5')).statusCode, 400);
    const text = await server.inject({ method: 'POST', url: '/items', payload: 'plain', headers: { 'content-type': 'text/plain' } });
    assert.equal(text.statusCode, 400);
    await server.close();
  });

  test('PUT replaces and DELETE returns 204 with an empty body', async () => {
    const server = app();
    const put = await send(server, 'PUT', '/items/5', VALID);
    assert.equal(put.statusCode, 200);
    assert.equal(put.json<{ id: number; description: string }>().description, 'Red');
    const del = await send(server, 'DELETE', '/items/5');
    assert.deepEqual([del.statusCode, del.body], [204, '']);
    await server.close();
  });

  test('error mapping never leaks internals', async () => {
    const statusError = (statusCode: number) => Object.assign(new Error('secret connection string'), { statusCode });
    const cases: [Error, number, string][] = [
      [new NotFoundError(), 404, 'NOT_FOUND'],
      [new Error('secret connection string'), 500, 'INTERNAL_ERROR'],
      [statusError(503), 500, 'INTERNAL_ERROR'],
      [statusError(200), 500, 'INTERNAL_ERROR'],
    ];
    for (const [failure, status, code] of cases) {
      const server = app(failure);
      for (const [method, url, body] of [['GET', '/items/1'], ['POST', '/items', VALID], ['PUT', '/items/1', VALID], ['DELETE', '/items/1']] as const) {
        const res = await send(server, method, url, body);
        assert.equal(res.statusCode, status, `${method} ${url} ${code}`);
        assert.equal(errorCode(res.body), code);
        assert.ok(!res.body.includes('secret'), res.body);
      }
      await server.close();
    }
  });

  test('framework client errors keep their status (413 body too large)', async () => {
    const server = app();
    const res = await send(server, 'POST', '/items', Buffer.alloc(1_048_577, 'a'));
    assert.equal(res.statusCode, 413);
    assert.equal(errorCode(res.body), 'VALIDATION_ERROR');
    await server.close();
  });

  test('only the contract routes exist', async () => {
    const server = app();
    assert.equal((await send(server, 'GET', '/items')).statusCode, 404);
    assert.equal((await send(server, 'PATCH', '/items/1')).statusCode, 404);
    assert.equal((await send(server, 'GET', '/health')).statusCode, 404);
    await server.close();
  });
});
