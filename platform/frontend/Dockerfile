# =============================================================================
#  FindJob frontend — multi-stage build.
#    1. Build the Vite bundle on a slim Node image.
#    2. Serve it from nginx with SPA fallback + reverse-proxy to /api.
# =============================================================================

# ---------- Stage 1: build ----------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# Install deps first for better layer caching
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Vite bakes env vars at build time. They must be prefixed VITE_ and provided
# via --build-arg / docker-compose `args`. They are NOT secrets — they end up
# in the JS bundle visible to every browser.
ARG VITE_API_URL=/api/v1
ARG VITE_GOOGLE_CLIENT_ID=
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID

COPY . .
RUN npm run build

# ---------- Stage 2: serve ----------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Remove default site
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/findjob.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
