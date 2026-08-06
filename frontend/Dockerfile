# syntax=docker/dockerfile:1
# Multi-stage build for the Hexta frontend (Next.js static export via output:'export').
# Rebuild the static export with `npm run build` if you change the kit.
FROM node:20-slim AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY . .
# NEXT_PUBLIC_API_URL is inlined at build time; default points at the backend stack service.
ARG NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=builder /app/out /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
