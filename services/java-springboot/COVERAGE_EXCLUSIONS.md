# Coverage exclusions: java-springboot

| Class | Reason |
|---|---|
| `bench.items.ItemsApplication` | Bare `main()` entrypoint (`SpringApplication.run`). All wiring is in `AppConfig`, which `ApplicationIntegrationTest` starts for real. Approved by the System Analyst role per `clean-architecture.md` |

JaCoCo gate (`pom.xml`, `jacoco:check` at `verify`): BUNDLE **line 100 %** and **branch 100 %**.
Database-backed tests (`JdbcItemRepositoryTest`, `PoolWarmerTest`, `ApplicationIntegrationTest`) run when
`DATABASE_URL` is set; CI starts the seeded dev PostgreSQL so they count toward coverage.
