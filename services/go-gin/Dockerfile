# syntax=docker/dockerfile:1
# Base images pinned by digest (VERSIONS.md).
FROM golang:1.27.1-trixie@sha256:3b77fc618ec235a1ab412de7737f120dd507c57e8d87de4cbb7994fb94275ed5 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
# Release build: static binary, no debug info. No PGO, no custom GC flags (benchmark-rules.md).
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/server ./cmd/server

FROM debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /out/server /usr/local/bin/server
USER 10001
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/server"]
