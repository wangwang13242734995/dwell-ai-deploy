-- ============================================================
-- 服务器端 image_url 应急修正（仅当线上 sku.db 仍含 localhost 时使用）
-- 执行前把 @DOMAIN 替换为最终公网域名（不含 https://，末尾不带 /）
-- 例：UPDATE products ... 'https://' || 'dwell-frontend.xxxx.sealos.run' || ...
-- ============================================================
UPDATE products
SET image_url = 'https://' || '@DOMAIN' || substr(image_url, instr(image_url, '/static/'))
WHERE image_url LIKE 'http://localhost:%/static/%';

-- 校验：修正行数（期望 72）
SELECT 'fixed_rows' AS k, count(*) AS v
FROM products
WHERE image_url NOT LIKE 'http://localhost:%' AND image_url LIKE '%/static/sku/%';

-- 校验：残留 localhost（期望 0）
SELECT 'leftover_localhost' AS k, count(*) AS v
FROM products
WHERE image_url LIKE 'http://localhost:%';
