# syntax=docker/dockerfile:1
# Base images pinned by digest (VERSIONS.md).
FROM mcr.microsoft.com/dotnet/sdk:10.0@sha256:e70cdb7f80b0348f5cb85f19a8f670fca061f033d57eed12fa003d58b0e06317 AS build
WORKDIR /src
# Restore layer: project files only, so source edits do not re-download packages.
COPY global.json Directory.Build.props Directory.Packages.props ./
COPY src/Items.Domain/Items.Domain.csproj src/Items.Domain/
COPY src/Items.Application/Items.Application.csproj src/Items.Application/
COPY src/Items.Infrastructure/Items.Infrastructure.csproj src/Items.Infrastructure/
COPY src/Items.Api/Items.Api.csproj src/Items.Api/
RUN dotnet restore src/Items.Api/Items.Api.csproj
COPY src ./src
# Release build, framework-dependent. No Native AOT, no ReadyToRun, no trimming (benchmark-rules.md).
RUN dotnet publish src/Items.Api/Items.Api.csproj -c Release --no-restore -o /out

FROM mcr.microsoft.com/dotnet/aspnet:10.0.12@sha256:222759b391a1aaf241166672c8f99b2d4ada452e7b5319f3c6e8f265a37b5ad4
WORKDIR /app
COPY --from=build /out .
# The base image ships a non-root `app` user.
USER $APP_UID
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["dotnet", "Items.Api.dll"]
