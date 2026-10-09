#!/usr/bin/env bash
# ============================================================
# kubectl cp 上传数据到 PVC（方式 B）
# 前置：backend 已部署且 PVC 已挂载；本机已配置 Sealos kubeconfig
# 用法：
#   NS=<工作空间名> POD=<backend-pod名> PAYLOAD=<payload.zip绝对路径> \
#     bash deploy_sealos/scripts/upload_data_kubectl.sh
# ============================================================
set -euo pipefail

NS="${NS:?请设置 NS（Sealos 工作空间 namespace）}"
POD="${POD:?请设置 POD（backend pod 名，kubectl get pods -n \$NS 查看）}"
PAYLOAD="${PAYLOAD:?请设置 PAYLOAD（payload.zip 绝对路径）}"

echo "[1/4] 上传 payload.zip 到 pod"
kubectl cp "${PAYLOAD}" "${NS}/${POD}:/tmp/payload.zip"

echo "[2/4] 解压并写入 PVC（data + static）"
kubectl exec -n "${NS}" "${POD}" -- sh -c '
  set -e
  mkdir -p /tmp/payload
  cd /tmp/payload && unzip -o /tmp/payload.zip
  cp -f sku.db plans.db /app/backend/data/
  mkdir -p /app/backend/static
  cp -rf static/. /app/backend/static/
  echo "--- 校验 ---"
  ls -l /app/backend/data/
  echo "图片数量: $(ls -1 /app/backend/static/sku | wc -l)"
'

echo "[3/4] 重启 backend 加载新数据"
kubectl rollout restart -n "${NS}" deployment/dwell-backend
kubectl rollout status  -n "${NS}" deployment/dwell-backend --timeout=120s

echo "[4/4] 完成。建议按主文档 §6.4 执行线上校验。"
