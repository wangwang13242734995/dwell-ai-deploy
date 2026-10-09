"""
SKU Admin Routes (P1)

SKU 管理后台 API：
- GET    /sku/admin/products         分页列表（支持品类/关键词/库存筛选）
- POST   /sku/admin/products         新增 SKU
- PUT    /sku/admin/products/{id}    编辑 SKU（价格/库存/名称等）
- DELETE /sku/admin/products/{id}    删除 SKU
- POST   /sku/admin/products/import-csv  CSV 批量导入（upsert）
- GET    /sku/admin/categories       品类列表（管理页筛选下拉）

设计约束：复用 products 表与 store/db.py 数据访问层，不触碰 /sku/search、
/sku/plan、/api/v1/plan 等既有接口逻辑。
"""

import csv
import io
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Dict, Any

from app.store.db import (
    get_categories,
    list_products_paged,
    create_product,
    update_product,
    delete_product,
    import_products_from_rows,
)

router = APIRouter(prefix="/sku/admin", tags=["SKU Admin"])


# === Request / Response Models ===

class AdminSkuPayload(BaseModel):
    """新增/编辑 SKU 载荷（编辑时可只传需要更新的字段）。"""
    id: Optional[str] = Field(None, description="商品 ID（新增必填，编辑时忽略）")
    name: str = Field(..., description="商品名称")
    category: str = Field(..., description="品类（如 客厅/卧室/餐厅/书房/玄关/软装）")
    subcategory: Optional[str] = Field(None)
    material: Optional[str] = Field(None)
    color: Optional[str] = Field(None)
    style: Optional[str] = Field(None)
    dim_w: Optional[float] = Field(None)
    dim_d: Optional[float] = Field(None)
    dim_h: Optional[float] = Field(None)
    unit: str = Field("cm", description="尺寸单位")
    price: float = Field(..., ge=0, description="人民币售价")
    stock: int = Field(0, ge=0, description="库存数量")
    lead_time_days: int = Field(7, ge=0, description="交付周期（天）")
    space_tags: Optional[str] = Field(None, description="适用空间，竖线分隔，如 客厅|卧室")
    keywords: Optional[str] = Field(None, description="检索关键词（空格分隔）")
    image_url: Optional[str] = Field(None, description="商品图片 URL")


class AdminPriceStockUpdate(BaseModel):
    """库存/价格快速调整（管理页行内操作）。"""
    price: Optional[float] = Field(None, ge=0)
    stock: Optional[int] = Field(None, ge=0)
    lead_time_days: Optional[int] = Field(None, ge=0)


class AdminImportResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: List[str] = []


# === Endpoints ===

@router.get("/products")
async def admin_list_products(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    space: Optional[str] = None,
    in_stock: bool = False,
) -> Dict[str, Any]:
    """分页列出 SKU（管理后台）。"""
    try:
        return list_products_paged(
            keyword=keyword,
            category=category,
            space=space,
            in_stock=in_stock,
            page=page,
            page_size=page_size,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def admin_categories() -> List[dict]:
    """品类列表（供管理页筛选下拉，返回品类及商品数）。"""
    try:
        return get_categories()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products")
async def admin_create_product(request: AdminSkuPayload) -> Dict[str, Any]:
    """新增 SKU。"""
    try:
        data = request.model_dump(exclude_none=True)
        if not (request.id or "").strip():
            raise HTTPException(status_code=422, detail="商品 ID 不能为空")
        return create_product(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/products/{product_id}")
async def admin_update_product(product_id: str, request: AdminSkuPayload) -> Dict[str, Any]:
    """编辑 SKU（价格/库存/名称等）。"""
    try:
        data = request.model_dump(exclude_none=True)
        result = update_product(product_id, data)
        if result is None:
            raise HTTPException(status_code=404, detail=f"商品不存在：{product_id}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/products/{product_id}/price-stock")
async def admin_quick_update(product_id: str, request: AdminPriceStockUpdate) -> Dict[str, Any]:
    """库存/价格快速调整（行内操作，只改价格/库存/交付周期）。"""
    try:
        data = {k: v for k, v in request.model_dump().items() if v is not None}
        if not data:
            raise HTTPException(status_code=422, detail="至少需要 price/stock/lead_time_days 之一")
        result = update_product(product_id, data)
        if result is None:
            raise HTTPException(status_code=404, detail=f"商品不存在：{product_id}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/products/{product_id}")
async def admin_delete_product(product_id: str) -> Dict[str, Any]:
    """删除 SKU。"""
    try:
        deleted = delete_product(product_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"商品不存在：{product_id}")
        return {"deleted": True, "id": product_id}
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/import-csv", response_model=AdminImportResponse)
async def admin_import_csv(file: UploadFile = File(...)) -> AdminImportResponse:
    """CSV 批量导入（upsert：ID 存在则更新，不存在则新增）。

    CSV 表头（与 scripts/init_sku_db.py 一致）：
        id,name,category,subcategory,material,color,style,dim_w,dim_d,dim_h,unit,
        price,stock,lead_time_days,space_tags,keywords,image_url
    """
    try:
        raw = await file.read()
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV 编码需为 UTF-8（可带 BOM）")

    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict[str, Any]] = []
    for r in reader:
        rows.append(dict(r))

    if not rows:
        raise HTTPException(status_code=400, detail="CSV 为空或表头无法识别")

    try:
        result = import_products_from_rows(rows)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return AdminImportResponse(**result)
