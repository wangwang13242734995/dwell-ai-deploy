"""
Quote Route（P2 报价单）

- POST /quote/{plan_id}         基于已有方案生成报价单（幂等：已存在返回既有报价单）
- GET  /quote/{quote_id}        查询报价单（JSON）
- GET  /quote/{quote_id}/html   打印版 HTML（浏览器直接可打印）
- GET  /quote/by-plan/{plan_id} 查询某方案最新报价单

设计说明：
- 复用 plans.db 与 plans.py（store/plans.py），基于 /api/v1/plan 保存的方案生成；
- 报价单含商品明细/总价/交付周期/门店信息；
- HTML 打印版内联样式，适合 A4 打印与微信内分享截图。
"""

import html as html_mod
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.store import plans as plans_store

router = APIRouter(prefix="/quote", tags=["Quote"])


class QuoteResponse(BaseModel):
    quote_id: str
    plan_id: str
    quote: dict
    created_at: str


def _require_plan(plan_id: str):
    plan_record = plans_store.get_plan(plan_id)
    if plan_record is None:
        raise HTTPException(status_code=404, detail="方案不存在或链接已失效")
    return plan_record


@router.post("/{plan_id}", response_model=QuoteResponse)
async def create_quote(plan_id: str) -> QuoteResponse:
    """基于方案生成报价单（幂等：同一方案已生成过则直接返回既有报价单）。"""
    plan_record = _require_plan(plan_id)

    existing = plans_store.get_quote_by_plan(plan_id)
    if existing is not None:
        return QuoteResponse(**existing)

    quote = plans_store.build_quote_from_plan(plan_record)
    saved = plans_store.create_quote(plan_id, quote)
    return QuoteResponse(**saved)


@router.get("/by-plan/{plan_id}", response_model=QuoteResponse)
async def get_quote_by_plan(plan_id: str) -> QuoteResponse:
    """查询某方案的最新报价单（未生成时返回 404，前端据此触发生成）。"""
    _require_plan(plan_id)
    record = plans_store.get_quote_by_plan(plan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="该方案尚未生成报价单")
    return QuoteResponse(**record)


@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(quote_id: str) -> QuoteResponse:
    """按报价单号查询报价单。"""
    record = plans_store.get_quote(quote_id)
    if record is None:
        raise HTTPException(status_code=404, detail="报价单不存在")
    return QuoteResponse(**record)


