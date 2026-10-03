-- 100 000 deterministic rows (ids 1..100000 are read-only during benchmarks).
-- Identity is restarted by reset.sh, so the first id created by a service is 100001.
INSERT INTO items (name, description, price_cents, quantity)
SELECT 'item-' || g,
       CASE WHEN g % 10 = 0 THEN NULL ELSE 'desc-' || md5(g::text) END,
       (g * 37) % 1000000,
       g % 1000
FROM generate_series(1, 100000) AS g;
