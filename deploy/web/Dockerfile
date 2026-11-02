# syntax=docker/dockerfile:1
# Build context: repository root (see docker-compose.yml)
FROM node:22-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY deploy/nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /src/dist /usr/share/nginx/html
RUN rm -f /etc/nginx/conf.d/default.conf && mkdir -p /var/www/certbot
EXPOSE 80 443
