---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: ac383eac53e07a88a271abf849eda8fc_72c8045fbfe911f197eb525400393706
    ReservedCode1: gnCCe84A/dljWlkzZGZUxU8V8TruxHJc4GUYQrUo04/L3XCB1hMVjkVkW55w748ezmnSSrP3jELkt/RX0f8Utpphzxj3JbQOZmzFp3j/vFREWdkpjh3TbeQm6aRVd6hqCDw8e2OuLjIbH+DRVHT7uKMQEa+2pXj1vlfKlFary1/CCF4uhq1Z5sxqQeU=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: ac383eac53e07a88a271abf849eda8fc_72c8045fbfe911f197eb525400393706
    ReservedCode2: gnCCe84A/dljWlkzZGZUxU8V8TruxHJc4GUYQrUo04/L3XCB1hMVjkVkW55w748ezmnSSrP3jELkt/RX0f8Utpphzxj3JbQOZmzFp3j/vFREWdkpjh3TbeQm6aRVd6hqCDw8e2OuLjIbH+DRVHT7uKMQEa+2pXj1vlfKlFary1/CCF4uhq1Z5sxqQeU=
---

# Sealos 最短上线执行手册（GitHub Actions + Sealos Web 控制台）

> 适用：本机无 Docker daemon、无 gh/sealos CLI 登录态的环境。
> 路线：**GitHub Actions 构建镜像（ghcr.io）→ Sealos Web 控制台部署 + Web 数据导入**。
> 全程只依赖浏览器与 GitHub 网页/推送，共 **8 步**。
> 默认方案：**ghcr.io 镜像 + Sealos 分配域名 + 无 LLM key 走 Gemini 兜底**。

---

## 前置条件

- 已把项目源码（根目录含 `backend/`、`frontend/`）推送到 **GitHub 公共仓库**，并把 `deploy_sealos/` 目录放入仓库根；
- 仓库为 **public**（ghcr 包默认跟随仓库可见性，公共包 Sealos 可免凭据拉取；私有包需在 Sealos 填仓库凭据，不推荐）；
- Sealos 账号（GitHub 登录）已就绪。

---

## Step 0 · 本地生成数据包 payload.zip（1 次）

在本机（无需 Docker）执行，参数 `-Domain` 先填**暂定域名**占位（如 `https://dwell-placeholder.invalid`），拿到 Sealos 正式域名后可重跑一遍再更新镜像/数据：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy_sealos\scripts\prepare_upload.ps1 `
  -Domain "https://dwell-placeholder.invalid" -SrcRoot "temp\dwell_ai_src"
```

产出 `deploy_sealos/data/payload.zip`（含修正 image_url 后的 sku.db、plans.db[plans/quotes/leads]、static/sku 72 张图）。

把 `payload.zip` **提交并推送到 GitHub 仓库**（后续 data-init 镜像构建与数据导入都要用到）。

---

## Step 1 · GitHub Actions 自动构建镜像

```bash
git add .
git commit -m "chore: sealos deploy materials"
git tag v1.0.0
git push origin main --tags
```

Actions（`dwell-build` workflow）自动执行：
- 构建并推送 `ghcr.io/<owner>/dwell-backend:v1.0.0`（amd64 + arm64）；
- 构建并推送 `ghcr.io/<owner>/dwell-frontend:v1.0.0`（**占位域名**，下一步拿到正式域名后二次构建）。

> 若已有正式域名：先在仓库 **Settings → Secrets and variables → Actions → Variables** 设置 `FRONTEND_NEXT_PUBLIC_API_URL=https://<正式域名>`，再打 tag 构建，可跳过 Step 5 的二次构建。

**构建数据初始化镜像**（Actions → `dwell-build` → Run workflow → 勾选 build_data_init → 运行）：
- 产出 `ghcr.io/<owner>/dwell-data-init:v1.0.0`（内含 payload.zip；仅当仓库中已提交 payload.zip 才可构建）。

---

