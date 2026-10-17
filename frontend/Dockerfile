# syntax=docker/dockerfile:1

# Build the Vite bundle from the locked dependency graph.
FROM node:22-alpine AS build

WORKDIR /app

# Dependencies are installed first so the layer is reused when only app code changes.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run test && npm run build


# Serve the static bundle. No Node runtime, no source, no build tools.
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
