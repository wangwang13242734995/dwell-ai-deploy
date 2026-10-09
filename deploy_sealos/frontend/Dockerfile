# dwell-frontend 镜像（Sealos 部署，Next.js standalone）
# 构建（两阶段，最终域名注入构建期）：
#   docker build \
#     --build-arg NEXT_PUBLIC_API_URL=https://<最终域名> \
#     --build-arg BACKEND_URL=http://dwell-backend:8000 \
#     -t ghcr.io/<GH_USER>/dwell-frontend:v1.0.0-sealos \
#     -f deploy_sealos/frontend/Dockerfile .

# ---- deps ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# ---- builder ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./
# 覆盖为 standalone 生产配置（含内网 rewrite）
COPY deploy_sealos/frontend/next.config.production.ts ./next.config.ts

ARG NEXT_PUBLIC_API_URL
ARG BACKEND_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    BACKEND_URL=$BACKEND_URL

RUN npm run build

# ---- runner ----
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup -S nodejs && adduser -S nextjs -G nodejs

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
