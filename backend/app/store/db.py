"""
SKU 数据库访问层

基于 SQLite 的门店商品库。字段说明：
- id / name / category / subcategory / material / color / style
- dim_w / dim_d / dim_h / unit：尺寸（cm）
- price：人民币售价
- stock：库存数量
- lead_time_days：交付周期（现货=0 或 5/7/10/15/20 天）
- space_tags：适用空间（客厅|卧室|餐厅|书房|玄关|软装）
- keywords：检索关键词（品类/材质/风格/颜色）
"""

import os
import sqlite3
from functools import lru_cache
from typing import Dict, List, Optional, Any

from app.config import get_settings

# 英文 label → 中文品类关键词映射（Dwell_AI 布局对象 label 常见取值）
LABEL_MAP = {
    "bed": ["床"],
    "sofa": ["沙发"],
    "armchair": ["单人沙发", "休闲椅", "沙发"],
    "desk": ["书桌", "桌"],
    "study desk": ["书桌"],
    "chair": ["餐椅", "椅"],
    "dining table": ["餐桌"],
    "dining chair": ["餐椅"],
    "table": ["餐桌", "茶几", "书桌"],
    "coffee table": ["茶几"],
    "side table": ["边几", "茶几"],
    "end table": ["边几"],
    "nightstand": ["床头柜"],
    "wardrobe": ["衣柜", "柜"],
    "closet": ["衣柜"],
    "cabinet": ["餐边柜", "斗柜", "柜"],
    "dresser": ["斗柜", "梳妆台"],
    "chest": ["斗柜", "柜"],
    "tv stand": ["电视柜"],
    "media console": ["电视柜"],
    "bookshelf": ["书架"],
    "bookcase": ["书架"],
    "rug": ["地毯"],
    "carpet": ["地毯"],
    "plant": ["绿植"],
    "floor lamp": ["落地灯", "灯"],
    "lamp": ["灯"],
    "pendant light": ["灯"],
    "artwork": ["装饰画"],
    "painting": ["装饰画"],
    "decor": ["装饰画", "抱枕"],
    "pillow": ["抱枕"],
    "cushion": ["抱枕"],
    "mirror": ["镜"],
    "curtain": ["窗帘"],
    "shoe cabinet": ["鞋柜"],
    "entryway table": ["玄关桌"],
    "bench": ["换鞋凳"],
    "stool": ["换鞋凳", "餐椅"],
    "storage": ["柜", "斗柜"],
    "shelf": ["书架", "置物架"],
    "lamp": ["灯"],
    "ottoman": ["换鞋凳", "沙发"],
    "lounge": ["单人沙发", "休闲椅"],
    "recliner": ["单人沙发", "休闲椅"],
}


def _db_path() -> str:
    """定位 SKU 数据库文件（backend/data/sku.db）。"""
    settings = get_settings()
    if settings.sku_db_path:
        return settings.sku_db_path
    # 默认取 backend/data/sku.db（相对 config 所在包向上两级）
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "data", "sku.db")


def _connect() -> sqlite3.Connection:
    db = _db_path()
    if not os.path.exists(db):
        raise FileNotFoundError(
            f"SKU 数据库不存在：{db}。请先运行 scripts/init_sku_db.py 初始化门店商品库。"
        )
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    # 尺寸/价格转成便于前端展示的结构
    d["dimensions"] = {
        "w": d.pop("dim_w", None),
        "d": d.pop("dim_d", None),
        "h": d.pop("dim_h", None),
        "unit": d.pop("unit", "cm"),
    }
    d["space_list"] = [s.strip() for s in (d.get("space_tags") or "").split("|") if s.strip()]
    return d


@lru_cache(maxsize=8)
def get_categories() -> List[Dict[str, Any]]:
    """返回品类列表及每个品类的商品数。"""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT category, COUNT(*) AS cnt FROM products GROUP BY category ORDER BY cnt DESC"
        ).fetchall()
        return [{"category": r["category"], "count": r["cnt"]} for r in rows]
    finally:
        conn.close()


