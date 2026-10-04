// Shared k6 options (single VU pool, phase tag, thresholds) and the machine-readable summary.
import { MEASURE_S, RESULT_PATH, SCENARIO_NAME, SLO_MS, SUMMARY_PATH, THINK, VUS, WARMUP_S } from './config.js';

const STEPS = ['1', '2', '3', '4', '5', '6', '7'];
const ENDPOINTS = ['get', 'post', 'put', 'delete'];
const FAILURE_TYPES = ['status', 'transport', 'timeout', 'check'];

// System tags kept small on purpose: no `url` (one series per id would explode memory).
const SYSTEM_TAGS = ['status', 'method', 'name', 'scenario', 'error', 'error_code', 'check'];

function thresholds() {
  const t = {
    // The SLO: p50, p95 and p99 of the measure phase, aborting as soon as one is breached.
    'http_req_duration{phase:measure}': [
      { threshold: `p(50)<=${SLO_MS}`, abortOnFail: true, delayAbortEval: '10s' },
      { threshold: `p(95)<=${SLO_MS}`, abortOnFail: true, delayAbortEval: '10s' },
      { threshold: `p(99)<=${SLO_MS}`, abortOnFail: true, delayAbortEval: '10s' },
    ],
    // One failed request, in ANY phase, fails the level.
    http_req_failed: [{ threshold: 'rate==0', abortOnFail: true }],
    checks: [{ threshold: 'rate==1', abortOnFail: true }],
    // Report-only sub-metrics. `max>=0` always holds; it only makes k6 track the series.
    'http_reqs{phase:measure}': ['count>=0'],
  };
  FAILURE_TYPES.forEach((f) => { t[`req_failures{type:${f}}`] = ['count>=0']; });
  STEPS.forEach((s) => { t[`http_req_duration{phase:measure,step:${s}}`] = ['max>=0']; });
  ENDPOINTS.forEach((e) => { t[`http_req_duration{phase:measure,endpoint:${e}}`] = ['max>=0']; });
  return t;
}

// One ramping-vus scenario: ramp (<=15 s) and hold are the warm-up, then the measure phase.
export function levelOptions() {
  const ramp = Math.min(15, WARMUP_S);
  const stages = [{ duration: `${ramp}s`, target: VUS }];
  if (WARMUP_S > ramp) stages.push({ duration: `${WARMUP_S - ramp}s`, target: VUS });
  stages.push({ duration: `${MEASURE_S}s`, target: VUS });
  return {
    summaryTrendStats: ['count', 'min', 'med', 'avg', 'p(90)', 'p(95)', 'p(99)', 'max'],
    systemTags: SYSTEM_TAGS,
    scenarios: {
      level: { executor: 'ramping-vus', startVUs: 0, stages, gracefulRampDown: '0s', gracefulStop: '10s' },
    },
    thresholds: thresholds(),
  };
}

// Open-model validation: constant arrival rate at the closed-model throughput (k6 plan §7).
export function openOptions(rate, durationS, preAllocatedVUs, maxVUs) {
  return {
    summaryTrendStats: ['count', 'min', 'med', 'avg', 'p(90)', 'p(95)', 'p(99)', 'max'],
    systemTags: SYSTEM_TAGS,
    scenarios: {
      level: {
        executor: 'constant-arrival-rate', rate, timeUnit: '1s', duration: `${durationS}s`,
        preAllocatedVUs, maxVUs,
      },
    },
    thresholds: {
      http_req_failed: [{ threshold: 'rate==0', abortOnFail: true }],
      checks: [{ threshold: 'rate==1', abortOnFail: true }],
      'http_req_duration': ['max>=0'],
      dropped_iterations: ['count>=0'],
      'req_failures{type:transport}': ['count>=0'],
      'req_failures{type:timeout}': ['count>=0'],
    },
  };
}

const v = (data, name, key) => {
  const m = data.metrics[name];
  return m && m.values && m.values[key] !== undefined ? m.values[key] : null;
};

// Condensed result consumed by the runner (loadtest/runner/runlevel.py).
export function buildResult(data, extra) {
  const dur = 'http_req_duration{phase:measure}';
  const perStep = {};
  STEPS.forEach((s) => {
    const n = `http_req_duration{phase:measure,step:${s}}`;
    if (data.metrics[n]) perStep[s] = { p50: v(data, n, 'med'), p95: v(data, n, 'p(95)'), p99: v(data, n, 'p(99)'), count: v(data, n, 'count') };
  });
  const perEndpoint = {};
  ENDPOINTS.forEach((e) => {
    const n = `http_req_duration{phase:measure,endpoint:${e}}`;
    if (data.metrics[n]) perEndpoint[e] = { p50: v(data, n, 'med'), p95: v(data, n, 'p(95)'), p99: v(data, n, 'p(99)'), count: v(data, n, 'count') };
  });
  const failuresByType = {};
  FAILURE_TYPES.forEach((f) => {
    const n = `req_failures{type:${f}}`;
    failuresByType[f] = data.metrics[n] ? v(data, n, 'count') || 0 : 0;
  });
  const open = !!(extra && extra.open);
  const lat = open ? 'http_req_duration' : dur;
  return Object.assign({
    scenario: SCENARIO_NAME, think: THINK, vus: VUS, warmup_s: WARMUP_S, measure_s: MEASURE_S,
    p50: v(data, lat, 'med'), p90: v(data, lat, 'p(90)'), p95: v(data, lat, 'p(95)'), p99: v(data, lat, 'p(99)'), max: v(data, lat, 'max'),
    requests_measure: v(data, 'http_reqs{phase:measure}', 'count'),
    rps_measure: v(data, 'http_reqs{phase:measure}', 'rate'),
    requests_total: v(data, 'http_reqs', 'count'),
    iterations: v(data, 'iterations', 'count'),
    iterations_per_s: v(data, 'iterations', 'rate'),
    dropped_iterations: v(data, 'dropped_iterations', 'count'),
    failed_rate: v(data, 'http_req_failed', 'rate'),
    checks_rate: v(data, 'checks', 'rate'),
    req_failures: v(data, 'req_failures', 'count'),
    per_step: perStep, per_endpoint: perEndpoint, failures_by_type: failuresByType,
  }, extra || {});
}

export function makeHandleSummary(extra) {
  return function handleSummary(data) {
    const result = buildResult(data, extra);
    const out = {};
    if (SUMMARY_PATH) out[SUMMARY_PATH] = JSON.stringify(data);
    if (RESULT_PATH) out[RESULT_PATH] = JSON.stringify(result, null, 2);
    out.stdout = `${result.scenario} ${result.think} vus=${result.vus} p50=${result.p50} p95=${result.p95} p99=${result.p99} ` +
      `rps=${result.rps_measure} failed_rate=${result.failed_rate} checks_rate=${result.checks_rate}\n`;
    return out;
  };
}
