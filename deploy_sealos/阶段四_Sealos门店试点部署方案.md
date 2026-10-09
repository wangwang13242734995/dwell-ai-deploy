---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: ac383eac53e07a88a271abf849eda8fc_92d7a760bda711f18019525400248c00
    ReservedCode1: dt2ZoORHIa7BHmMmQaOFtxWN1su2ykKdoU+GCg3ZPb2H+Lq/38pfLn0jNo9R2LbHh310y2sXVQVQNPbRQ/JOqTs+R5EN1JUELp+nVW8ZwpLj9Xk6gE3lmsnD6CjCFv1E0Ghp4rDy35gTmmOdvCIaqytCC5FJjcaxgTXj5F1zuX3DQ6jA6y++5V10Uh8=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: ac383eac53e07a88a271abf849eda8fc_92d7a760bda711f18019525400248c00
    ReservedCode2: dt2ZoORHIa7BHmMmQaOFtxWN1su2ykKdoU+GCg3ZPb2H+Lq/38pfLn0jNo9R2LbHh310y2sXVQVQNPbRQ/JOqTs+R5EN1JUELp+nVW8ZwpLj9Xk6gE3lmsnD6CjCFv1E0Ghp4rDy35gTmmOdvCIaqytCC5FJjcaxgTXj5F1zuX3DQ6jA6y++5V10Uh8=
---

# 阶段四 · Sealos 门店试点部署方案

> 适用范围：家具门店 AI 导购系统门店试点上线（改用 **Sealos 云平台**路线）。
> 前提：用户已有 Sealos 账号（GitHub 登录）；**不使用** xingguangzl.top 域名。
> 本文档为**纯本地产出**，所有脚本/配置文件仅为交付，**未在服务器/云端执行**；实际部署前须确认账户可用区、配额、镜像仓库账号等。

---

## 0. 部署架构总览（Sealos 上）

```
                    ┌─────────────────────── Sealos Cloud ───────────────────────┐
                    │  工作空间（GitHub 登录）                                    │
 浏览器             │                                                           │
 ─── https://xxx.sealos.run ──► Ingress（Sealos 自动域名 + 自动 HTTPS）          │
   (frontend域名)   │    /              → dwell-frontend (Next standalone:3000) │
                    │    /api/v1/*      → dwell-backend  (FastAPI:8000)         │
                    │    /health        → dwell-backend  (FastAPI:8000)         │
                    │    /static/*      → dwell-backend  (FastAPI:8000)         │
                    │                                                           │
                    │  dwell-frontend（Deployment 1实例，standalone node）       │
                    │  dwell-backend（Deployment 1实例，uvicorn 多进程）         │
                    │     ├─ PVC dwell-data    → /app/backend/data  (sku.db/plans.db) │
                    │     └─ PVC dwell-static  → /app/backend/static (商品图 72张)     │
                    └───────────────────────────────────────────────────────────┘
```

- 两个独立应用（应用管理 App Launchpad）：`dwell-frontend`、`dwell-backend`；
- 均启用**公网访问**，Sealos 自动分配 `*.sealos.run` 域名并自动签发/续期 HTTPS；
- 后端仅通过 Ingress 暴露 `/api/v1`、`/health`、`/static`，前端与后端**同域**，浏览器无跨域；
- 后端容器内监听 `0.0.0.0:8000`（与 `main.py` 默认端口一致），由 Sealos Ingress 转发；
- 数据持久化：SQLite（sku.db、plans.db）与商品图分别挂独立 PVC（见 §3.3）。

### 0.1 与现有代码的适配点（已核对源码）

| 项目 | 现状 | Sealos 处置 |
|---|---|---|
| `backend/app/main.py` | 挂载 `/static` → `backend/static`（72 张图）；10 个 router 均在 `/api/v1`；`/health` 在根路径 | Ingress 按路径转发即可；后端镜像需 `uvicorn --host 0.0.0.0` |
| `backend/app/config.py` | `debug=True` 默认、CORS 仅 localhost；`sku_db_path` 可覆盖 | 环境变量 `DEBUG=false`、`SKU_DB_PATH=/app/backend/data/sku.db` |
| `backend/app/store/db.py` | `sku_db_path` 为空时默认 `backend/data/sku.db` | 显式设置指向 PVC |
| `backend/app/store/plans.py` | plans.db 与 sku.db 同目录（由 `sku_db_path` 推导） | 同一 PVC 挂 `/app/backend/data` 即可覆盖 |
| `frontend/next.config.ts` | **未配置 standalone** | 构建前替换为 `deploy_sealos/frontend/next.config.production.ts`（`output: "standalone"`） |
| `frontend/src/lib/api.ts` | `NEXT_PUBLIC_API_URL` 默认 `http://localhost:8001` | 构建时注入最终公网域名（见 §3.4 两阶段构建） |
| **image_url 风险点** | 72 条新 SKU 硬编码 `http://localhost:8001/static/sku/*.png` | 迁移前修正为最终 Sealos 域名（见 §5.2） |