def _fmt_money(v) -> str:
    try:
        return f"¥{float(v):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _render_quote_html(record: dict) -> str:
    """渲染打印版 HTML（A4 友好、内联样式）。"""
    quote = record["quote"]
    store = quote.get("store", {})
    summary = quote.get("summary", {})
    items = quote.get("items", [])
    source_plan = quote.get("source_plan", {})

    def esc(s):
        return html_mod.escape(str(s if s is not None else ""))

    rows = []
    for idx, it in enumerate(items, start=1):
        p = it.get("product", {})
        dims = p.get("dimensions") or {}
        dim_parts = []
        for key, unit_label in (("w", "宽"), ("d", "深"), ("h", "高")):
            v = dims.get(key)
            if v:
                dim_parts.append(f"{v}{dims.get('unit', 'cm')}{unit_label}")
        dim_text = " · ".join(dim_parts)
        stock_text = "现货" if it.get("in_stock") else "需调货/缺货"
        lead_text = f"{it.get('lead_time_days')} 天" if it.get("lead_time_days") else "现货"
        rows.append(
            f"""
            <tr>
              <td class="num">{idx}</td>
              <td>
                <div class="pname">{esc(p.get('title') or it.get('furniture_label'))}</div>
                <div class="psub">{esc(it.get('furniture_label'))}{' · ' + esc(dim_text) if dim_text else ''}</div>
                <div class="psub">货号 {esc(p.get('sku_id') or '—')} · {esc(p.get('category') or '—')}</div>
              </td>
              <td class="num">{it.get('quantity', 1)}</td>
              <td class="num">{_fmt_money(p.get('price'))}</td>
              <td class="num">{lead_text}</td>
              <td class="num {'' if it.get('in_stock') else 'warn'}">{stock_text}</td>
              <td class="num total">{_fmt_money(it.get('line_total'))}</td>
            </tr>
            """
        )

    budget = summary.get("total_budget") or 0
    price = summary.get("total_price") or 0
    diff = price - budget
    budget_line = (
        f"方案总价在预算内（预算 {_fmt_money(budget)}）"
        if diff <= 0
        else f"方案总价超出预算 {_fmt_money(diff)}（预算 {_fmt_money(budget)}）"
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>报价单 {esc(record['quote_id'])}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; background: #F2EFEA; color: #2B2B2B; }}
  .page {{ max-width: 820px; margin: 24px auto; background: #fff; padding: 48px 52px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
  .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #2B2B2B; padding-bottom: 18px; }}
  .brand {{ font-size: 24px; font-weight: 700; letter-spacing: 2px; color: #2B2B2B; }}
  .brand small {{ display: block; font-size: 12px; font-weight: 400; color: #8B6F47; letter-spacing: 1px; margin-top: 4px; }}
  .doc-title {{ text-align: right; }}
  .doc-title h1 {{ font-size: 26px; color: #8B6F47; }}
  .doc-title p {{ font-size: 12px; color: #999; margin-top: 4px; }}
  .store {{ display: flex; justify-content: space-between; margin: 22px 0; font-size: 13px; color: #555; }}
  .store .block {{ line-height: 1.9; }}
  .store .label {{ color: #999; margin-right: 6px; }}
  .meta {{ background: #F7F5F2; border-radius: 8px; padding: 14px 18px; display: flex; gap: 28px; font-size: 13px; margin-bottom: 24px; }}
  .meta .m {{ flex: 1; }}
  .meta .m .label {{ color: #999; display: block; font-size: 12px; }}
  .meta .m .val {{ font-weight: 600; font-size: 16px; margin-top: 2px; }}
  .meta .m .val.accent {{ color: #8B6F47; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  thead th {{ background: #2B2B2B; color: #fff; padding: 10px 8px; text-align: left; font-weight: 500; }}
  thead th.num, td.num {{ text-align: right; }}
  td {{ padding: 12px 8px; border-bottom: 1px solid #EDE9E3; vertical-align: top; }}
  .pname {{ font-weight: 600; }}
  .psub {{ font-size: 11px; color: #999; margin-top: 2px; }}
  .total {{ color: #8B6F47; font-weight: 600; }}
  .warn {{ color: #A85B2D; }}
  .summary {{ margin-top: 18px; display: flex; justify-content: flex-end; }}
  .summary .box {{ min-width: 300px; }}
  .summary .line {{ display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; }}
  .summary .line.grand {{ border-top: 2px solid #2B2B2B; margin-top: 6px; padding-top: 10px; font-size: 18px; font-weight: 700; color: #2B2B2B; }}
  .summary .line.grand .v {{ color: #8B6F47; }}
  .notes {{ margin-top: 28px; font-size: 12px; color: #777; line-height: 1.9; border-top: 1px dashed #DDD6CC; padding-top: 14px; }}
  .footer {{ margin-top: 20px; text-align: center; font-size: 11px; color: #B5AEA4; }}
  @media print {{ body {{ background: #fff; }} .page {{ box-shadow: none; margin: 0; max-width: none; padding: 24px 20px; }} }}
</style>
</head>
<body>
  <div class="page">
    <div class="header">
      <div class="brand">{esc(store.get('store_name') or 'Dwell.ai 家居体验馆')}<small>门店 AI 导购 · 可成交方案报价</small></div>
      <div class="doc-title">
        <h1>报 价 单</h1>
        <p>编号：{esc(record['quote_id'])}</p>
        <p>生成时间：{esc(record['created_at'])}</p>
      </div>
    </div>
    <div class="store">
      <div class="block">
        <div><span class="label">门店地址：</span>{esc(store.get('store_address') or '—')}</div>
        <div><span class="label">联系电话：</span>{esc(store.get('store_phone') or '—')}</div>
      </div>
      <div class="block">
        <div><span class="label">营业时间：</span>{esc(store.get('store_hours') or '—')}</div>
        <div><span class="label">专属导购：</span>{esc(store.get('sales_name') or '—')}（{esc(store.get('sales_phone') or '—')}）</div>
      </div>
    </div>
    <div class="meta">
      <div class="m"><span class="label">关联方案</span><span class="val">{esc(source_plan.get('plan_id') or record.get('plan_id'))}</span></div>
      <div class="m"><span class="label">商品件数</span><span class="val">{summary.get('item_count', 0)}</span></div>
      <div class="m"><span class="label">最快交付</span><span class="val">{summary.get('max_lead_time_days') or '现货'} 天</span></div>
      <div class="m"><span class="label">现货 / 需调货</span><span class="val">{summary.get('in_stock_count', 0)} / {summary.get('out_of_stock_count', 0)}</span></div>
    </div>
    <table>
      <thead>
        <tr>
          <th style="width:32px">#</th>
          <th>商品明细</th>
          <th class="num" style="width:48px">数量</th>
          <th class="num" style="width:88px">单价</th>
          <th class="num" style="width:72px">交付</th>
          <th class="num" style="width:80px">库存</th>
          <th class="num" style="width:88px">小计</th>
        </tr>
      </thead>
      <tbody>{''.join(rows) or '<tr><td colspan="7" style="text-align:center;color:#999;padding:24px">该方案暂无可报价商品</td></tr>'}</tbody>
    </table>
    <div class="summary">
      <div class="box">
        <div class="line"><span>商品合计</span><span>{_fmt_money(price)}</span></div>
        <div class="line"><span>预算核对</span><span>{esc(budget_line)}</span></div>
        <div class="line grand"><span>报价总价</span><span class="v">{_fmt_money(price)}</span></div>
      </div>
    </div>
    <div class="notes">
      说明：
      1. 本报价单基于门店 AI 导购方案生成，价格为当前门店标价，最终以门店确认为准；
      2. 交付周期为对应商品的最长生产/配送周期，现货商品可即时安排配送；
      3. 缺货商品（需调货）由导购确认到货时间后另行告知；
      4. 本报价单有效期 7 天，逾期请咨询门店导购重新核价。
    </div>
    <div class="footer">本报价单由 Dwell.ai 门店 AI 导购系统自动生成 · 打印版</div>
  </div>
</body>
</html>"""
    return html_doc


@router.get("/{quote_id}/html")
async def get_quote_html(quote_id: str) -> Response:
    """返回报价单打印版 HTML。"""
    record = plans_store.get_quote(quote_id)
    if record is None:
        raise HTTPException(status_code=404, detail="报价单不存在")
    html_doc = _render_quote_html(record)
    return Response(
        content=html_doc,
        media_type="text/html; charset=utf-8",
        headers={"X-Quote-Id": quote_id},
    )