def search_products(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    space: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    in_stock: bool = False,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    按关键词/品类/空间/预算检索 SKU。

    keyword 会同时模糊匹配 name / keywords / material / color / style / subcategory；
    多个词按空格拆分，任一命中即返回（OR 语义）。
    """
    conn = _connect()
    try:
        clauses: List[str] = []
        params: List[Any] = []

        if keyword:
            terms = [t.strip() for t in keyword.replace("，", " ").replace(",", " ").split() if t.strip()]
            if terms:
                like_clauses = []
                for term in terms:
                    like_clauses.append(
                        "(name LIKE ? OR keywords LIKE ? OR material LIKE ? OR color LIKE ? OR style LIKE ? OR subcategory LIKE ?)"
                    )
                    for _ in range(6):
                        params.append(f"%{term}%")
                clauses.append("(" + " OR ".join(like_clauses) + ")")

        if category:
            clauses.append("category = ?")
            params.append(category)

        if space:
            clauses.append("space_tags LIKE ?")
            params.append(f"%{space}%")

        if max_price is not None:
            clauses.append("price <= ?")
            params.append(max_price)

        if min_price is not None:
            clauses.append("price >= ?")
            params.append(min_price)

        if in_stock:
            clauses.append("stock > 0")

        sql = "SELECT * FROM products"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY stock DESC, price ASC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


def match_label_to_keywords(label: str) -> List[str]:
    """把布局对象 label（如 'bed' / 'sofa'）转成中文品类关键词列表。"""
    key = (label or "").strip().lower()
    if not key:
        return []
    # 优先精确匹配
    if key in LABEL_MAP:
        return LABEL_MAP[key]
    # 其次做包含匹配（如 'dining table 6 seats' → 'table'）
    for k, v in LABEL_MAP.items():
        if k in key:
            return v
    # 兜底：用 label 本身作为关键词（前端中文 label 可直接命中）
    return [label]


def get_product_by_id(product_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return row_to_dict(row) if row else None
    finally:
        conn.close()


class SKUStore:
    """面向购物 Agent 的门店 SKU 检索门面。"""

    def search(
        self,
        query: str,
        max_price: Optional[float] = None,
        num_results: int = 3,
        label: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # 优先用 query 关键词搜索
        results = search_products(keyword=query, max_price=max_price, limit=num_results)
        if results:
            return results
        # 无结果时按 label 映射再搜
        if label:
            for kw in match_label_to_keywords(label):
                results = search_products(keyword=kw, max_price=max_price, limit=num_results)
                if results:
                    return results
        return []

    def plan_for_layout(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        根据布局中的移动家具清单生成「可成交方案」：
        每件家具选 1 个匹配 SKU，汇总总价、最大交付周期、缺货提示。
        """
        plan_items = []
        total = 0.0
        max_lead = 0
        out_of_stock = 0
        for item in items:
            label = item.get("label", "")
            query = item.get("search_query") or label
            budget = item.get("budget")
            products = self.search(query=query, max_price=budget, num_results=1, label=label)
            if not products:
                plan_items.append({
                    "furniture_id": item.get("id", ""),
                    "furniture_label": label,
                    "matched": False,
                    "products": [],
                })
                continue
            p = products[0]
            total += p["price"]
            max_lead = max(max_lead, p["lead_time_days"] or 0)
            if not (p.get("stock") or 0) > 0:
                out_of_stock += 1
            plan_items.append({
                "furniture_id": item.get("id", ""),
                "furniture_label": label,
                "matched": True,
                "products": products,
            })
        return {
            "items": plan_items,
            "total_price_cny": round(total, 2),
            "max_lead_time_days": max_lead,
            "out_of_stock_count": out_of_stock,
            "matched_count": sum(1 for i in plan_items if i["matched"]),
        }


# === P1：SKU 管理后台（复用 products 表，仅新增管理方法，不影响既有检索/方案接口） ===

PRODUCT_COLUMNS = [
    "id", "name", "category", "subcategory", "material", "color", "style",
    "dim_w", "dim_d", "dim_h", "unit", "price", "stock", "lead_time_days",
    "space_tags", "keywords", "image_url",
]


def _clear_cache() -> None:
    """管理端写操作后清除品类统计缓存，保证 /sku/categories 实时。"""
    get_categories.cache_clear()


def _normalize_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """把 API 载荷规整为 products 表字段字典。"""
    values = {
        "name": (data.get("name") or "").strip(),
        "category": (data.get("category") or "").strip(),
        "subcategory": (data.get("subcategory") or "").strip(),
        "material": (data.get("material") or "").strip(),
        "color": (data.get("color") or "").strip(),
        "style": (data.get("style") or "").strip(),
        "dim_w": data.get("dim_w"),
        "dim_d": data.get("dim_d"),
        "dim_h": data.get("dim_h"),
        "unit": (data.get("unit") or "cm").strip(),
        "price": float(data.get("price") or 0),
        "stock": int(data.get("stock") or 0),
        "lead_time_days": int(data.get("lead_time_days") or 7),
        "space_tags": (data.get("space_tags") or "").strip(),
        "keywords": (data.get("keywords") or "").strip(),
        "image_url": (data.get("image_url") or "").strip(),
    }
    if not values["name"]:
        raise ValueError("商品名称不能为空")
    if not values["category"]:
        raise ValueError("商品品类不能为空")
    if values["price"] < 0:
        raise ValueError("价格不能为负数")
    if values["stock"] < 0:
        raise ValueError("库存不能为负数")
    if values["lead_time_days"] < 0:
        raise ValueError("交付周期不能为负数")
    return values


def list_products_paged(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    space: Optional[str] = None,
    in_stock: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """分页查询 SKU（管理后台列表）。筛选逻辑与 search_products 一致。"""
    conn = _connect()
    try:
        clauses: List[str] = []
        params: List[Any] = []

        if keyword:
            terms = [t.strip() for t in keyword.replace("，", " ").replace(",", " ").split() if t.strip()]
            if terms:
                like_clauses = []
                for term in terms:
                    like_clauses.append(
                        "(id LIKE ? OR name LIKE ? OR keywords LIKE ? OR material LIKE ? OR color LIKE ? OR style LIKE ? OR subcategory LIKE ?)"
                    )
                    for _ in range(7):
                        params.append(f"%{term}%")
                clauses.append("(" + " OR ".join(like_clauses) + ")")

        if category:
            clauses.append("category = ?")
            params.append(category)

        if space:
            clauses.append("space_tags LIKE ?")
            params.append(f"%{space}%")

        if in_stock:
            clauses.append("stock > 0")

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        total = conn.execute(f"SELECT COUNT(*) FROM products{where}", params).fetchone()[0]

        page = max(1, page)
        page_size = max(1, min(100, page_size))
        offset = (page - 1) * page_size
        rows = conn.execute(
            f"SELECT * FROM products{where} ORDER BY category, id LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()
        return {
            "items": [row_to_dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    finally:
        conn.close()


def create_product(data: Dict[str, Any]) -> Dict[str, Any]:
    """新增 SKU。id/name/category/price 必填，ID 冲突抛 ValueError。"""
    product_id = (data.get("id") or "").strip()
    if not product_id:
        raise ValueError("商品 ID 不能为空")
    values = _normalize_payload(data)
    values["id"] = product_id
    conn = _connect()
    try:
        cur = conn.cursor()
        exists = cur.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
        if exists:
            raise ValueError(f"商品 ID 已存在：{product_id}")
        cur.execute(
            f"INSERT INTO products ({', '.join(PRODUCT_COLUMNS)}) VALUES ({', '.join('?' * len(PRODUCT_COLUMNS))})",
            [values[c] for c in PRODUCT_COLUMNS],
        )
        conn.commit()
        row = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        _clear_cache()
        return row_to_dict(row)
    except sqlite3.IntegrityError:
        raise ValueError(f"商品 ID 已存在：{product_id}")
    finally:
        conn.close()


def update_product(product_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """增量更新 SKU（价格/库存/名称等任意字段）。返回更新后的记录；不存在返回 None。"""
    conn = _connect()
    try:
        cur = conn.cursor()
        existing = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not existing:
            return None

        updates: Dict[str, Any] = {}
        for k, v in data.items():
            if k not in PRODUCT_COLUMNS or v is None:
                continue
            updates[k] = v

        if "price" in updates:
            updates["price"] = float(updates["price"])
            if updates["price"] < 0:
                raise ValueError("价格不能为负数")
        if "stock" in updates:
            updates["stock"] = int(updates["stock"])
            if updates["stock"] < 0:
                raise ValueError("库存不能为负数")
        if "lead_time_days" in updates:
            updates["lead_time_days"] = int(updates["lead_time_days"])
            if updates["lead_time_days"] < 0:
                raise ValueError("交付周期不能为负数")
        if "name" in updates:
            updates["name"] = (updates["name"] or "").strip()
            if not updates["name"]:
                raise ValueError("商品名称不能为空")
        if "category" in updates:
            updates["category"] = (updates["category"] or "").strip()
            if not updates["category"]:
                raise ValueError("商品品类不能为空")

        # ID 变更检查（默认不支持改主键，避免影响在售引用）
        if "id" in updates:
            new_id = (updates["id"] or "").strip()
            if not new_id or new_id == product_id:
                updates.pop("id", None)
            else:
                dup = cur.execute("SELECT id FROM products WHERE id = ?", (new_id,)).fetchone()
                if dup:
                    raise ValueError(f"商品 ID 已存在：{new_id}")
                raise ValueError("不支持修改商品 ID，请删除后重建")

        if not updates:
            return row_to_dict(existing)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        cur.execute(
            f"UPDATE products SET {set_clause} WHERE id = ?",
            [updates[k] for k in updates] + [product_id],
        )
        conn.commit()
        row = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        _clear_cache()
        return row_to_dict(row)
    finally:
        conn.close()


def delete_product(product_id: str) -> bool:
    """删除 SKU，返回是否删除成功。"""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        if deleted:
            _clear_cache()
        return deleted
    finally:
        conn.close()


def import_products_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    CSV 批量导入（upsert 语义）：
    - ID 不存在 → 新增；ID 存在 → 按 CSV 字段覆盖更新。
    - 返回 {created, updated, skipped, errors}，单行失败不中断整体导入。
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        created = 0
        updated = 0
        skipped = 0
        errors: List[str] = []

        for i, r in enumerate(rows, start=2):
            try:
                pid = (r.get("id") or "").strip()
                if not pid:
                    skipped += 1
                    errors.append(f"第 {i} 行：缺少 id，已跳过")
                    continue
                values = _normalize_payload(r)
                values["id"] = pid

                exists = cur.execute("SELECT id FROM products WHERE id = ?", (pid,)).fetchone()
                if exists:
                    set_clause = ", ".join(f"{k} = ?" for k in PRODUCT_COLUMNS)
                    cur.execute(
                        f"UPDATE products SET {set_clause} WHERE id = ?",
                        [values[c] for c in PRODUCT_COLUMNS] + [pid],
                    )
                    updated += 1
                else:
                    cur.execute(
                        f"INSERT INTO products ({', '.join(PRODUCT_COLUMNS)}) VALUES ({', '.join('?' * len(PRODUCT_COLUMNS))})",
                        [values[c] for c in PRODUCT_COLUMNS],
                    )
                    created += 1
            except Exception as e:  # 单行失败不影响整体
                skipped += 1
                errors.append(f"第 {i} 行：{e}")

        conn.commit()
        _clear_cache()
        return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}
    finally:
        conn.close()