---

## 1. 前置准备

1. **Sealos 账号**：GitHub 登录 `cloud.sealos.io` → 创建/进入目标**工作空间**（确认可用区，如国内区/国际区）；
2. **镜像仓库**（二选一，需可公网拉取）：
   - **ghcr.io**（推荐，GitHub 账号即可）：`docker login ghcr.io --username <GH_USER>`（Personal Access Token 需 `write:packages`）；
   - **Docker Hub**：`docker login`；
3. **本地构建环境**：Docker（或 podman）+ 已 clone/放置源码 `temp/dwell_ai_src`；
4. 确认配额：两个应用各 1~2 核 / 1~2Gi 内存即可；两个 PVC（data 5Gi、static 2Gi）。

---

## 2. ① Sealos 应用部署流程（官方调研结论）

来源：Sealos 官方文档（sealos.io / sealos.run）与社区实践（2026）。要点：

| 能力 | 结论 |
|---|---|
| **部署入口** | ① 控制台「应用管理」→ 创建应用（填镜像、资源、端口、环境变量、存储、公网访问）；② CLI `sealos apply -f app.yaml`（兼容标准 K8s 清单）；③ 应用商店模板（不适用本项目，需自构建镜像） |
| **镜像要求** | 固定 tag（不用 latest）；应用监听 `0.0.0.0`；明确业务端口；本地先 `docker run` 冒烟 |
| **公网域名** | 启用「公网访问」后自动分配 `*.sealos.run` 子域名并自动 HTTPS（如 `dwell-backend.xxxx.sealos.run`），无需自管证书/nginx |
| **持久卷 PVC** | 应用详情「存储管理」新增存储：填容器内数据目录绝对路径 + 容量，保存后重部署；重启/重建后数据保留 |
| **环境变量** | 应用高级配置中逐项填写；密钥建议用 Secret；变量名与值格式敏感（`KEY=value`） |
| **自定义域名** | DNS 加 CNAME → 指向 Sealos 公网地址 → 应用详情绑定自定义域名 → 自动签证书；**大陆节点需 ICP 备案** |
| **排障** | 控制台看日志；进阶 `kubectl -n <ns> get pods / logs` |

> Sealos 的 K8s 服务名规则：应用名即 Service 名，同一工作空间（namespace）内可直接用 `http://<应用名>:<端口>` 互访；跨 namespace 用 `<应用名>.<namespace>.svc.cluster.local:<端口>`。下文 `BACKEND_URL=http://dwell-backend:8000` 即基于此。

---

## 3. ② 容器化（Dockerfile + 构建/冒烟/推送）

### 3.1 后端镜像 `deploy_sealos/backend/Dockerfile`

要点：`python:3.11-slim`；复制 `backend/`；`WORKDIR /app/backend`；`CMD uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --limit-max-requests 10000`；
数据目录 `data/` 与图片目录 `static/` **不写入镜像**（由 PVC 挂载），镜像内保留空目录占位。

### 3.2 前端镜像 `deploy_sealos/frontend/Dockerfile`

要点：多阶段构建（`node:20-alpine`）：deps → builder（`npm ci` + 替换 standalone 配置 + `npm run build`）→ runner（复制 `.next/standalone` + `.next/static` + `public`）；`CMD node server.js`，`PORT=3000 HOSTNAME=0.0.0.0`。

> ⚠️ **两阶段构建**：`NEXT_PUBLIC_API_URL` 在**构建期**写入 JS，而 Sealos 分配域名在部署后才可知。流程：
> 1. 第一次构建用占位域名（如 `https://placeholder.example`）部署 frontend → 拿到 Sealos 分配域名 `https://<app>.sealos.run`；
> 2. 第二次构建注入**最终域名**（分配域名或自定义域名）→ 重新推送/更新 frontend 镜像；
> （可选优化：后续把 `api.ts` 改为同域相对路径请求，可免二次构建，属代码改动不在本次范围。）

### 3.3 构建、本地冒烟、推送命令（交付 `deploy_sealos/build_push.sh`）

