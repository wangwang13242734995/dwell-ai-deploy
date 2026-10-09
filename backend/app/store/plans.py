"""
方案持久化存储层（P0 手机只读分享页 + P2 报价单 / 导购跟进线索）

基于 SQLite 的「可成交方案」存取。plans.db 中包含三张表：
- plans：短链方案
  - id：短链 ID（8 位 base62，分享 URL 用，如 /share/xK3mQ9wA）
  - layout_json：生成方案时的家具布局（RoomObject 列表）
  - total_budget：顾客总预算（人民币）
  - plan_json：方案完整 JSON（ShopResponse 结构，含分项商品/总价/交付周期）
  - created_at：创建时间（本地 ISO 字符串）
- quotes：报价单（基于方案生成，含明细/总价/交付周期/门店信息）
  - id：报价单号（Q + 时间戳 + 随机）
  - plan_id：关联方案短链 ID
  - quote_json：报价单完整 JSON
  - created_at：创建时间（本地 ISO 字符串）
- leads：导购跟进线索（顾客名/电话/门店/关联方案ID/状态/跟进记录）
  - id：线索 ID
  - customer_name / phone / store_name / plan_id
  - status：new / following / negotiating / won / lost
  - remark：备注
  - follow_up_records：跟进记录 JSON 数组 [{content, created_at}]
  - created_at / updated_at

接口约定（见 routes/plan.py / quote.py / leads.py）：
- POST /api/v1/plan 生成并保存方案 → 返回 { plan_id, share_url, plan }
- GET  /api/v1/plan/{plan_id} 查询方案 → 返回完整方案
- POST /api/v1/quote/{plan_id} 基于方案生成报价单（幂等：已存在则返回既有报价单）
- GET  /api/v1/quote/{quote_id} 查询报价单
- GET  /api/v1/quote/{quote_id}/html 打印版 HTML
- GET  /api/v1/quote/by-plan/{plan_id} 查询某方案最新报价单
- GET/POST /api/v1/leads、GET/PUT/PATCH/DELETE /api/v1/leads/{id}
"""

import json
import os
import secrets
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import get_settings

# 短链字符集：去易混淆字符（0/O、1/I/L）的 base62 子集
_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
_ID_LENGTH = 8

# 门店信息（报价单抬头用；可通过环境变量覆盖）
STORE_INFO = {
    "store_name": os.getenv("DWELL_STORE_NAME", "Dwell.ai 家居体验馆"),
    "store_address": os.getenv("DWELL_STORE_ADDRESS", "上海市徐汇区漕溪北路 88 号 2F"),
    "store_phone": os.getenv("DWELL_STORE_PHONE", "021-8888-6666"),
    "store_hours": os.getenv("DWELL_STORE_HOURS", "10:00 - 22:00"),
    "sales_name": os.getenv("DWELL_SALES_NAME", "门店导购"),
    "sales_phone": os.getenv("DWELL_SALES_PHONE", "138-0000-0000"),
}

# 线索状态流转（P2）
LEAD_STATUSES = ["new", "following", "negotiating", "won", "lost"]
LEAD_STATUS_LABELS = {
    "new": "新线索",
    "following": "跟进中",
    "negotiating": "洽谈中",
    "won": "已成交",
    "lost": "已流失",
}


def _db_path() -> str:
    """定位方案数据库文件（backend/data/plans.db，与 sku.db 同目录）。"""
    settings = get_settings()
    if settings.sku_db_path:
        base = os.path.dirname(os.path.abspath(settings.sku_db_path))
        return os.path.join(base, "plans.db")
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "data", "plans.db")


