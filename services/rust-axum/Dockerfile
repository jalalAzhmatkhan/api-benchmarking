# syntax=docker/dockerfile:1
# Base images pinned by digest (VERSIONS.md).
FROM rust:1.99.0-slim-trixie@sha256:01dd4f9c24801cfc8ba9cf8a5dd6dcca451cd17d1ae73574edc22591de6e6816 AS build
WORKDIR /src
# Dependency layer: compile the dependencies against a stub so source edits do not rebuild them.
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo 'fn main() {}' > src/main.rs && echo '' > src/lib.rs \
    && cargo build --release --locked && rm -rf src target/release/deps/items_api* target/release/server*
COPY src ./src
# Default release profile (opt-level 3); no LTO, no PGO, no target-cpu (benchmark-rules.md).
RUN cargo build --release --locked

FROM debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /src/target/release/server /usr/local/bin/server
USER 10001
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/server"]