```bash
# ===== 后端 =====
docker build -t ghcr.io/<GH_USER>/dwell-backend:v1.0.0-sealos \
  -f deploy_sealos/backend/Dockerfile .

# 本地冒烟（后端）
docker run --rm -d -p 8000:8000 -e DEBUG=false \
  -e SKU_DB_PATH=/app/backend/data/sku.db \
  --name dwell-smoke-back ghcr.io/<GH_USER>/dwell-backend:v1.0.0-sealos
curl -s http://127.0.0.1:8000/health          # {"status":"ok",...}
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/static/sku/SKU4A001.png  # 200
docker stop dwell-smoke-back

# 推送
docker push ghcr.io/<GH_USER>/dwell-backend:v1.0.0-sealos

# ===== 前端（第二次构建时替换 NEXT_PUBLIC_API_URL 为最终域名）=====
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://<最终域名> \
  --build-arg BACKEND_URL=http://dwell-backend:8000 \
  -t ghcr.io/<GH_USER>/dwell-frontend:v1.0.0-sealos \
  -f deploy_sealos/frontend/Dockerfile .

docker run --rm -d -p 3000:3000 --name dwell-smoke-fe \
  ghcr.io/<GH_USER>/dwell-frontend:v1.0.0-sealos
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000/   # 200
docker stop dwell-smoke-fe

docker push ghcr.io/<GH_USER>/dwell-frontend:v1.0.0-sealos
```

---

## 4. ③ Sealos 部署编排

### 4.1 后端应用 `dwell-backend`

| 配置项 | 值 |
|---|---|
| 镜像 | `ghcr.io/<GH_USER>/dwell-backend:v1.0.0-sealos` |
| 容器端口 | `8000`（协议 https） |
| 实例数 | 1（试点；如流量大再扩） |
| 资源 | 1~2 核 / 1~2Gi |
| 公网访问 | **启用**（自动域名；`/health`、`/static`、`/api/v1`、`/docs` 均由其代理） |
| 环境变量 | `DEBUG=false`；`LOG_LEVEL=INFO`；`SKU_DB_PATH=/app/backend/data/sku.db`；`LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` / `LLM_VISION_MODEL` / `LLM_IMAGE_MODEL`（国内模型，密钥放 Secret 更佳） |
| 存储 1 | PVC `dwell-data`（5Gi）→ 挂载 `/app/backend/data`（sku.db / plans.db） |
| 存储 2 | PVC `dwell-static`（2Gi）→ 挂载 `/app/backend/static`（商品图 72 张） |

**uvicorn 多进程**：镜像 CMD 已含 `--workers 4 --limit-max-requests 10000`；单实例内多进程即可满足试点并发，Sealos 层无需多副本（SQLite 也不建议多副本写）。

### 4.2 前端应用 `dwell-frontend`

| 配置项 | 值 |
|---|---|
| 镜像 | `ghcr.io/<GH_USER>/dwell-frontend:v1.0.0-sealos`（第二次构建产物） |
| 容器端口 | `3000`（协议 https） |
| 实例数 | 1 |
| 资源 | 0.5~1 核 / 1Gi |
| 公网访问 | **启用** |
| 环境变量 | `PORT=3000`；`HOSTNAME=0.0.0.0`；`NODE_ENV=production`（`NEXT_PUBLIC_API_URL` 已构建期注入，无需运行时设置） |
| 存储 | 无（无本地写入） |

**`BACKEND_URL` 说明**：前端 standalone 的服务端 rewrite（`next.config.production.ts`）目标设为 **`http://dwell-backend:8000`**（Sealos 内网服务名）；浏览器侧的 `/api/v1/*`、`/health`、`/static/*` 请求经 Ingress 同域直达 backend，不走 rewrite。

### 4.3 PVC 与数据布局

```
PVC dwell-data (5Gi)  →  /app/backend/data
    ├── sku.db        （SKU 105 条，含修正后的 image_url）
    └── plans.db      （方案/报价单/线索）
PVC dwell-static (2Gi) →  /app/backend/static
    └── sku/*.png     （72 张商品图）
```

- 后端 `plans.py` 按 `sku_db_path` 同目录推导 plans.db，因此两个库在同一 PVC 目录即可同时持久化；
- 后端 `main.py` 静态目录解析为 `backend/static`，与 PVC 挂载点一致；
- 数据迁移上传见 §5。

### 4.4 CLI 方式（可选）：交付 `deploy_sealos/k8s/backend.yaml` / `frontend.yaml`

标准 K8s 资源清单（Deployment + Service + PVC），可 `kubectl apply` 或 `sealos apply -f`：
- `backend.yaml`：Deployment（镜像/env/PVC 挂载）+ Service（8000）+ 2 个 PVC；
- `frontend.yaml`：Deployment（镜像/env）+ Service（3000）；
- 公网 Ingress 由 Sealos 控制台「启用公网访问」自动创建（域名在控制台查看），也可按需自行提交 Ingress。

