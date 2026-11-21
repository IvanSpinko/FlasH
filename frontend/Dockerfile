# FlasH web app: built with Node, served by nginx.
# Usually started together with the API: see compose.yaml in the project root.

# 1. Build the app into static files (dist/).
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY . .
RUN npm run build

# 2. Serve them. Node isn't needed any more, so the final image is small.
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --start-interval=2s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1
