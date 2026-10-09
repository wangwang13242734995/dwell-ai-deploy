#!/bin/sh
# ============================================================
# 数据初始化脚本（在 data-init 一次性应用内运行）
# 把 payload.zip 解压写入挂载的 PVC：
#   /mnt/data   -> dwell-data PVC（/app/backend/data）
#   /mnt/static -> dwell-static PVC（/app/backend/static）
# payload.zip 结构（由 prepare_upload.ps1 生成）：
#   sku.db、plans.db、static/sku/*.png
# ============================================================
set -e

echo "[init] 开始数据初始化 $(date -u +%FT%TZ)"
mkdir -p /tmp/payload
unzip -o /init/payload.zip -d /tmp/payload

echo "[init] 写入数据库 PVC (/mnt/data)"
mkdir -p /mnt/data
cp -f /tmp/payload/sku.db /mnt/data/sku.db
cp -f /tmp/payload/plans.db /mnt/data/plans.db

echo "[init] 写入静态图 PVC (/mnt/static)"
mkdir -p /mnt/static
cp -rf /tmp/payload/static/. /mnt/static/

# ---- 校验 ----
echo "[init] 校验："
ls -l /mnt/data/
ls -l /mnt/static/sku/ | head -5
COUNT=$(ls -1 /mnt/static/sku/ | wc -l)
echo "[init] 商品图数量: ${COUNT}"
if [ "${COUNT}" -lt 70 ]; then
  echo "[init] ERROR: 商品图数量异常 (<70)，请检查 payload.zip"
  exit 1
fi
grep -l "localhost" /mnt/data/sku.db >/dev/null 2>&1 && echo "[init] WARN: sku.db 中仍有 localhost 字样" || true
echo "[OK] data initialized"