> 推荐新手走**控制台 UI**（§4.1/§4.2 表单），YAML 供熟悉 K8s 的团队与自动化使用。

---

## 5. ④ 域名策略

### 5.1 默认：Sealos 分配域名（推荐试点）

- 启用公网访问后，控制台为每个应用分配 `https://<随机前缀>.sealos.run`，自动 HTTPS；
- **前端最终域名** = frontend 应用的分配域名（构建 `NEXT_PUBLIC_API_URL` 用）；
- 后端分配域名仅用于排障直连（正常流量经 frontend 同域）。

### 5.2 可选：绑定自有域名（CNAME）

1. 应用详情页确认 Sealos 已分配公网地址（如 `dwell-frontend.xxxx.sealos.run`）；
2. DNS 服务商添加记录：
   ```
   记录类型: CNAME
   主机记录: ai         （或 @）
   记录值:   dwell-frontend.xxxx.sealos.run
   ```
3. 等待解析生效（几分钟）；
4. 应用详情 → 「自定义域名」→ 输入 `ai.你的域名.com` → 保存/部署；
5. Sealos 自动签发该域名 SSL 证书；之后需**重新构建前端**注入 `NEXT_PUBLIC_API_URL=https://ai.你的域名.com` 并更新镜像。

> ⚠️ 若 Sealos 节点位于中国大陆，自定义域名需完成 **ICP 备案**（备案云厂商需与可用区一致）；绑定前请确认。

---

## 6. ⑤ 数据迁移（本地 → Sealos）

### 6.1 迁移内容

| 数据 | 来源 | 目标 |
|---|---|---|
| `sku.db`（105 条） | `temp/dwell_ai_src/backend/data/sku.db` | PVC `dwell-data` → `/app/backend/data/sku.db` |
| `plans.db` | 同目录 | PVC `dwell-data` → `/app/backend/data/plans.db` |
| `static/sku/*.png`（72 张） | `temp/dwell_ai_src/backend/static/sku/` | PVC `dwell-static` → `/app/backend/static/sku/` |

### 6.2 修正 image_url（必做）

72 条新 SKU 的 `image_url` 硬编码为 `http://localhost:8001/static/sku/*.png`，浏览器无法访问。迁移前执行本机脚本（交付 `deploy_sealos/scripts/prepare_upload.ps1`）：

```powershell
# 用法（PowerShell，参数为最终域名）
.\deploy_sealos\scripts\prepare_upload.ps1 -Domain "https://<最终域名>"
# 自动完成：
#   1) 复制 sku.db/plans.db/static/sku → deploy_sealos/data/payload/
#   2) 用 sqlite3 将 sku.db 的 image_url 修正为 https://<最终域名>/static/sku/{id}.png
#   3) 打包 payload.zip 并输出校验报告（修正行数/残留 localhost 数/图片数量）
```

> 服务器端应急修正 SQL 见 `deploy_sealos/scripts/fix_image_url.sql`（带 `@DOMAIN` 占位），仅当线上数据需再改域名时使用。

### 6.3 上传到持久卷（两种方式）

**方式 A：一次性数据初始化镜像（推荐，UI 可操作）**
交付 `deploy_sealos/data/init-data.Dockerfile` + `init_data.sh`：
1. 本地把 `payload.zip` 打进 `ghcr.io/<GH_USER>/dwell-data-init:v1.0.0` 并推送；
2. Sealos 创建一次性应用 `dwell-data-init`：挂载 `dwell-data` → `/mnt/data`、`dwell-static` → `/mnt/static`，启动命令运行 `init_data.sh`（解压 payload.zip 到挂载目录并校验）；
3. 日志显示 `[OK] data initialized` 后删除该应用（PVC 保留）。

**方式 B：kubectl cp（CLI）**
1. 先部署 backend（PVC 已挂载，镜像启动即可）；
2. 上传：`kubectl cp payload.zip <ns>/<backend-pod>:/tmp/` → `kubectl exec` 解压到 `/app/backend/data` 与 `/app/backend/static`；
3. 重启 backend pod 使其加载新数据。

> 首次部署顺序建议：先创建 PVC/backend 应用（空数据可启动）→ 执行数据初始化 → 再部署 frontend（第二次构建注入域名）→ 校验。

### 6.4 校验清单（迁移后）

