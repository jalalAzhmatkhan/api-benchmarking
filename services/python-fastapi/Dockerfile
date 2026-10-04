# syntax=docker/dockerfile:1
# Base and uv images pinned by digest (VERSIONS.md).
FROM ghcr.io/astral-sh/uv:0.12.22@sha256:f513a91fc62fe7c17567eee97230dd198e43edb8a9fbecca843714a4358fe1bc AS uv

FROM python:3.14.8-slim-trixie@sha256:89fb7d3da20043c370643435258bdd7ab755d326d359001d02988ed15ae5219e AS build
COPY --from=uv /uv /usr/local/bin/uv
# Use the image's own interpreter; compile bytecode now so workers start without writing .pyc files.
ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
WORKDIR /app
# Dependency layer first, so source edits do not reinstall packages. Production dependencies only.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.14.8-slim-trixie@sha256:89fb7d3da20043c370643435258bdd7ab755d326d359001d02988ed15ae5219e
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080
WORKDIR /app
COPY --from=build /app/.venv ./.venv
COPY gunicorn.conf.py ./
COPY src ./src
# Non-root. WORKERS comes from deploy/stacks/python-fastapi.env (default 2, decision D-11); each worker
# gets its share of DB_POOL_SIZE from gunicorn.conf.py.
RUN useradd --system --no-create-home --uid 10001 app
USER app
EXPOSE 8080
ENTRYPOINT ["gunicorn", "-c", "gunicorn.conf.py", "app.main:app"]