def _connect() -> sqlite3.Connection:
    db = _db_path()
    os.makedirs(os.path.dirname(db), exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _ensure_table(conn)
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY,
            layout_json TEXT NOT NULL DEFAULT '[]',
            total_budget REAL NOT NULL DEFAULT 0,
            plan_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        )
        """
    )
    # P2：报价单表
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quotes (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            quote_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_quotes_plan_id ON quotes(plan_id)"
    )
    # P2：导购跟进线索表
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            store_name TEXT NOT NULL DEFAULT '',
            plan_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'new',
            remark TEXT NOT NULL DEFAULT '',
            follow_up_records TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)"
    )


def _generate_id(conn: sqlite3.Connection) -> str:
    """生成不冲突的短链 ID（8 位，最多重试 20 次）。"""
    for _ in range(20):
        candidate = "".join(secrets.choice(_ID_ALPHABET) for _ in range(_ID_LENGTH))
        row = conn.execute("SELECT 1 FROM plans WHERE id = ?", (candidate,)).fetchone()
        if row is None:
            return candidate
    raise RuntimeError("无法生成唯一方案 ID")


def create_plan(
    layout: list,
    total_budget: float,
    plan: Dict[str, Any],
) -> Dict[str, Any]:
    """保存一份方案，返回 { plan_id, share_url, plan }。"""
    conn = _connect()
    try:
        plan_id = _generate_id(conn)
        created_at = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO plans (id, layout_json, total_budget, plan_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                plan_id,
                json.dumps(layout, ensure_ascii=False),
                float(total_budget),
                json.dumps(plan, ensure_ascii=False),
                created_at,
            ),
        )
        conn.commit()
        return {
            "plan_id": plan_id,
            "share_url": f"/share/{plan_id}",
            "created_at": created_at,
            "plan": plan,
        }
    finally:
        conn.close()


def get_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    """按短链 ID 查询方案；不存在返回 None。"""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, layout_json, total_budget, plan_json, created_at FROM plans WHERE id = ?",
            (plan_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "plan_id": row["id"],
            "created_at": row["created_at"],
            "total_budget": row["total_budget"],
            "layout": json.loads(row["layout_json"] or "[]"),
            "plan": json.loads(row["plan_json"] or "{}"),
        }
    finally:
        conn.close()


# ============ P2：报价单 ============


def build_quote_from_plan(plan_record: Dict[str, Any]) -> Dict[str, Any]:
    """基于方案记录构建报价单 JSON（明细/总价/交付周期/门店信息）。"""
    plan = plan_record.get("plan") or {}
    items = plan.get("items", []) or []
    total_price = 0.0
    in_stock_count = 0
    out_of_stock_count = 0
    detail_items = []
    max_lead_time_days = 0

    for item in items:
        products = item.get("products", []) or []
        product = products[0] if products else None
        if not product:
            continue
        price = float(product.get("price") or 0)
        stock = int(product.get("stock") or 0)
        lead_time = int(product.get("lead_time_days") or 0)
        total_price += price
        if stock > 0:
            in_stock_count += 1
        else:
            out_of_stock_count += 1
        max_lead_time_days = max(max_lead_time_days, lead_time)
        detail_items.append(
            {
                "furniture_id": item.get("furniture_id", ""),
                "furniture_label": item.get("furniture_label", ""),
                "product": product,
                "quantity": 1,
                "line_total": round(price, 2),
                "lead_time_days": lead_time,
                "in_stock": stock > 0,
            }
        )

    return {
        "store": dict(STORE_INFO),
        "summary": {
            "item_count": len(detail_items),
            "total_price": round(total_price, 2),
            "total_budget": round(float(plan.get("total_budget") or plan_record.get("total_budget") or 0), 2),
            "max_lead_time_days": max_lead_time_days,
            "in_stock_count": in_stock_count,
            "out_of_stock_count": out_of_stock_count,
        },
        "items": detail_items,
        "source_plan": {
            "plan_id": plan_record["plan_id"],
            "created_at": plan_record["created_at"],
        },
        "message": plan.get("message", ""),
    }


def _generate_quote_id(conn: sqlite3.Connection) -> str:
    """生成报价单号：Q + 日期 + 4 位随机。"""
    now = datetime.now()
    base = f"Q{now:%Y%m%d}"
    for _ in range(20):
        suffix = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
        candidate = f"{base}{suffix}"
        row = conn.execute("SELECT 1 FROM quotes WHERE id = ?", (candidate,)).fetchone()
        if row is None:
            return candidate
    raise RuntimeError("无法生成唯一报价单号")


def create_quote(plan_id: str, quote: Dict[str, Any]) -> Dict[str, Any]:
    """保存报价单，返回 { quote_id, plan_id, quote, created_at }。"""
    conn = _connect()
    try:
        quote_id = _generate_quote_id(conn)
        created_at = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO quotes (id, plan_id, quote_json, created_at) VALUES (?, ?, ?, ?)",
            (quote_id, plan_id, json.dumps(quote, ensure_ascii=False), created_at),
        )
        conn.commit()
        return {
            "quote_id": quote_id,
            "plan_id": plan_id,
            "quote": quote,
            "created_at": created_at,
        }
    finally:
        conn.close()


def get_quote(quote_id: str) -> Optional[Dict[str, Any]]:
    """按报价单号查询；不存在返回 None。"""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, plan_id, quote_json, created_at FROM quotes WHERE id = ?",
            (quote_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "quote_id": row["id"],
            "plan_id": row["plan_id"],
            "quote": json.loads(row["quote_json"] or "{}"),
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def get_quote_by_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    """按方案 ID 查询最新报价单；不存在返回 None。"""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, plan_id, quote_json, created_at FROM quotes WHERE plan_id = ? ORDER BY created_at DESC LIMIT 1",
            (plan_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "quote_id": row["id"],
            "plan_id": row["plan_id"],
            "quote": json.loads(row["quote_json"] or "{}"),
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


# ============ P2：导购跟进线索 ============


def _generate_lead_id(conn: sqlite3.Connection) -> str:
    """生成线索 ID：L + 日期 + 4 位随机。"""
    now = datetime.now()
    base = f"L{now:%Y%m%d}"
    for _ in range(20):
        suffix = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
        candidate = f"{base}{suffix}"
        row = conn.execute("SELECT 1 FROM leads WHERE id = ?", (candidate,)).fetchone()
        if row is None:
            return candidate
    raise RuntimeError("无法生成唯一线索 ID")


def _lead_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "customer_name": row["customer_name"],
        "phone": row["phone"],
        "store_name": row["store_name"],
        "plan_id": row["plan_id"],
        "status": row["status"],
        "status_label": LEAD_STATUS_LABELS.get(row["status"], row["status"]),
        "remark": row["remark"],
        "follow_up_records": json.loads(row["follow_up_records"] or "[]"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_lead(
    customer_name: str,
    phone: str = "",
    store_name: str = "",
    plan_id: str = "",
    status: str = "new",
    remark: str = "",
) -> Dict[str, Any]:
    """创建导购跟进线索。"""
    if status not in LEAD_STATUSES:
        raise ValueError(f"无效线索状态：{status}")
    conn = _connect()
    try:
        lead_id = _generate_lead_id(conn)
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO leads (id, customer_name, phone, store_name, plan_id, status, remark, follow_up_records, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (lead_id, customer_name, phone, store_name, plan_id, status, remark, "[]", now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return _lead_row_to_dict(row)
    finally:
        conn.close()


def list_leads(
    keyword: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """分页列出线索（支持关键词/状态筛选）。"""
    conn = _connect()
    try:
        where = []
        params: List[Any] = []
        if keyword:
            like = f"%{keyword}%"
            where.append("(customer_name LIKE ? OR phone LIKE ? OR plan_id LIKE ?)")
            params += [like, like, like]
        if status:
            where.append("status = ?")
            params.append(status)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        total = conn.execute(f"SELECT COUNT(*) FROM leads {clause}", params).fetchone()[0]
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, page)
        rows = conn.execute(
            f"SELECT * FROM leads {clause} ORDER BY updated_at DESC, created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
        return {
            "items": [_lead_row_to_dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    finally:
        conn.close()


def get_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    """查询单个线索；不存在返回 None。"""
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return _lead_row_to_dict(row) if row else None
    finally:
        conn.close()


def update_lead(
    lead_id: str,
    customer_name: Optional[str] = None,
    phone: Optional[str] = None,
    store_name: Optional[str] = None,
    plan_id: Optional[str] = None,
    remark: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """更新线索基础信息；不存在返回 None。"""
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if row is None:
            return None
        updates = []
        params: List[Any] = []
        if customer_name is not None:
            updates.append("customer_name = ?")
            params.append(customer_name)
        if phone is not None:
            updates.append("phone = ?")
            params.append(phone)
        if store_name is not None:
            updates.append("store_name = ?")
            params.append(store_name)
        if plan_id is not None:
            updates.append("plan_id = ?")
            params.append(plan_id)
        if remark is not None:
            updates.append("remark = ?")
            params.append(remark)
        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat(timespec="seconds"))
            conn.execute(f"UPDATE leads SET {', '.join(updates)} WHERE id = ?", params + [lead_id])
            conn.commit()
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return _lead_row_to_dict(row)
    finally:
        conn.close()


def update_lead_status(lead_id: str, status: str) -> Optional[Dict[str, Any]]:
    """流转线索状态；不存在返回 None。"""
    if status not in LEAD_STATUSES:
        raise ValueError(f"无效线索状态：{status}")
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now().isoformat(timespec="seconds"), lead_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return _lead_row_to_dict(row)
    finally:
        conn.close()


def add_lead_record(lead_id: str, content: str) -> Optional[Dict[str, Any]]:
    """追加一条跟进记录；线索不存在返回 None。"""
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if row is None:
            return None
        records = json.loads(row["follow_up_records"] or "[]")
        now = datetime.now().isoformat(timespec="seconds")
        records.append({"content": content, "created_at": now})
        conn.execute(
            "UPDATE leads SET follow_up_records = ?, updated_at = ? WHERE id = ?",
            (json.dumps(records, ensure_ascii=False), now, lead_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return _lead_row_to_dict(row)
    finally:
        conn.close()


def delete_lead(lead_id: str) -> bool:
    """删除线索；不存在返回 False。"""
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
