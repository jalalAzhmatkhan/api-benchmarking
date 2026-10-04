# node-fastify

**Stack:** Node.js 26.10 · Fastify 5.12 · TypeScript 7.0 (compiled to JS) · `pg` 8.23 `Pool` · `node:cluster` (versions: `../../VERSIONS.md`)
**Status:** implemented (T-2.2.a/b/c). Implements the `/items` contract (`../../contract/openapi.yaml`).

## Layout (clean architecture)
```
src/domain/          Item, ItemInput, ItemRepository port, validation (code points), ValidationError/NotFoundError
src/application/     createUseCases(repository): getItem, createItem, replaceItem, deleteItem
src/infrastructure/  config.ts (env contract), postgres.ts (raw-SQL repository, pool, warm-up)
src/interface/       server.ts (Fastify routes, error handler), parse.ts (strict body parsing, wire format)
src/app.ts           composition root: config → pool → repository → use cases → server
src/cluster.ts       node:cluster primary: forks WORKERS workers, splits the pool, supervises
src/main.ts          bare entrypoint (excluded from coverage)
```
Dependencies point inward. Source uses erasable TypeScript only, so tests run on Node's native type stripping; production runs the `tsc` output (`dist/`).

## Run / test
```bash
docker compose -f ../../deploy/compose.dev.yaml up -d postgres && docker compose -f ../../deploy/compose.dev.yaml run --rm db-init
npm ci && npm run build
DATABASE_URL=postgres://bench:bench@127.0.0.1:5432/bench WORKERS=2 npm start
k6 run -e BASE_URL=http://127.0.0.1:8080 ../../contract/conformance.js

npm run typecheck && npm test      # 100 % line/branch/function gate; DATABASE_URL enables the 2 integration tests
```

## Non-default configuration knobs
| Knob | Value | Why |
|---|---|---|
| `node:cluster` workers | `WORKERS` (default = `os.availableParallelism()`, **2** on the SUT via `deploy/stacks/node-fastify.env`) | one JS thread per vCPU (D-16); ablation `WORKERS=1` |
| Pool | total `DB_POOL_SIZE` (10) split across workers (5 + 5); each worker: `max = min`, `connectionTimeoutMillis` 5000, `idleTimeoutMillis` 0 (no eviction), pre-warmed before listening | `connection-pooling.md` |
| Fastify | `logger: false`, no plugins, no JSON schemas (default `JSON.stringify` serialization) | per-request logging off, no extra middleware |
| Body parsing | every content type delivered as a raw Buffer, parsed in `parse.ts` | malformed input must be the contract 400, not Fastify's 415/400 |
| `NODE_ENV=production` | in the image | release mode |
| BIGINT type parser | `int8` → `Number` | `pg` returns bigint as strings; ids/prices stay below 2^53 by contract |

Default: `pg` unnamed extended-protocol statements (D-06), Fastify limits (1 MiB body, 72 s keep-alive), V8 heap sizing, no Node flags.

**Known differences from the other stacks** (outside the conformance suite): JSON numbers that are mathematically integers (`1.0`, `1e3`) are accepted as integers because `JSON.parse` cannot tell them apart; unknown routes and wrong methods both answer 404 (Fastify has no 405).
