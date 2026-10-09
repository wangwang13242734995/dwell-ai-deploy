"""
Leads Route（P2 导购跟进线索）

- GET    /leads                分页列表（关键词/状态筛选）
- POST   /leads                创建线索
- GET    /leads/{id}           查询线索（含跟进记录）
- PUT    /leads/{id}           更新线索基础信息
- PATCH  /leads/{id}/status    状态流转
- POST   /leads/{id}/records   追加跟进记录
- DELETE /leads/{id}           删除线索

设计说明：
- 线索落新表 leads（plans.db 内），复用 plans.py 持久化层；
- 状态机：new(新线索) → following(跟进中) → negotiating(洽谈中) → won(已成交)/lost(已流失)。
"""

from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.store import plans as plans_store

router = APIRouter(prefix="/leads", tags=["Leads"])


class LeadCreatePayload(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=64, description="顾客姓名")
    phone: str = Field("", max_length=32, description="联系电话")
    store_name: str = Field("", max_length=64, description="门店名称")
    plan_id: str = Field("", max_length=32, description="关联方案 ID")
    status: str = Field("new", description="初始状态：new/following/negotiating/won/lost")
    remark: str = Field("", max_length=500, description="备注")


class LeadUpdatePayload(BaseModel):
    customer_name: Optional[str] = Field(None, min_length=1, max_length=64)
    phone: Optional[str] = Field(None, max_length=32)
    store_name: Optional[str] = Field(None, max_length=64)
    plan_id: Optional[str] = Field(None, max_length=32)
    remark: Optional[str] = Field(None, max_length=500)


class LeadStatusPayload(BaseModel):
    status: str = Field(..., description="目标状态：new/following/negotiating/won/lost")


class LeadRecordPayload(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000, description="跟进记录内容")


def _status_check(status: str) -> None:
    if status not in plans_store.LEAD_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"无效线索状态：{status}，可选：{', '.join(plans_store.LEAD_STATUSES)}",
        )


@router.get("")
async def list_leads(
    keyword: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict:
    """分页列出线索（管理页数据源）。"""
    if status:
        _status_check(status)
    try:
        return plans_store.list_leads(
            keyword=keyword.strip(),
            status=status.strip(),
            page=page,
            page_size=min(max(page_size, 1), 100),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("")
async def create_lead(request: LeadCreatePayload) -> Dict:
    """创建导购跟进线索。"""
    if request.status:
        _status_check(request.status)
    try:
        return plans_store.create_lead(
            customer_name=request.customer_name.strip(),
            phone=request.phone.strip(),
            store_name=request.store_name.strip(),
            plan_id=request.plan_id.strip(),
            status=request.status,
            remark=request.remark.strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{lead_id}")
async def get_lead(lead_id: str) -> Dict:
    """查询单个线索（含跟进记录）。"""
    record = plans_store.get_lead(lead_id)
    if record is None:
        raise HTTPException(status_code=404, detail="线索不存在")
    return record


@router.put("/{lead_id}")
async def update_lead(lead_id: str, request: LeadUpdatePayload) -> Dict:
    """更新线索基础信息。"""
    data = request.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=422, detail="没有需要更新的字段")
    try:
        record = plans_store.update_lead(lead_id, **data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if record is None:
        raise HTTPException(status_code=404, detail="线索不存在")
    return record


@router.patch("/{lead_id}/status")
async def update_lead_status(lead_id: str, request: LeadStatusPayload) -> Dict:
    """线索状态流转。"""
    _status_check(request.status)
    try:
        record = plans_store.update_lead_status(lead_id, request.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if record is None:
        raise HTTPException(status_code=404, detail="线索不存在")
    return record


@router.post("/{lead_id}/records")
async def add_lead_record(lead_id: str, request: LeadRecordPayload) -> Dict:
    """追加一条跟进记录。"""
    record = plans_store.add_lead_record(lead_id, request.content.strip())
    if record is None:
        raise HTTPException(status_code=404, detail="线索不存在")
    return record


@router.delete("/{lead_id}")
async def delete_lead(lead_id: str) -> Dict:
    """删除线索。"""
    deleted = plans_store.delete_lead(lead_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="线索不存在")
    return {"deleted": True, "id": lead_id}