## Step 2 · Sealos 创建持久卷 PVC（2 分钟）

控制台 `cloud.sealos.io` → 登录（GitHub）→ 进入目标**工作空间** → **存储管理**：

| 名称 | 容量 | 用途 |
|---|---|---|
| `dwell-data` | 5Gi | sku.db / plans.db（SQLite） |
| `dwell-static` | 2Gi | static/sku 商品图（72 张） |

---

## Step 3 · 创建后端应用 dwell-backend

**应用管理 → 新建应用**：

| 配置项 | 值 |
|---|---|
| 应用名 | `dwell-backend` |
| 镜像 | `ghcr.io/<owner>/dwell-backend:v1.0.0`（公共包，**不填仓库凭据**） |
| 端口 | `8000`（https） |
| 公网访问 | **不开**（仅内部服务，经 frontend 同域转发） |
| 环境变量 | `DEBUG=false`；`LOG_LEVEL=INFO`；`SKU_DB_PATH=/app/backend/data/sku.db`；国内模型按需：`LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_MODEL` / `LLM_VISION_MODEL` / `LLM_IMAGE_MODEL`；**有 key 填 `LLM_API_KEY`，无 key 则不填（后端自动走 Gemini 兜底）** |
| 存储 | 添加存储：`dwell-data` → 容器路径 `/app/backend/data`；再添加：`dwell-static` → 容器路径 `/app/backend/static` |
| 资源 | 1 核 / 1Gi（默认即可） |

点击**部署应用**，等实例 Running（日志无报错）。

---

## Step 4 · Web 导入数据到 PVC（纯浏览器）

**方式 A：File Browser（推荐）**
1. **应用管理 → 新建应用**：镜像 `filebrowser/filebrowser`，应用名 `dwell-filebrowser`，端口 `80`（https），**开启公网访问**；
2. 添加存储：`dwell-data` → `/srv/data`；`dwell-static` → `/srv/static`；部署；
3. 浏览器打开分配域名，默认账号 `admin/admin`（首次登录后改密）；
4. 进入 `/srv/data`：上传 `payload.zip` → **解压**（File Browser 内置解压）→ 确认 `sku.db`、`plans.db` 就位；
5. 把 `payload.zip` 内的 `static/sku/` 整个上传/解压到 `/srv/static/`（即 `/srv/static/sku/*.png`）；
6. 校验：`/srv/data/` 有 sku.db、plans.db；`/srv/static/sku/` 有 72 张 png。

**方式 B：网页终端（备选）**
1. backend 应用详情 → 右上角菜单 → **终端**；
2. 若镜像内无 unzip：`apt-get update && apt-get install -y unzip curl`（容器为 root）；
3. 若 payload.zip 已上传到 GitHub Release：`curl -L -o /tmp/payload.zip <Release 下载 URL>`；
4. 解压到 PVC 挂载点：`cd /tmp && unzip payload.zip && cp -f sku.db plans.db /app/backend/data/ && mkdir -p /app/backend/static && cp -rf static/. /app/backend/static/`；
5. 校验同上。

> 两种方式写入的都是 PVC 挂载路径，重启/重建容器不丢数据。完成后可删除 `dwell-filebrowser` 应用（PVC 保留）。

---

## Step 5 · 创建前端应用并二次构建注入正式域名

1. **应用管理 → 新建应用**：

| 配置项 | 值 |
|---|---|
| 应用名 | `dwell-frontend` |
| 镜像 | `ghcr.io/<owner>/dwell-frontend:v1.0.0`（占位域名版，先用于拿域名） |
| 端口 | `3000`（https） |
| 公网访问 | **开启** → 部署后自动分配域名，**记下分配域名** `https://<随机>.sealos.run` |
| 环境变量 | `PORT=3000`；`HOSTNAME=0.0.0.0`；`NODE_ENV=production` |
| 存储 | 无 |

