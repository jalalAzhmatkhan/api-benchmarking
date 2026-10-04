// node:cluster supervision (decision D-16: one worker per vCPU). The primary only forks, splits the
// connection pool between workers and supervises; each worker runs a complete server.
import type { Config } from './infrastructure/config.ts';

/** Splits the total pool across workers (every worker gets at least one connection). */
export function splitPool(total: number, workers: number): number[] {
  const base = Math.floor(total / workers);
  const remainder = total % workers;
  return Array.from({ length: workers }, (_, index) => Math.max(1, base + (index < remainder ? 1 : 0)));
}

export interface WorkerLike {
  kill(signal?: string): void;
}

export interface ClusterLike {
  fork(env: Record<string, string>): WorkerLike;
  on(event: 'exit', listener: (worker: WorkerLike) => void): unknown;
}

export interface PrimaryHooks {
  exit(code: number): void;
  log(message: string): void;
  onSignal(signal: 'SIGTERM' | 'SIGINT', listener: () => void): void;
}

/**
 * Forks `config.workers` workers. If a worker dies unexpectedly the run is invalid, so the primary
 * stops the others and exits non-zero (no silent restarts). On SIGTERM/SIGINT it stops the workers
 * and exits 0 once all of them are gone.
 */
export function runPrimary(cluster: ClusterLike, config: Config, hooks: PrimaryHooks): WorkerLike[] {
  const shares = splitPool(config.poolSize, config.workers);
  const workers = shares.map((share) => cluster.fork({ WORKER_DB_POOL_SIZE: String(share) }));
  hooks.log(`primary: ${workers.length} workers, pool split ${shares.join('+')}`);

  let shuttingDown = false;
  let exited = 0;
  const stopAll = () => workers.forEach((worker) => worker.kill('SIGTERM'));

  cluster.on('exit', () => {
    exited += 1;
    if (shuttingDown) {
      if (exited === workers.length) hooks.exit(0);
      return;
    }
    hooks.log('primary: a worker exited unexpectedly, stopping all workers');
    shuttingDown = true;
    stopAll();
    hooks.exit(1);
  });
  for (const signal of ['SIGTERM', 'SIGINT'] as const) {
    hooks.onSignal(signal, () => {
      shuttingDown = true;
      stopAll();
    });
  }
  return workers;
}
