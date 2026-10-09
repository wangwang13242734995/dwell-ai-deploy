"""
Store SKU 模块

门店真实在售商品库（SQLite）数据访问层。
替代 SerpAPI 在线购物搜索，让推荐结果始终来自门店可成交 SKU。
"""

from app.store.db import (
    SKUStore,
    search_products,
    match_label_to_keywords,
    get_categories,
    get_product_by_id,
)

__all__ = [
    "SKUStore",
    "search_products",
    "match_label_to_keywords",
    "get_categories",
    "get_product_by_id",
]
