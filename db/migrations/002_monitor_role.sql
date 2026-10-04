-- Read-only role for the resource sampler (monitoring/sampler.py). No password and no remote
-- login: it is reachable only through the container's local socket (docker exec), and TCP
-- connections need a password it does not have. It is deliberately not the `bench` role, so the
-- sampler's connection never counts toward the service's pool (pg_stat_activity usename='bench').
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'monitor') THEN
    CREATE ROLE monitor LOGIN;
  END IF;
END
$$;
GRANT pg_monitor TO monitor;
GRANT CONNECT ON DATABASE bench TO monitor;
