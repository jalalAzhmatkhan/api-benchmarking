import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { runPrimary, splitPool } from './cluster.ts';
import type { ClusterLike, PrimaryHooks, WorkerLike } from './cluster.ts';
import type { Config } from './infrastructure/config.ts';

const config = (poolSize: number, workers: number): Config => ({
  databaseUrl: 'x', port: 0, poolSize, workers, workerPoolSize: null,
});

function harness() {
  const forks: Record<string, string>[] = [];
  const killed: string[] = [];
  const exits: number[] = [];
  const logs: string[] = [];
  const signals = new Map<string, () => void>();
  let onExit: (worker: WorkerLike) => void = () => {};
  const cluster: ClusterLike = {
    fork(env) {
      forks.push(env);
      return { kill: (signal) => void killed.push(`${forks.length}:${signal}`) };
    },
    on(_event, listener) {
      onExit = listener;
    },
  };
  const hooks: PrimaryHooks = {
    exit: (code) => void exits.push(code),
    log: (message) => void logs.push(message),
    onSignal: (signal, listener) => void signals.set(signal, listener),
  };
  return { cluster, hooks, forks, killed, exits, logs, signals, worker: () => onExit({ kill() {} }) };
}

describe('splitPool', () => {
  test('splits evenly, spreads the remainder, and never starves a worker', () => {
    assert.deepEqual(splitPool(10, 2), [5, 5]);
    assert.deepEqual(splitPool(10, 4), [3, 3, 2, 2]);
    assert.deepEqual(splitPool(10, 1), [10]);
    assert.deepEqual(splitPool(2, 4), [1, 1, 1, 1]);
    assert.equal(splitPool(10, 3).reduce((a, b) => a + b, 0), 10);
  });
});

describe('runPrimary', () => {
  test('forks one worker per slot with its share of the pool', () => {
    const h = harness();
    const workers = runPrimary(h.cluster, config(10, 2), h.hooks);
    assert.equal(workers.length, 2);
    assert.deepEqual(h.forks, [{ WORKER_DB_POOL_SIZE: '5' }, { WORKER_DB_POOL_SIZE: '5' }]);
    assert.match(h.logs[0] ?? '', /2 workers, pool split 5\+5/);
  });

  test('an unexpected worker exit stops everything and exits non-zero', () => {
    const h = harness();
    runPrimary(h.cluster, config(10, 2), h.hooks);
    h.worker();
    assert.deepEqual(h.exits, [1]);
    assert.equal(h.killed.length, 2);
    assert.ok(h.logs.some((l) => l.includes('exited unexpectedly')));
  });

  test('a signal stops the workers and exits 0 once all are gone', () => {
    const h = harness();
    runPrimary(h.cluster, config(10, 2), h.hooks);
    assert.deepEqual([...h.signals.keys()].sort(), ['SIGINT', 'SIGTERM']);
    h.signals.get('SIGTERM')?.();
    assert.equal(h.killed.length, 2);
    h.worker();
    assert.deepEqual(h.exits, [], 'not yet: one worker is still running');
    h.worker();
    assert.deepEqual(h.exits, [0]);
  });
});
