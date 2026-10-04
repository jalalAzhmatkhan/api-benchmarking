import { sleep } from 'k6';
import exec from 'k6/execution';
import { SEED, SEED_ROWS } from './config.js';
import { call, parse, verify } from './api.js';
import { itemInput, rng, seedFor } from './payloads.js';
import { think, stagger } from './think.js';

const isTs = (v) => typeof v === 'string' && !Number.isNaN(Date.parse(v));
const MAX_OWNED = 10; // S2: rows a VU keeps before it deletes one instead of creating another

function iterationRng() {
  return rng(seedFor(SEED, exec.vu.idInTest, exec.vu.iterationInScenario));
}

// ---- S1: the 7-step user journey (k6 plan §3.1) ------------------------------------------
//   GET(seeded) → POST → GET → PUT → GET → DELETE → GET(404)
// A failed step ends the iteration, so one fault is not counted several times. Think time
// follows every step.
export function s1Journey() {
  stagger(exec.vu.iterationInScenario === 0);
  const r = iterationRng();

  // 1. read a seeded row
  const seededId = r.int(1, SEED_ROWS);
  let res = call(1, 'GET', `/items/${seededId}`, undefined, [200]);
  let b = parse(res);
  if (!verify(res, 'step1 GET seeded', { 'status 200': (x) => x.status === 200, 'id matches': () => !!b && b.id === seededId })) return;
  think();

  // 2. create
  const created = itemInput(r);
  res = call(2, 'POST', '/items', created, [201]);
  b = parse(res);
  if (!verify(res, 'step2 POST', {
    'status 201': (x) => x.status === 201,
    'echoes name and price': () => !!b && b.name === created.name && b.price_cents === created.price_cents,
    'Location header': (x) => (x.headers['Location'] || x.headers['location'] || '').indexOf('/items/') !== -1,
  })) return;
  const id = b.id;
  think();

  // 3. read your write
  res = call(3, 'GET', `/items/${id}`, undefined, [200]);
  b = parse(res);
  if (!verify(res, 'step3 GET created', {
    'status 200': (x) => x.status === 200,
    'equals POSTed values': () => !!b && b.id === id && b.name === created.name && b.quantity === created.quantity && b.price_cents === created.price_cents,
  })) return;
  think();

  // 4. replace
  const updated = itemInput(r);
  res = call(4, 'PUT', `/items/${id}`, updated, [200]);
  b = parse(res);
  if (!verify(res, 'step4 PUT', {
    'status 200': (x) => x.status === 200,
    'echoes new values': () => !!b && b.name === updated.name && b.price_cents === updated.price_cents && b.quantity === updated.quantity,
    'timestamps': () => !!b && isTs(b.updated_at) && Date.parse(b.updated_at) >= Date.parse(b.created_at),
  })) return;
  think();

  // 5. read the replacement
  res = call(5, 'GET', `/items/${id}`, undefined, [200]);
  b = parse(res);
  if (!verify(res, 'step5 GET updated', {
    'status 200': (x) => x.status === 200,
    'equals PUT values': () => !!b && b.name === updated.name && b.price_cents === updated.price_cents && b.quantity === updated.quantity,
  })) return;
  think();

  // 6. delete
  res = call(6, 'DELETE', `/items/${id}`, undefined, [204]);
  if (!verify(res, 'step6 DELETE', { 'status 204': (x) => x.status === 204 })) return;
  think();

  // 7. the item is gone: a 404 is the EXPECTED answer here (and only here)
  res = call(7, 'GET', `/items/${id}`, undefined, [404]);
  b = parse(res);
  verify(res, 'step7 GET deleted', {
    'status 404': (x) => x.status === 404,
    'NOT_FOUND error body': () => !!b && !!b.error && b.error.code === 'NOT_FOUND',
  });
  think();
}

// ---- S2: read-heavy, independent requests (k6 plan §3.2) ---------------------------------
// Weights: GET 80 %, POST 7 %, PUT 6 %, DELETE 7 %. PUT/DELETE act on rows this VU created (POST
// instead if it owns none); POST becomes DELETE once the VU owns MAX_OWNED rows. That keeps the
// table size stable and each row owned by exactly one VU.
const owned = []; // per-VU state: ids created by this VU

export function s2Op() {
  stagger(exec.vu.iterationInScenario === 0);
  const r = iterationRng();
  const roll = r.next() * 100;
  let op = roll < 80 ? 'GET' : roll < 87 ? 'POST' : roll < 93 ? 'PUT' : 'DELETE';
  if ((op === 'PUT' || op === 'DELETE') && owned.length === 0) op = 'POST';
  if (op === 'POST' && owned.length >= MAX_OWNED) op = 'DELETE';

  if (op === 'GET') {
    const id = r.int(1, SEED_ROWS);
    const res = call(1, 'GET', `/items/${id}`, undefined, [200]);
    verify(res, 'GET seeded', { 'status 200': (x) => x.status === 200 });
  } else if (op === 'POST') {
    const res = call(2, 'POST', '/items', itemInput(r), [201]);
    const b = parse(res);
    if (verify(res, 'POST', { 'status 201': (x) => x.status === 201, 'has id': () => !!b && Number.isInteger(b.id) })) owned.push(b.id);
  } else if (op === 'PUT') {
    const id = owned[r.int(0, owned.length - 1)];
    const res = call(4, 'PUT', `/items/${id}`, itemInput(r), [200]);
    verify(res, 'PUT', { 'status 200': (x) => x.status === 200 });
  } else {
    const idx = r.int(0, owned.length - 1);
    const id = owned.splice(idx, 1)[0];
    const res = call(6, 'DELETE', `/items/${id}`, undefined, [204]);
    verify(res, 'DELETE', { 'status 204': (x) => x.status === 204 });
  }
  think();
}

// ---- S3: GET only, diagnostic upper bound (k6 plan §3.3) ---------------------------------
export function s3Op() {
  stagger(exec.vu.iterationInScenario === 0);
  const id = iterationRng().int(1, SEED_ROWS);
  const res = call(1, 'GET', `/items/${id}`, undefined, [200]);
  verify(res, 'GET seeded', { 'status 200': (x) => x.status === 200 });
  think();
}

export { sleep };