```bash
# 1) 后端健康
curl -s https://<frontend域名>/health
# 2) SKU 总数与品类
curl -s "https://<frontend域名>/api/v1/sku/admin/categories"
# 3) image_url 已修正（应无 localhost 残留）
# 4) 商品图全部 200
for f in SKU4A001 SKU4A002 SKU4A010; do
  curl -s -o /dev/null -w "$f %{http_code}\n" "https://<frontend域名>/static/sku/$f.png"
done
# 5) 门店链路：/ 首页、/admin/sku、/share/[planId]、报价单、线索接口人工点测
```

---

## 7. ⑥ 上线 checklist 与回滚

### 7.1 上线 checklist

**准备期**
- [ ] Sealos 工作空间与配额确认（2 应用 / 2 PVC / 镜像仓库登录）
- [ ] 镜像构建完成并推送（backend；frontend 两阶段）
- [ ] `prepare_upload.ps1 -Domain <最终域名>` 生成 payload.zip，校验报告通过（残留 localhost=0、图片 72）
- [ ] payload.zip 已打包进 data-init 镜像并推送（或 kubectl cp 材料就绪）

**部署期**
- [ ] 创建 PVC（dwell-data 5Gi、dwell-static 2Gi）与 backend 应用（env 全、PVC 挂载正确）
- [ ] 数据初始化完成（data-init 日志 OK；backend pod 可读 sku.db 105 条）
- [ ] 后端 `/health` 200；`/static/sku/SKU4A001.png` 200
- [ ] frontend 第一次构建部署 → 获取分配域名 → 第二次构建注入最终域名 → 更新 frontend 镜像
- [ ] `https://<最终域名>/` 首页 200；`/admin/sku`、`/share/x` 200；图片/API 同域可用
- [ ] 国内模型真实调用抽测（LLM_API_KEY 已配）：analyze / plan / quote / leads 全链路
- [ ] 自动 HTTPS 证书无告警

**运维期**
- [ ] 记录两个应用分配域名、命名空间、镜像 tag
- [ ] PVC 容量监控（data 5Gi / static 2Gi）；Sealos 计费账单确认
- [ ] 定期备份 PVC 内 sku.db / plans.db（`kubectl cp` 或控制台导出）

### 7.2 回滚方案

| 场景 | 动作 |
|---|---|
| **数据回滚（最优先）** | 迁移前在本地备份原始 `sku.db`/`plans.db`；线上误操作时：停止 backend → 用备份重建 payload → 重跑 data-init（或 kubectl cp 覆盖）→ 重启 backend |
| **后端回滚** | 保留上一镜像 tag（如 `v1.0.0-sealos` vs `v0.9.0-sealos`）：控制台改镜像 tag 重新部署；CLI：`kubectl -n <ns> rollout undo deployment/dwell-backend` |
| **前端回滚** | 同理切换 frontend 镜像 tag（旧构建的 NEXT_PUBLIC_API_URL 需与当前域名一致，否则需用占位域名临时回滚+二次构建） |
| **域名回滚** | 解绑自定义域名（保留 Sealos 分配域名始终可用）；删除 CNAME 记录 |
| **整体回滚** | 删除两个应用与 PVC 前，先用 `kubectl cp` 导出 PVC 内 sku.db/plans.db/static 到本地备份 |

> 原则：**先数据备份、后变更**；SQLite 单文件，备份即 `cp`，最可靠的回滚就是保留原始文件。

---

## 8. 交付物清单（output/deploy_sealos/）

| 文件 | 用途 |
|---|---|
| `阶段四_Sealos门店试点部署方案.md` | 本文档 |
| `backend/Dockerfile` + `backend/.dockerignore` | 后端镜像（§3.1） |
| `frontend/Dockerfile` + `frontend/.dockerignore` + `frontend/next.config.production.ts` | 前端镜像/配置（§3.2） |
| `build_push.sh` | 构建+冒烟+推送（§3.3） |
| `k8s/backend.yaml`、`k8s/frontend.yaml` | Sealos/K8s 资源清单（§4.4） |
| `data/init-data.Dockerfile`、`data/init_data.sh` | 数据初始化镜像（§6.3 方式 A） |
| `scripts/prepare_upload.ps1` | 本机打包+image_url 修正（§6.2） |
| `scripts/fix_image_url.sql` | 服务器端 image_url 应急修正（§6.2） |
| `scripts/upload_data_kubectl.sh` | kubectl cp 上传（§6.3 方式 B） |
| `scripts/rollback_sealos.sh` | 回滚辅助脚本（§7.2） |
| `.env.sealos.example` | Sealos 后端环境变量清单（§4.1） |

> 以上脚本均为**待执行模板**：镜像仓库用户名、最终域名、LLM_API_KEY 等需在操作时按实填写。本机**不执行**任何部署操作。
*（内容由AI生成，仅供参考）*
