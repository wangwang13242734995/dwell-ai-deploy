"""
Plan Route（P0 手机只读分享页）

POST /api/v1/plan - 生成并持久化一份「可成交方案」，返回短链 ID
GET  /api/v1/plan/{plan_id} - 按短链 ID 查询完整方案（无需登录）

设计说明：
- 入参复用 /shop 的 ShopRequest（current_layout + total_budget），
  内部走 ShoppingAgent 生成方案后落库（backend/data/plans.db）。
- 导购在画布上「生成方案」一步到位：生成 + 保存 + 拿短链；
  顾客手机打开 /share/{plan_id} 只读展示。
"""

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.room import RoomObject
from app.routes.shop import ShopRequest, ShopResponse
from app.store import plans as plans_store

try:
    from langsmith import traceable
    LANGSMITH_ENABLED = True
except ImportError:
    LANGSMITH_ENABLED = False
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


router = APIRouter(prefix="/plan", tags=["Plan"])


class PlanCreateResponse(BaseModel):
    """POST /plan 返回：短链 ID + 分享 URL + 完整方案。"""
    plan_id: str
    share_url: str
    created_at: str
    plan: ShopResponse


class PlanDetailResponse(BaseModel):
    """GET /plan/{plan_id} 返回：方案详情（含布局与预算元信息）。"""
    plan_id: str
    created_at: str
    total_budget: float
    layout: List[RoomObject] = Field(default_factory=list)
    plan: ShopResponse


@router.post("", response_model=PlanCreateResponse)
@traceable(
    name="plan_create_endpoint",
    run_type="chain",
    tags=["api", "plan", "shopping"],
    metadata={"description": "Generate and persist a sellable furniture plan"}
)
async def create_plan(request: ShopRequest) -> PlanCreateResponse:
    """生成并保存一份可成交方案，返回分享短链。"""
    try:
        from app.agents.shopping_node import ShoppingAgent

        agent = ShoppingAgent()
        result = await agent.find_products(
            current_layout=request.current_layout,
            total_budget=request.total_budget,
            perspective_image_base64=request.perspective_image_base64,
        )

        # 复用 /shop 的响应结构（items/total_estimated/message 等）
        shop_response = ShopResponse(
            items=result.get("items", []),
            total_estimated=result.get("total_estimated", 0),
            total_budget=result.get("total_budget", request.total_budget),
            message=result.get("message", ""),
        )

        saved = plans_store.create_plan(
            layout=[obj.model_dump(mode="json") for obj in request.current_layout],
            total_budget=request.total_budget,
            plan=json.loads(shop_response.model_dump_json()),
        )
        return PlanCreateResponse(**saved)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Plan create failed: {str(e)}"
        )


@router.get("/{plan_id}", response_model=PlanDetailResponse)
async def get_plan(plan_id: str) -> PlanDetailResponse:
    """按短链 ID 查询方案（手机只读页数据源，无需登录）。"""
    plan_id = (plan_id or "").strip()
    if not plan_id:
        raise HTTPException(status_code=400, detail="plan_id is required")

    record = plans_store.get_plan(plan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="方案不存在或链接已失效")

    plan = record["plan"]
    plan_obj = ShopResponse(**plan) if isinstance(plan, dict) else plan

    return PlanDetailResponse(
        plan_id=record["plan_id"],
        created_at=record["created_at"],
        total_budget=record["total_budget"],
        layout=record["layout"],
        plan=plan_obj,
    )
