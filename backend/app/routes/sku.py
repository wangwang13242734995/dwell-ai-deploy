"""
SKU Route

POST /sku/plan - 根据布局家具清单生成门店可成交方案（匹配门店真实在售 SKU）。
GET  /sku/search - 按关键词/品类/空间/预算检索门店 SKU。
GET  /sku/categories - 返回门店商品品类列表。

替代 SerpAPI 在线购物搜索：推荐结果全部来自门店自建商品库。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from app.models.room import RoomObject
from app.store.db import search_products, get_categories, match_label_to_keywords

router = APIRouter(prefix="/sku", tags=["Store SKU"])


# === Request / Response Models ===

class SkuSearchRequest(BaseModel):
    """按关键词/品类/空间/预算检索门店 SKU。"""
    keyword: Optional[str] = Field(None, description="关键词（匹配名称/材质/颜色/风格/分类）")
    category: Optional[str] = Field(None, description="品类（如 客厅/卧室/餐厅/书房/玄关/软装）")
    space: Optional[str] = Field(None, description="适用空间（如 客厅/卧室）")
    max_price: Optional[float] = Field(None, description="最高单价（人民币）")
    min_price: Optional[float] = Field(None, description="最低单价（人民币）")
    in_stock: bool = Field(False, description="仅返回有库存商品")
    limit: int = Field(10, ge=1, le=50)


class SkuProduct(BaseModel):
    """门店在售 SKU 商品。"""
    id: str
    name: str
    category: str
    subcategory: Optional[str] = None
    material: Optional[str] = None
    color: Optional[str] = None
    style: Optional[str] = None
    dimensions: Optional[dict] = None
    price: float
    stock: int = 0
    lead_time_days: int = 0
    space_list: List[str] = []
    image_url: str = ""


class SkuPlanRequest(BaseModel):
    """根据布局家具清单生成门店可成交方案。"""
    current_layout: List[RoomObject] = Field(..., description="当前家具布局（含 label）")
    total_budget: Optional[float] = Field(None, description="总预算（人民币），用于按件分摊")


class SkuPlanItem(BaseModel):
    """方案中单件家具的匹配结果。"""
    furniture_id: str
    furniture_label: str
    matched: bool = False
    products: List[SkuProduct] = []


class SkuPlanResponse(BaseModel):
    """门店可成交方案。"""
    items: List[SkuPlanItem]
    total_price_cny: float = 0
    max_lead_time_days: int = 0
    out_of_stock_count: int = 0
    matched_count: int = 0
    message: str = ""


# === Endpoints ===

@router.get("/search", response_model=List[SkuProduct])
async def sku_search(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    space: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    in_stock: bool = False,
    limit: int = 10,
) -> List[SkuProduct]:
    """检索门店 SKU。"""
    try:
        rows = search_products(
            keyword=keyword,
            category=category,
            space=space,
            max_price=max_price,
            min_price=min_price,
            in_stock=in_stock,
            limit=limit,
        )
        return [SkuProduct(**r) for r in rows]
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories", response_model=List[dict])
async def sku_categories() -> List[dict]:
    """门店商品品类及数量。"""
    try:
        return get_categories()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan", response_model=SkuPlanResponse)
async def sku_plan(request: SkuPlanRequest) -> SkuPlanResponse:
    """根据布局家具清单生成门店可成交方案。"""
    try:
        movable_items = [
            {"id": obj.id, "label": obj.label}
            for obj in request.current_layout
            if obj.type.value == "movable"
        ]
        if not movable_items:
            return SkuPlanResponse(items=[], message="布局中没有可移动家具。")

        # 预算分摊（无总预算时按件匹配、不限价）
        per_budget = None
        if request.total_budget and request.total_budget > 0:
            per_budget = round(request.total_budget / len(movable_items), 2)

        items = []
        total = 0.0
        max_lead = 0
        out_of_stock = 0
        matched = 0
        for item in movable_items:
            label = item["label"] or ""
            keywords = match_label_to_keywords(label)
            query = " ".join(keywords) if keywords else label
            products = search_products(keyword=query, max_price=per_budget, limit=3)
            if products:
                matched += 1
                total += products[0]["price"]
                max_lead = max(max_lead, products[0]["lead_time_days"] or 0)
                if not (products[0].get("stock") or 0) > 0:
                    out_of_stock += 1
            items.append(SkuPlanItem(
                furniture_id=item["id"],
                furniture_label=label,
                matched=bool(products),
                products=[SkuProduct(**p) for p in products],
            ))

        return SkuPlanResponse(
            items=items,
            total_price_cny=round(total, 2),
            max_lead_time_days=max_lead,
            out_of_stock_count=out_of_stock,
            matched_count=matched,
            message=f"已为 {matched}/{len(movable_items)} 件家具匹配门店在售 SKU。",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
