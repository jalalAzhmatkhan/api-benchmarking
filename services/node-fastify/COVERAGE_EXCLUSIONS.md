# Coverage exclusions: node-fastify

| Path | Reason |
|---|---|
| `src/main.ts` | Bare process entrypoint: chooses single process vs cluster primary and wires `process` signals. All logic (`cluster.ts`, `app.ts`, config, server) is in tested modules. Approved by the System Analyst role per `clean-architecture.md` |
| `src/**/*.test.ts` | Test files themselves |

Gate (`npm test`): Node's built-in coverage, **100 % lines, 100 % branches, 100 % functions** over `src/**`.
Everything but the two database-backed integration tests (`integration.test.ts`, skipped without `DATABASE_URL`) runs
without a database; CI sets `DATABASE_URL` so those run too.
