import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { NotFoundError, ValidationError } from '../domain/errors.ts';
import type { Item, ItemInput, ItemRepository } from '../domain/item.ts';
import { createUseCases } from './use-cases.ts';

const NOW = new Date('2026-10-03T10:00:00Z');
const item = (id: number): Item => ({ id, name: 'n', description: null, priceCents: 1, quantity: 1, createdAt: NOW, updatedAt: NOW });
const ok: ItemInput = { name: 'n', description: null, priceCents: 1, quantity: 1 };
const bad: ItemInput = { ...ok, name: '' };

/** Records calls; with `missing` every call rejects with NotFoundError. */
function fakeRepository(missing: boolean): ItemRepository & { calls: string[] } {
  const calls: string[] = [];
  const record = async (call: string): Promise<void> => {
    calls.push(call);
    if (missing) throw new NotFoundError();
  };
  return {
    calls,
    async get(id) {
      await record('get');
      return item(id);
    },
    async create() {
      await record('create');
      return item(100_001);
    },
    async replace(id) {
      await record('replace');
      return item(id);
    },
    async delete() {
      await record('delete');
    },
  };
}

describe('use cases', () => {
  test('getItem', async () => {
    const repo = fakeRepository(false);
    assert.equal((await createUseCases(repo).getItem(7)).id, 7);
    await assert.rejects(createUseCases(repo).getItem(0), ValidationError);
    assert.deepEqual(repo.calls, ['get'], 'an invalid id must not reach the repository');
    await assert.rejects(createUseCases(fakeRepository(true)).getItem(1), NotFoundError);
  });

  test('createItem', async () => {
    const repo = fakeRepository(false);
    assert.equal((await createUseCases(repo).createItem(ok)).id, 100_001);
    await assert.rejects(createUseCases(repo).createItem(bad), ValidationError);
    assert.deepEqual(repo.calls, ['create']);
  });

  test('replaceItem', async () => {
    const repo = fakeRepository(false);
    assert.equal((await createUseCases(repo).replaceItem(5, ok)).id, 5);
    await assert.rejects(createUseCases(repo).replaceItem(-1, ok), ValidationError);
    await assert.rejects(createUseCases(repo).replaceItem(1, bad), ValidationError);
    assert.deepEqual(repo.calls, ['replace']);
    await assert.rejects(createUseCases(fakeRepository(true)).replaceItem(1, ok), NotFoundError);
  });

  test('deleteItem', async () => {
    const repo = fakeRepository(false);
    await createUseCases(repo).deleteItem(9);
    await assert.rejects(createUseCases(repo).deleteItem(0), ValidationError);
    assert.deepEqual(repo.calls, ['delete']);
    await assert.rejects(createUseCases(fakeRepository(true)).deleteItem(1), NotFoundError);
  });
});
