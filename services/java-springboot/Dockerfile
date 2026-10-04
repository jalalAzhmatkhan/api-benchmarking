# syntax=docker/dockerfile:1
# Base images pinned by digest (VERSIONS.md).
FROM eclipse-temurin:25.0.4.1_1-jdk-noble@sha256:0d623ea18d7b0fe1e12a2c0a920f7e950cad433387e5a49d3611e1507fa07602 AS build
WORKDIR /src
# Dependency layer first, so source edits do not re-download the world.
COPY .mvn .mvn
COPY mvnw pom.xml ./
RUN ./mvnw -B -ntp -q dependency:go-offline
COPY src ./src
# Tests and the coverage gate run in CI before the image is built.
RUN ./mvnw -B -ntp -q -DskipTests -Djacoco.skip=true package && cp target/app.jar /app.jar

FROM eclipse-temurin:25.0.4.1_1-jre-noble@sha256:398f810215757dc1926390014272579fb0e57c41ef1c8aa4f64ae761613a168b
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /app.jar /app/app.jar
USER 10001
ENV PORT=8080
EXPOSE 8080
# No JVM flags: ergonomic defaults (decision D-04): G1 on 2 CPUs, heap = 25 % of the container limit.
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
