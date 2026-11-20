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
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
