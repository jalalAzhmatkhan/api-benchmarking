// Run configuration, all from environment variables (-e KEY=VALUE).
const int = (name, def) => {
  const v = parseInt(__ENV[name] || '', 10);
  return Number.isFinite(v) ? v : def;
};

export const BASE_URL = (__ENV.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
export const VUS = int('VUS', 10);
export const WARMUP_S = int('WARMUP_S', 60); // failures count in warm-up, latency thresholds do not
export const MEASURE_S = int('MEASURE_S', 120);
export const SEED = int('SEED', 1); // payload PRNG seed
export const SEED_ROWS = int('SEED_ROWS', 100000); // rows created by db/seed/seed.sql
export const THINK = (__ENV.THINK || 'T0').toUpperCase(); // T0 = none, T1 = uniform 0.5-1.5 s
export const SLO_MS = int('SLO_MS', 1000);
export const SUMMARY_PATH = __ENV.SUMMARY_PATH || '';
export const RESULT_PATH = __ENV.RESULT_PATH || '';
export const SCENARIO_NAME = __ENV.SCENARIO_NAME || 'unnamed';

if (THINK !== 'T0' && THINK !== 'T1') {
  throw new Error(`THINK must be T0 or T1, got "${THINK}"`);
}
