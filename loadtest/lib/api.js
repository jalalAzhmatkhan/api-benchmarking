// HTTP helper: tags, expected statuses, failure classification, phase tagging.
import http from 'k6/http';
import { check } from 'k6';
import exec from 'k6/execution';
import { Counter } from 'k6/metrics';
import { BASE_URL, DETAIL, WARMUP_S } from './config.js';

// Failures by type so the analysis can tell a server fault from a load-generator/network fault:
// status | transport | timeout | check
export const failures = new Counter('req_failures');

const ENDPOINT = { GET: 'get', POST: 'post', PUT: 'put', DELETE: 'delete' };
const HEADERS = { 'Content-Type': 'application/json' };
const K6_TIMEOUT_CODE = 1050;

// Reused per-call objects: building them on every request is measurable load-generator CPU.
const expectedCache = {};
function expectedStatuses(list) {
  const key = list.join(',');
  return expectedCache[key] || (expectedCache[key] = http.expectedStatuses(...list));
}
const tagCache = {};
function tagsFor(step, method, path) {
  const name = `${method} ${path.indexOf('/', 1) > 0 ? '/items/{id}' : '/items'}`; // keeps cardinality low
  if (!DETAIL) return { name };
  const key = `${step}|${name}`;
  return tagCache[key] || (tagCache[key] = { step: String(step), endpoint: ENDPOINT[method], name });
}

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
    responseCallback: expectedStatuses(expected),
    tags: tagsFor(step, method, path),
  });
  if (expected.indexOf(res.status) === -1) {
    let type = 'status';
    if (res.status === 0) type = res.error_code === K6_TIMEOUT_CODE ? 'timeout' : 'transport';
    failures.add(1, { type });
  }
  return res;
}

// Lean levels (search runs, DETAIL off) skip body parsing and body checks: they are the load
// generator's biggest per-request cost. `needed` forces parsing where the journey uses the body (ids).
// Body correctness under load is verified by the confirmation runs (DETAIL=1) and conformance.
export function parse(res, needed = false) {
  if (!DETAIL && !needed) return undefined;
  try {
    return res.json();
  } catch (e) {
    return undefined;
  }
}

// Runs the checks; returns true only if all passed (a failed step ends the iteration).
export function verify(res, label, conditions) {
  if (!DETAIL) {
    // Lean: the first condition is always the status check; no k6 `check` sample is emitted.
    const ok = conditions[Object.keys(conditions)[0]](res);
    if (!ok) failures.add(1, { type: 'check' });
    return ok;
  }
  const named = {};
  Object.keys(conditions).forEach((k) => {
    named[`${label}: ${k}`] = conditions[k];
  });
  const ok = check(res, named);
  if (!ok) failures.add(1, { type: 'check' });
  return ok;
}
