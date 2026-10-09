# dwell-backend 镜像（Sealos 部署）
# 构建：docker build -t ghcr.io/<GH_USER>/dwell-backend:v1.0.0 -f deploy_sealos/backend/Dockerfile .
# 或由 GitHub Actions（.github/workflows/dwell-build.yml）自动构建
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBUG=false \
    LOG_LEVEL=INFO

WORKDIR /app

# 先装依赖（利用层缓存）
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY backend/ ./backend/

WORKDIR /app/backend

# 数据目录与静态目录由 PVC 挂载，镜像内仅保留空目录占位
RUN mkdir -p /app/backend/data /app/backend/static

EXPOSE 8000

# 多进程 uvicorn：试点单实例内 4 workers，--limit-max-requests 防内存泄漏长驻
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--limit-max-requests", "10000"]
