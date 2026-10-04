// Bare process entrypoint (excluded from coverage, see COVERAGE_EXCLUSIONS.md): decides between a
// single process and a cluster primary, and wires process signals. All logic lives elsewhere.
import cluster from 'node:cluster';

import { startServer } from './app.ts';
import { runPrimary } from './cluster.ts';
import type { ClusterLike } from './cluster.ts';
import { loadConfig } from './infrastructure/config.ts';

const config = loadConfig(process.env);

if (config.workers > 1 && cluster.isPrimary) {
  runPrimary(cluster as unknown as ClusterLike, config, {
    exit: (code) => process.exit(code),
    log: (message) => console.error(message),
    onSignal: (signal, listener) => process.once(signal, listener),
  });
} else {
  const server = await startServer(config);
  for (const signal of ['SIGTERM', 'SIGINT'] as const) {
    process.once(signal, () => void server.close().then(() => process.exit(0)));
  }
}
