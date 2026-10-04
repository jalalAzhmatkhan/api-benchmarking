// Deterministic payloads: a seeded PRNG per (VU, iteration) so runs are reproducible.
export function rng(seed) {
  let a = seed >>> 0;
  const next = () => {
    // mulberry32
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    next,
    int: (min, max) => min + Math.floor(next() * (max - min + 1)),
  };
}

const ALPHABET = 'abcdefghijklmnopqrstuvwxyz0123456789';
function text(r, length) {
  let s = '';
  for (let i = 0; i < length; i++) s += ALPHABET[r.int(0, ALPHABET.length - 1)];
  return s;
}

// ASCII only: name about 20 chars, description about 60 chars (k6 plan §3.5).
export function itemInput(r) {
  return {
    name: text(r, 20),
    description: text(r, 60),
    price_cents: r.int(0, 1000000),
    quantity: r.int(0, 1000),
  };
}

export function seedFor(base, vuId, iteration) {
  return (base * 1000003 + vuId * 7919 + iteration * 104729) >>> 0;
}
