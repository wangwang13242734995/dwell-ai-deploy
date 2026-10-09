#!/usr/bin/env bash
# ============================================================
# dwell-backend 构建 / 本地冒烟 / 推送（Sealos 部署）
# 用法：
#   GH_USER=<GitHub用户名> bash deploy_sealos/build_push.sh [tag]
# 默认 tag: v1.0.0-sealos；镜像仓库: ghcr.io（Docker Hub 请改 REGISTRY）
# 本机需已登录 ghcr.io / docker hub
# ============================================================
set -euo pipefail

REGISTRY="${REGISTRY:-ghcr.io}"
GH_USER="${GH_USER:?请设置 GH_USER（如: export GH_USER=yourname）}"
TAG="${1:-v1.0.0-sealos}"

BACK_IMAGE="${REGISTRY}/${GH_USER}/dwell-backend:${TAG}"
FRONT_IMAGE="${REGISTRY}/${GH_USER}/dwell-frontend:${TAG}"

# ---- 后端：构建 ----
echo "[1/6] 构建后端镜像 ${BACK_IMAGE}"
docker build -t "${BACK_IMAGE}" -f deploy_sealos/backend/Dockerfile .

# ---- 后端：本地冒烟 ----
echo "[2/6] 后端本地冒烟（/health 与 /static/sku 示例图）"
docker rm -f dwell-smoke-back >/dev/null 2>&1 || true
docker run --rm -d -p 8000:8000 -e DEBUG=false \
  -e SKU_DB_PATH=/app/backend/data/sku.db \
  --name dwell-smoke-back "${BACK_IMAGE}"
sleep 3
curl -sf http://127.0.0.1:8000/health || { echo "后端冒烟失败：/health"; exit 1; }
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/static/sku/SKU4A001.png || true)
[ "${code}" = "200" ] || { echo "后端冒烟失败：/static 返回 ${code}（PVC 未挂载时图片目录为空属预期）"; }
docker rm -f dwell-smoke-back >/dev/null 2>&1 || true

# ---- 后端：推送 ----
echo "[3/6] 推送后端镜像"
docker push "${BACK_IMAGE}"

# ---- 前端：构建（两阶段，最终域名在构建期注入）----
echo "[4/6] 构建前端镜像 ${FRONT_IMAGE}"
# 第一次部署前未知 Sealos 分配域名，可用占位域名构建；拿到正式域名后必须重新构建：
#   docker build --build-arg NEXT_PUBLIC_API_URL=https://<正式域名> \
#     --build-arg BACKEND_URL=http://dwell-backend:8000 \
#     -t ${FRONT_IMAGE} -f deploy_sealos/frontend/Dockerfile .
FRONT_URL="${NEXT_PUBLIC_API_URL:?请设置 NEXT_PUBLIC_API_URL（最终访问域名，如 https://xxx.sealos.run）}"
BACK_URL="${BACKEND_URL:-http://dwell-backend:8000}"
docker build \
  --build-arg NEXT_PUBLIC_API_URL="${FRONT_URL}" \
  --build-arg BACKEND_URL="${BACK_URL}" \
  -t "${FRONT_IMAGE}" \
  -f deploy_sealos/frontend/Dockerfile .

# ---- 前端：本地冒烟 ----
echo "[5/6] 前端本地冒烟（/ 首页）"
docker rm -f dwell-smoke-fe >/dev/null 2>&1 || true
docker run --rm -d -p 3000:3000 --name dwell-smoke-fe "${FRONT_IMAGE}"
sleep 5
curl -sf -o /dev/null http://127.0.0.1:3000/ || { echo "前端冒烟失败：/"; exit 1; }
docker rm -f dwell-smoke-fe >/dev/null 2>&1 || true

# ---- 前端：推送 ----
echo "[6/6] 推送前端镜像"
docker push "${FRONT_IMAGE}"

echo "全部完成：${BACK_IMAGE} / ${FRONT_IMAGE}"
