# ============================================================
# 本机数据准备脚本（Windows PowerShell，无需 Docker）
# 作用：
#   1) 从源码目录复制 sku.db / plans.db / static/sku -> deploy_sealos/data/payload/
#   2) 修正 sku.db 中 72 条新 SKU 的 image_url（http://localhost:8001 -> https://<最终域名>）
#   3) 校验数据完整性（SKU 行数、plans/quotes/leads 表、图片数量、localhost 残留）
#   4) 打包 payload.zip 并输出校验报告
# 用法（PowerShell 5.1+，本机需可运行 python3/python）：
#   powershell -ExecutionPolicy Bypass -File .\deploy_sealos\scripts\prepare_upload.ps1 `
#       -Domain "https://<最终域名>" -SrcRoot "temp\dwell_ai_src"
# 注意：
#   - -Domain 不要带结尾斜杠
#   - 正式域名确定后务必重跑一次本脚本，并把新 payload.zip 提交到 GitHub 仓库
#   - payload.zip 结构：sku.db、plans.db、static/sku/*.png
# ============================================================
param(
    [Parameter(Mandatory = $true)]
    [string]$Domain,          # 最终公网域名，如 https://dwell-frontend.xxxx.sealos.run
    [string]$SrcRoot = "temp\dwell_ai_src",
    [string]$OutDir  = "deploy_sealos\data"
)

$ErrorActionPreference = "Stop"

$srcBackend = Join-Path $SrcRoot "backend"
$payloadDir = Join-Path $OutDir "payload"
$zipPath    = Join-Path $OutDir "payload.zip"

if (-not (Test-Path (Join-Path $srcBackend "data\sku.db"))) {
    throw "未找到源码数据：$srcBackend\data\sku.db，请检查 -SrcRoot"
}

Write-Host "[1/4] 清理并重建 payload 目录: $payloadDir"
if (Test-Path $payloadDir) { Remove-Item -Recurse -Force $payloadDir }
New-Item -ItemType Directory -Force -Path $payloadDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $payloadDir "static\sku") | Out-Null

Write-Host "[2/4] 复制数据库与商品图"
Copy-Item (Join-Path $srcBackend "data\sku.db")   (Join-Path $payloadDir "sku.db")   -Force
Copy-Item (Join-Path $srcBackend "data\plans.db") (Join-Path $payloadDir "plans.db") -Force
Copy-Item (Join-Path $srcBackend "static\sku\*")  (Join-Path $payloadDir "static\sku\") -Force

Write-Host "[3/4] 修正 image_url -> $Domain，并校验数据完整性"
$sql = @"
import sqlite3, sys

domain = "$Domain".rstrip("/")
base = r"$payloadDir"

# ---- sku.db: 修正 image_url ----
con = sqlite3.connect(base + r"\sku.db")
cur = con.cursor()
cols = [r[1] for r in cur.execute("PRAGMA table_info(products)").fetchall()]
url_col = None
for c in cols:
    if "image_url" in c.lower():
        url_col = c
        break
if url_col is None:
    raise SystemExit("未找到 image_url 列")
cur.execute(
    "UPDATE products SET {col} = ? || substr({col}, instr({col}, '/static/')) "
    "WHERE {col} LIKE 'http://localhost:%/static/%'".format(col=url_col),
    (domain,),
)
con.commit()
n_fixed = cur.rowcount
n_left = cur.execute("SELECT count(*) FROM products WHERE image_url LIKE 'http://localhost:%'").fetchone()[0]
n_sku = cur.execute("SELECT count(*) FROM products").fetchone()[0]
con.close()

# ---- plans.db: 校验关键表存在 ----
pcon = sqlite3.connect(base + r"\plans.db")
pc = pcon.cursor()
tables = [r[0] for r in pc.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
missing = [t for t in ("plans", "quotes", "leads") if t not in tables]
if missing:
    raise SystemExit("plans.db 缺少表: %s（现有: %s）" % (",".join(missing), ",".join(tables)))
rowcounts = {}
for t in ("plans", "quotes", "leads"):
    rowcounts[t] = pc.execute("SELECT count(*) FROM " + t).fetchone()[0]
pcon.close()

# ---- 校验汇总 ----
print("fixed=%d leftover_localhost=%d sku_rows=%d plans_rows=%d quotes_rows=%d leads_rows=%d missing_tables=%s" % (
    n_fixed, n_left, n_sku, rowcounts["plans"], rowcounts["quotes"], rowcounts["leads"], ",".join(missing) if missing else "-"))
sys.exit(1 if (n_left > 0 or missing) else 0)
"@
$pyExe = $null
foreach ($cand in @("python", "python3")) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -and $_.Source -notlike "*WindowsApps*" } |
        Select-Object -First 1
    if ($cmd) { $pyExe = $cmd.Source; break }
}
if (-not $pyExe) { throw "未找到可用的 python（已排除 WindowsApps 商店 stub）" }
$pyScript = Join-Path $env:TEMP "prepare_upload_payload.py"
[System.IO.File]::WriteAllText($pyScript, $sql, [System.Text.Encoding]::UTF8)
$out = & $pyExe $pyScript 2>&1
Remove-Item -Force $pyScript -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0) {
    Write-Host "数据校验/修正失败：$out"
    throw "数据校验/修正失败"
}
Write-Host "  -> $out"

Write-Host "[4/4] 打包 payload.zip 并生成报告"
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path (Join-Path $payloadDir "*") -DestinationPath $zipPath -Force
$imgCount = (Get-ChildItem (Join-Path $payloadDir "static\sku") -Filter *.png).Count
$zipSize  = (Get-Item $zipPath).Length / 1MB

Write-Host "=========================================="
Write-Host "payload.zip 已生成: $zipPath"
Write-Host ("  大小: {0:N2} MB" -f $zipSize)
Write-Host "  商品图数量: $imgCount"
Write-Host "  校验: $out"
Write-Host "  要求: sku_rows>=105, 图片=72, localhost 残留=0, 三表存在"
Write-Host "下一步: 把 payload.zip 提交到 GitHub 仓库根 deploy_sealos/data/ 下"
Write-Host "（data-init 镜像构建或 File Browser 数据导入均使用该包）"
Write-Host "=========================================="
