# syntax=docker/dockerfile:1

# Build the Spring Boot jar. The whole repository is the build context because
# this is a Maven project rooted at the repository top level; `.dockerignore`
# keeps everything the build does not need out of it.
FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /build

# The dependency graph is resolved separately so it is cached across code changes.
COPY pom.xml ./
RUN mvn -B --no-transfer-progress dependency:go-offline

COPY src ./src
RUN mvn -B --no-transfer-progress -DskipTests package


# Runtime image: JRE only, non-root, no build tooling.
FROM eclipse-temurin:21-jre AS runtime

ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75"

WORKDIR /app

# Export jobs write files, so the non-root user needs a directory it owns. The
# property default (./target/export-jobs) resolves to /app/target, which the app
# user cannot create because /app belongs to root; /app itself stays read-only.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /var/lib/expense-tracker/exports \
    && chown -R app:app /var/lib/expense-tracker

ENV APP_EXPORT_JOBS_STORAGE_DIR=/var/lib/expense-tracker/exports

COPY --from=builder /build/target/*.jar app.jar
USER app

EXPOSE 9090

ENTRYPOINT ["java", "-jar", "app.jar"]
