// Composition root: config → pool → repository → use cases → Fastify server.
import type { FastifyInstance } from 'fastify';

import { createUseCases } from './application/use-cases.ts';
import type { Config } from './infrastructure/config.ts';
import { createItemRepository, createPool, warmPool } from './infrastructure/postgres.ts';
import type { ManagedPool } from './infrastructure/postgres.ts';
import { buildServer } from './interface/server.ts';

export interface Deps {
  createPool(databaseUrl: string, size: number): ManagedPool;
}

export interface RunningServer {
  app: FastifyInstance;
  address: string;
  close(): Promise<void>;
}

/** Opens the (pre-warmed) pool, then starts listening; `close()` stops the server and ends the pool. */
export async function startServer(config: Config, deps: Deps = { createPool }): Promise<RunningServer> {
  const pool = deps.createPool(config.databaseUrl, config.workerPoolSize ?? config.poolSize);
  await warmPool(pool, config.workerPoolSize ?? config.poolSize);
  const app = buildServer(createUseCases(createItemRepository(pool)));
  const address = await app.listen({ port: config.port, host: '0.0.0.0' });
  return {
    app,
    address,
    async close() {
      await app.close();
      await pool.end();
    },
  };
}
