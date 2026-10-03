# Used by the service-ci self-test and the dev compose. Not a benchmarked service.
FROM python:3.14.8-slim-trixie@sha256:89fb7d3da20043c370643435258bdd7ab755d326d359001d02988ed15ae5219e
WORKDIR /app
COPY server.py .
USER nobody
ENV PORT=8080
EXPOSE 8080
CMD ["python", "/app/server.py"]
