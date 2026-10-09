# ============================================================
# 数据初始化镜像（可选数据导入通道，与 File Browser 二选一）
# 构建（上下文=仓库根，需 deploy_sealos/data/payload.zip 已存在）：
#   docker build -t ghcr.io/<GH_USER>/dwell-data-init:v1.0.0 \
#     -f deploy_sealos/data/init-data.Dockerfile .
# 或由 GitHub Actions 手动触发 build_data_init job 自动构建
# Sealos 使用：创建一次性应用 dwell-data-init，挂载
#   dwell-data   -> /mnt/data
#   dwell-static -> /mnt/static
# 日志显示 [OK] 后删除该应用（PVC 保留数据）。
# ============================================================
FROM alpine:3.19
RUN apk add --no-cache unzip
WORKDIR /init
COPY deploy_sealos/data/payload.zip ./payload.zip
COPY deploy_sealos/data/init_data.sh ./init_data.sh
ENTRYPOINT ["/bin/sh", "/init/init_data.sh"]
