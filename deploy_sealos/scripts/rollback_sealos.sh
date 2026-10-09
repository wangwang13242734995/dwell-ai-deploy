#!/usr/bin/env bash
# ============================================================
# Sealos 回滚辅助脚本（§7.2）
# 原则：先备份数据、后变更。SQLite 备份即 cp 原文件。
# 用法：
#   NS=<工作空间名> bash deploy_sealos/scripts/rollback_sealos.sh <backend|frontend|data>
#   - backend: 回滚 backend Deployment 到上一版本
#   - frontend: 回滚 frontend Deployment 到上一版本
#   - data: 仅打印数据回滚指引（需本地保留原始 sku.db/plans.db）
# ============================================================
set -euo pipefail

NS="${NS:?请设置 NS（Sealos 工作空间 namespace）}"
MODE="${1:?请指定回滚对象: backend|frontend|data}"

case "${MODE}" in
  backend)
    echo "[rollback] backend 回滚到上一镜像版本"
    kubectl -n "${NS}" rollout undo deployment/dwell-backend
    kubectl -n "${NS}" rollout status deployment/dwell-backend --timeout=120s
    echo "[rollback] 完成；如仍异常，可在控制台手动改镜像 tag 到更早版本"
    ;;
  frontend)
    echo "[rollback] frontend 回滚到上一镜像版本"
    kubectl -n "${NS}" rollout undo deployment/dwell-frontend
    kubectl -n "${NS}" rollout status deployment/dwell-frontend --timeout=120s
    echo "[rollback] 注意：旧镜像内 NEXT_PUBLIC_API_URL 必须与当前域名一致，否则需用占位域名临时回滚后二次构建"
    ;;
  data)
    echo "[rollback] 数据回滚指引（不自动执行）"
    echo "  1) 停止 backend：kubectl -n ${NS} scale deploy/dwell-backend --replicas=0"
    echo "  2) 使用本地备份（迁移前原始 sku.db/plans.db）重新生成 payload.zip"
    echo "     再执行 prepare_upload.ps1 或 kubectl cp 覆盖 PVC 文件"
    echo "  3) 恢复 backend：kubectl -n ${NS} scale deploy/dwell-backend --replicas=1"
    echo "  4) 按主文档 §6.4 校验"
    echo "  强烈建议：先 kubectl cp 导出当前 PVC 内 sku.db/plans.db 到本地再操作"
    ;;
  *)
    echo "未知模式: ${MODE}（可用: backend|frontend|data）"
    exit 1
    ;;
esac
