# syntax=docker/dockerfile:1
# Base image pinned by digest (VERSIONS.md).
FROM node:26.10.0-trixie-slim@sha256:ec7758ee051e457b468b32bde57b0879010b325bb9862718e9615225ce4aaae1 AS build
WORKDIR /app
# Dependency layer first, so source edits do not reinstall packages.
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json tsconfig.build.json ./
COPY src ./src
# TypeScript compiled to JavaScript (D-01); only production dependencies are kept for the runtime image.
RUN npm run build && npm prune --omit=dev

FROM node:26.10.0-trixie-slim@sha256:ec7758ee051e457b468b32bde57b0879010b325bb9862718e9615225ce4aaae1
ENV NODE_ENV=production \
    PORT=8080
WORKDIR /app
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
# The base image ships a non-root `node` user. WORKERS comes from deploy/stacks/node-fastify.env
# (default: one worker per available CPU, decision D-16); no V8 or Node flags.
USER node
EXPOSE 8080
ENTRYPOINT ["node", "dist/main.js"]
