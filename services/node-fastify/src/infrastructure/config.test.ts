import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { DEFAULT_DATABASE_URL, loadConfig } from './config.ts';

describe('loadConfig', () => {
  test('defaults (workers follow the CPU count)', () => {
    assert.deepEqual(loadConfig({}, 2), {
      databaseUrl: DEFAULT_DATABASE_URL,
      port: 8080,
      poolSize: 10,
      workers: 2,
      workerPoolSize: null,
    });
    assert.equal(loadConfig({}, 4).workers, 4);
  });

  test('uses the real CPU count when none is given', () => {
    assert.ok(loadConfig({}).workers >= 1);
  });

  test('empty values behave like unset ones', () => {
    const c = loadConfig({ DATABASE_URL: '', PORT: '', DB_POOL_SIZE: '', WORKERS: '', WORKER_DB_POOL_SIZE: '' }, 2);
    assert.deepEqual([c.databaseUrl, c.port, c.poolSize, c.workers, c.workerPoolSize], [DEFAULT_DATABASE_URL, 8080, 10, 2, null]);
  });

  test('overrides', () => {
    const c = loadConfig({ DATABASE_URL: 'postgres://x', PORT: '9000', DB_POOL_SIZE: '20', WORKERS: '1', WORKER_DB_POOL_SIZE: '5' }, 2);
    assert.deepEqual(c, { databaseUrl: 'postgres://x', port: 9000, poolSize: 20, workers: 1, workerPoolSize: 5 });
  });

  test('rejects invalid values', () => {
    const bad: Record<string, string>[] = [
      { PORT: 'abc' },
      { PORT: '0' },
      { PORT: '70000' },
      { PORT: '-1' },
      { PORT: '1.5' },
      { DB_POOL_SIZE: 'ten' },
      { DB_POOL_SIZE: '0' },
      { WORKERS: '0' },
      { WORKER_DB_POOL_SIZE: 'x' },
    ];
    for (const env of bad) assert.throws(() => loadConfig(env, 2), /invalid/, JSON.stringify(env));
  });
});