2. **二次构建注入正式域名**（二选一）：
   - A：仓库 Variables 设 `FRONTEND_NEXT_PUBLIC_API_URL=https://<分配域名>`，打新 tag `v1.0.1` push → Actions 自动构建；
   - B：Actions → `dwell-build` → Run workflow → 输入 `tag_name=v1.0.1`、`next_public_api_url=https://<分配域名>` → 运行；
   产出 `ghcr.io/<owner>/dwell-frontend:v1.0.1`。
3. 回到 frontend 应用详情 → 修改镜像为 `...dwell-frontend:v1.0.1` → **重新部署**。

---

## Step 6 · 上线验证（最短）

```bash
# 前端首页
curl -s -o /dev/null -w "%{http_code}\n" https://<分配域名>/              # 200
# 后端健康（同域转发）
curl -s https://<分配域名>/health
# 商品图（验证 static 路由 + PVC 图片）
curl -s -o /dev/null -w "%{http_code}\n" https://<分配域名>/static/sku/SKU4A001.png  # 200
# SKU 检索（验证 sku.db + image_url）
curl -s "https://<分配域名>/api/v1/sku/search?keyword=沙发" | head -c 300
```

浏览器人工点测：首页 → 拍照/草图 → 出方案 → 报价单 → 分享页 → 线索跟进（无 key 时应走 Gemini 兜底链路，确认能出方案）。

---

## Step 7 · 上线 checklist 与回滚

### Checklist
- [ ] payload.zip 校验报告通过（localhost 残留 0、图片 72、leads/quotes 表存在）
- [ ] ghcr 三个镜像（backend/frontend/data-init）均推送且包为 public
- [ ] PVC 创建完成（dwell-data 5Gi / dwell-static 2Gi）
- [ ] backend 部署，日志无报错，PVC 挂载路径正确
- [ ] 数据导入完成：sku.db 105 条、plans.db 含 plans/quotes/leads、72 张图就位
- [ ] frontend 二次构建注入正式域名并更新
- [ ] Step 6 全部通过（/、/health、/static、/api/v1、人工链路）
- [ ] 记录：分配域名、镜像 tag、工作空间名

### 回滚（Web 操作，无需 CLI）
| 场景 | 动作 |
|---|---|
| 数据错误 | File Browser 上传覆盖 `sku.db`/`plans.db`（先下载备份当前文件）→ backend 重启（改镜像 tag 触发重部署或删建应用） |
| 后端异常 | backend 应用详情 → 改镜像 tag 到上一版本（或删除重建，PVC 数据不丢） |
| 前端异常 | 改 frontend 镜像 tag；旧镜像的 NEXT_PUBLIC_API_URL 必须与当前域名一致（域名换了则用占位域名版临时回滚+重新二次构建） |
| 域名异常 | 解绑/换自定义域名只需重新二次构建 frontend |
| 整体 | 删除两应用即可（PVC 保留）；彻底下线再删 PVC（先备份数据） |

---

## 交付物索引（output/deploy_sealos/）

| 文件 | 说明 |
|---|---|
| `.github/workflows/dwell-build.yml` | GitHub Actions：tag v* 自动构建 backend/frontend；手动触发二次构建与 data-init |
| `scripts/prepare_upload.ps1` | 本地生成 payload.zip（参数化域名 + image_url 修正 + 数据校验） |
| `data/init-data.Dockerfile` + `data/init_data.sh` | data-init 镜像（可选数据导入通道，与 File Browser 二选一） |
| `backend/Dockerfile`、`frontend/Dockerfile`、`frontend/next.config.production.ts` | 镜像构建源 |
| `k8s/backend.yaml`、`k8s/frontend.yaml` | K8s 清单（可选，Web 手动创建更简） |
| `scripts/rollback_sealos.sh` | CLI 回滚辅助（本机无 CLI 时以 Step 7 Web 回滚为准） |
| `.env.sealos.example` | 后端环境变量清单 |

> 本手册为纯本地产出，未在云端执行任何操作。
*（内容由AI生成，仅供参考）*
