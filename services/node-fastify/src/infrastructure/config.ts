import { availableParallelism } from 'node:os';

/** Matches deploy/compose.dev.yaml. */
export const DEFAULT_DATABASE_URL = 'postgres://bench:bench@127.0.0.1:5432/bench';

export interface Config {
  databaseUrl: string;
  port: number;
  /** Total pool size of the service (DB_POOL_SIZE); split across workers by the cluster primary. */
  poolSize: number;
  /** node:cluster worker count (WORKERS); 1 = single process. Default: available parallelism (D-16). */
  workers: number;
  /** This worker's share of the pool, set by the primary (WORKER_DB_POOL_SIZE); null outside cluster workers. */
  workerPoolSize: number | null;
}

type Env = Record<string, string | undefined>;

/** An optional positive integer from the environment; empty counts as unset. */
function integer(env: Env, key: string, fallback: number | null, max: number): number | null {
  const raw = env[key];
  if (raw === undefined || raw === '') {
    return fallback;
  }
  const value = Number(raw);
  if (!/^[0-9]+$/.test(raw) || value < 1 || value > max) {
    throw new Error(`invalid ${key} ${JSON.stringify(raw)}`);
  }
  return value;
}

/** Reads the shared env contract (contract/README.md) plus the Node-specific WORKERS knob. */
export function loadConfig(env: Env, cpus: number = availableParallelism()): Config {
  const url = env['DATABASE_URL'];
  return {
    databaseUrl: url === undefined || url === '' ? DEFAULT_DATABASE_URL : url,
    port: integer(env, 'PORT', 8080, 65535) as number,
    poolSize: integer(env, 'DB_POOL_SIZE', 10, 10_000) as number,
    workers: integer(env, 'WORKERS', cpus, 1024) as number,
    workerPoolSize: integer(env, 'WORKER_DB_POOL_SIZE', null, 10_000),
  };
}
