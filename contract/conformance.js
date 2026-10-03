// Black-box contract conformance suite (k6, functional, 1 iteration).
// Every service must pass 100 % before it is benchmark-eligible.
//   k6 run -e BASE_URL=http://127.0.0.1:8080 contract/conformance.js
// Spec: Documentation/specs/api-contract.md §5. Only the contract is asserted, no implementation details.
import http from 'k6/http';
import { check } from 'k6';

const BASE = (__ENV.BASE_URL || 'http://127.0.0.1:8080').replace(/\/$/, '');
const MAX_ID = '9007199254740991';
const MAX_ID_PLUS_1 = '9007199254740992';
const MAX_PRICE = 9007199254740991;
const MAX_QTY = 2147483647;
const JSON_HDR = { 'Content-Type': 'application/json' };

export const options = {
  vus: 1,
  iterations: 1,
  // Any failed assertion fails the run (non-zero exit code).
  thresholds: { checks: ['rate==1'] },
};

// ---- helpers ----------------------------------------------------------------
function call(method, path, body, raw) {
  const payload = raw !== undefined ? raw : body === undefined ? null : JSON.stringify(body);
  return http.request(method, BASE + path, payload, {
    headers: JSON_HDR,
    // 4xx are expected responses here; never let k6 count them as failed requests.
    responseCallback: http.expectedStatuses({ min: 200, max: 499 }),
  });
}

function json(res) {
  try {
    return res.json();
  } catch (e) {
    return undefined;
  }
}

function header(res, name) {
  const wanted = name.toLowerCase();
  for (const k of Object.keys(res.headers)) {
    if (k.toLowerCase() === wanted) return res.headers[k];
  }
  return undefined;
}

function assertStatus(res, status, label) {
  check(res, { [`${label}: status ${status}`]: (r) => r.status === status });
}

function assertError(res, status, code, label) {
  const b = json(res);
  check(res, {
    [`${label}: status ${status}`]: (r) => r.status === status,
    [`${label}: error.code ${code}`]: () => !!b && !!b.error && b.error.code === code,
    [`${label}: error.message is a string`]: () => !!b && !!b.error && typeof b.error.message === 'string',
  });
}

const isTs = (v) => typeof v === 'string' && !Number.isNaN(Date.parse(v));

function assertItem(res, expected, label) {
  const b = json(res);
  check(res, {
    [`${label}: JSON content type`]: (r) => /^application\/json/i.test(header(r, 'Content-Type') || ''),
    [`${label}: id is a positive integer`]: () => !!b && Number.isInteger(b.id) && b.id > 0,
    [`${label}: name`]: () => !!b && b.name === expected.name,
    [`${label}: description`]: () => !!b && b.description === (expected.description === undefined ? null : expected.description),
    [`${label}: price_cents`]: () => !!b && b.price_cents === expected.price_cents,
    [`${label}: quantity`]: () => !!b && b.quantity === expected.quantity,
    [`${label}: created_at is a timestamp`]: () => !!b && isTs(b.created_at),
    [`${label}: updated_at is a timestamp`]: () => !!b && isTs(b.updated_at),
  });
  return b;
}

function create(body, label) {
  const res = call('POST', '/items', body);
  assertStatus(res, 201, label);
  const b = json(res);
  return { res, id: b && b.id };
}

const valid = { name: 'Widget', description: 'Blue', price_cents: 1999, quantity: 5 };

