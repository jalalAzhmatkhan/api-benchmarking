// HTTP helper: tags, expected statuses, failure classification, phase tagging.
import http from 'k6/http';
import { check } from 'k6';
import exec from 'k6/execution';
import { Counter } from 'k6/metrics';
import { BASE_URL, WARMUP_S } from './config.js';

// Failures by type so the analysis can tell a server fault from a load-generator/network fault:
// status | transport | timeout | check
export const failures = new Counter('req_failures');

const ENDPOINT = { GET: 'get', POST: 'post', PUT: 'put', DELETE: 'delete' };
const HEADERS = { 'Content-Type': 'application/json' };
const K6_TIMEOUT_CODE = 1050;

// Latency thresholds only look at the measure phase; failures count in every phase.
function setPhase() {
  const elapsedMs = Date.now() - exec.scenario.startTime;
  exec.vu.metrics.tags.phase = elapsedMs < WARMUP_S * 1000 ? 'warmup' : 'measure';
}

export function call(step, method, path, body, expected) {
  setPhase();
  const res = http.request(method, BASE_URL + path, body === undefined ? null : JSON.stringify(body), {
    headers: HEADERS,
    timeout: '5s',
    responseCallback: http.expectedStatuses(...expected),
    tags: {
      step: String(step),
      endpoint: ENDPOINT[method],
      name: `${method} ${path.indexOf('/', 1) > 0 ? '/items/{id}' : '/items'}`, // keeps cardinality low
    },
  });
  if (expected.indexOf(res.status) === -1) {
    let type = 'status';
    if (res.status === 0) type = res.error_code === K6_TIMEOUT_CODE ? 'timeout' : 'transport';
    failures.add(1, { type });
  }
  return res;
}

export function parse(res) {
  try {
    return res.json();
  } catch (e) {
    return undefined;
  }
}

// Runs the checks; returns true only if all passed (a failed step ends the iteration).
export function verify(res, label, conditions) {
  const named = {};
  Object.keys(conditions).forEach((k) => {
    named[`${label}: ${k}`] = conditions[k];
  });
  const ok = check(res, named);
  if (!ok) failures.add(1, { type: 'check' });
  return ok;
}