export default function () {
  // ---- POST: success -----------------------------------------------------------
  {
    const { res, id } = create(valid, 'POST valid');
    const b = assertItem(res, valid, 'POST valid');
    check(res, {
      'POST valid: Location header': (r) => (header(r, 'Location') || '').endsWith(`/items/${id}`),
      'POST valid: updated_at is not before created_at': () => !!b && Date.parse(b.updated_at) >= Date.parse(b.created_at),
    });
    call('DELETE', `/items/${id}`);
  }
  {
    const r1 = create({ name: 'n', price_cents: 0, quantity: 0 }, 'POST description absent');
    assertItem(r1.res, { name: 'n', description: null, price_cents: 0, quantity: 0 }, 'POST description absent');
    const r2 = create({ name: 'n', description: null, price_cents: 1, quantity: 1 }, 'POST description null');
    assertItem(r2.res, { name: 'n', description: null, price_cents: 1, quantity: 1 }, 'POST description null');
    const r3 = create({ ...valid, unknown_field: 'ignored', id: 1 }, 'POST unknown fields ignored');
    const b3 = assertItem(r3.res, valid, 'POST unknown fields ignored');
    check(r3.res, { 'POST unknown fields: id is not taken from the client': () => !!b3 && b3.id !== 1 });
    [r1.id, r2.id, r3.id].forEach((i) => call('DELETE', `/items/${i}`));
  }

  // ---- POST: boundaries accepted ----------------------------------------------
  const okCases = [
    ['name length 1', { ...valid, name: 'a' }],
    ['name length 100', { ...valid, name: 'a'.repeat(100) }],
    ['description length 0', { ...valid, description: '' }],
    ['description length 1000', { ...valid, description: 'd'.repeat(1000) }],
    ['price_cents 0', { ...valid, price_cents: 0 }],
    ['price_cents max', { ...valid, price_cents: MAX_PRICE }],
    ['quantity 0', { ...valid, quantity: 0 }],
    ['quantity max', { ...valid, quantity: MAX_QTY }],
  ];
  okCases.forEach(([label, body]) => {
    const { res, id } = create(body, `POST ${label}`);
    assertItem(res, body, `POST ${label}`);
    call('DELETE', `/items/${id}`);
  });

  // ---- POST: invalid input → 400 VALIDATION_ERROR ------------------------------
  const badBodies = [
    ['name empty', JSON.stringify({ ...valid, name: '' })],
    ['name length 101', JSON.stringify({ ...valid, name: 'a'.repeat(101) })],
    ['name missing', JSON.stringify({ price_cents: 1, quantity: 1 })],
    ['name null', JSON.stringify({ ...valid, name: null })],
    ['name not a string', JSON.stringify({ ...valid, name: 5 })],
    ['description length 1001', JSON.stringify({ ...valid, description: 'd'.repeat(1001) })],
    ['description not a string', JSON.stringify({ ...valid, description: 5 })],
    ['price_cents missing', JSON.stringify({ name: 'n', quantity: 1 })],
    ['price_cents negative', JSON.stringify({ ...valid, price_cents: -1 })],
    // raw text: JS cannot serialize integers above 2^53 or keep 1.5 distinct from an integer
    ['price_cents above max', `{"name":"n","price_cents":${MAX_ID_PLUS_1},"quantity":1}`],
    ['price_cents fractional', '{"name":"n","price_cents":1.5,"quantity":1}'],
    ['price_cents as string', JSON.stringify({ ...valid, price_cents: '10' })],
    ['quantity missing', JSON.stringify({ name: 'n', price_cents: 1 })],
    ['quantity negative', JSON.stringify({ ...valid, quantity: -1 })],
    ['quantity above max', JSON.stringify({ ...valid, quantity: MAX_QTY + 1 })],
    ['quantity fractional', '{"name":"n","price_cents":1,"quantity":1.5}'],
    ['quantity as string', JSON.stringify({ ...valid, quantity: '1' })],
    ['body is an array', '[]'],
    ['body is a string', '"x"'],
    ['malformed JSON', '{"name":'],
    ['empty body', ''],
  ];
  badBodies.forEach(([label, raw]) => {
    assertError(call('POST', '/items', undefined, raw), 400, 'VALIDATION_ERROR', `POST ${label}`);
  });

  // ---- GET ----------------------------------------------------------------------
  {
    const { id } = create(valid, 'GET fixture');
    const res = call('GET', `/items/${id}`);
    assertStatus(res, 200, 'GET existing');
    const b = assertItem(res, valid, 'GET existing');
    check(res, { 'GET existing: id matches': () => !!b && b.id === id });
    ['abc', '0', '-1', '1.5', '1e3', MAX_ID_PLUS_1, '99999999999999999999'].forEach((bad) => {
      assertError(call('GET', `/items/${bad}`), 400, 'VALIDATION_ERROR', `GET invalid id "${bad}"`);
    });
    assertError(call('GET', `/items/${MAX_ID}`), 404, 'NOT_FOUND', 'GET unknown id');
    call('DELETE', `/items/${id}`);
  }

  // ---- PUT ----------------------------------------------------------------------
  {
    const { id, res: created } = create(valid, 'PUT fixture');
    const before = json(created);
    const next = { name: 'Gadget', description: 'Red', price_cents: 2500, quantity: 9 };
    const res = call('PUT', `/items/${id}`, next);
    assertStatus(res, 200, 'PUT existing');
    const b = assertItem(res, next, 'PUT existing');
    check(res, {
      'PUT existing: id unchanged': () => !!b && b.id === id,
      'PUT existing: created_at unchanged': () => !!b && !!before && Date.parse(b.created_at) === Date.parse(before.created_at),
      'PUT existing: updated_at not before created_at': () => !!b && Date.parse(b.updated_at) >= Date.parse(b.created_at),
    });
    assertItem(call('GET', `/items/${id}`), next, 'PUT is persisted (GET)');

    // full replacement: an omitted description becomes null
    const full = call('PUT', `/items/${id}`, { name: 'Gadget2', price_cents: 1, quantity: 1 });
    assertStatus(full, 200, 'PUT without description');
    const replaced = { name: 'Gadget2', description: null, price_cents: 1, quantity: 1 };
    assertItem(full, replaced, 'PUT without description (replaced by null)');

    assertError(call('PUT', `/items/${MAX_ID}`, next), 404, 'NOT_FOUND', 'PUT unknown id');
    ['abc', '0', '-1'].forEach((bad) => {
      assertError(call('PUT', `/items/${bad}`, next), 400, 'VALIDATION_ERROR', `PUT invalid id "${bad}"`);
    });
    assertError(call('PUT', `/items/${id}`, undefined, '{"name":'), 400, 'VALIDATION_ERROR', 'PUT malformed JSON');
    assertError(call('PUT', `/items/${id}`, { ...next, name: '' }), 400, 'VALIDATION_ERROR', 'PUT invalid body');
    assertError(call('PUT', `/items/${id}`, { ...next, quantity: -1 }), 400, 'VALIDATION_ERROR', 'PUT quantity negative');
    assertItem(call('GET', `/items/${id}`), replaced, 'PUT with invalid body leaves the item unchanged');
    call('DELETE', `/items/${id}`);
  }

  // ---- DELETE -------------------------------------------------------------------
  {
    const { id } = create(valid, 'DELETE fixture');
    const res = call('DELETE', `/items/${id}`);
    check(res, {
      'DELETE existing: status 204': (r) => r.status === 204,
      'DELETE existing: empty body': (r) => r.body === '' || r.body === null,
    });
    assertError(call('GET', `/items/${id}`), 404, 'NOT_FOUND', 'GET after DELETE');
    assertError(call('DELETE', `/items/${id}`), 404, 'NOT_FOUND', 'DELETE again');
    ['abc', '0', '-1'].forEach((bad) => {
      assertError(call('DELETE', `/items/${bad}`), 400, 'VALIDATION_ERROR', `DELETE invalid id "${bad}"`);
    });
    assertError(call('DELETE', `/items/${MAX_ID}`), 404, 'NOT_FOUND', 'DELETE unknown id');
  }

  // ---- general: no caching headers, no compression -------------------------------
  {
    const { res, id } = create(valid, 'headers');
    const g = call('GET', `/items/${id}`);
    [res, g].forEach((r, i) => {
      const tag = i === 0 ? 'POST' : 'GET';
      check(r, {
        [`${tag}: no ETag`]: (x) => header(x, 'ETag') === undefined,
        [`${tag}: no Cache-Control`]: (x) => header(x, 'Cache-Control') === undefined,
        [`${tag}: no Last-Modified`]: (x) => header(x, 'Last-Modified') === undefined,
        [`${tag}: no Content-Encoding`]: (x) => header(x, 'Content-Encoding') === undefined,
      });
    });
    call('DELETE', `/items/${id}`);
  }
}
