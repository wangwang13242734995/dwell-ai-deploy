'use client';

/**
 * 手机只读方案页（P0）+ 报价单合一视图（P2）
 * 路由：/share/[planId]
 * 基准宽度 375px，无登录，纯展示。
 * - Tab「方案详情」：GET /api/v1/plan/{planId}
 * - Tab「报价单」：GET /api/v1/quote/by-plan/{planId}，未生成则自动 POST /api/v1/quote/{planId} 生成
 */
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
  Loader2,
  ShoppingBag,
  Armchair,
  Clock,
  PackageCheck,
  PackageX,
  AlertTriangle,
  ChevronRight,
  Store,
  FileText,
  Printer,
  ReceiptText,
  MapPin,
  Phone,
  UserRound,
} from 'lucide-react';
import type { QuoteResponse } from '@/lib/types';
import { createQuote, getQuoteByPlan, openQuoteHtml } from '@/lib/api';

// 同源请求，经 next.config.ts rewrites 代理到后端 /api/v1
const API_BASE = '/api/v1';

interface Product {
  title: string;
  price?: number | null;
  price_raw?: string;
  thumbnail?: string;
  source?: string;
  sku_id?: string | null;
  category?: string | null;
  stock?: number | null;
  lead_time_days?: number | null;
  dimensions?: { w?: number | null; d?: number | null; h?: number | null; unit?: string } | null;
  style?: string | null;
  material?: string | null;
}

interface PlanItem {
  furniture_id: string;
  furniture_label: string;
  search_query?: string;
  budget_allocated?: number;
  products: Product[];
  error?: string | null;
}

interface PlanPayload {
  items: PlanItem[];
  total_estimated: number;
  total_budget: number;
  message?: string;
}

interface PlanDetail {
  plan_id: string;
  created_at: string;
  total_budget: number;
  layout?: unknown[];
  plan: PlanPayload;
}

type LoadState = 'loading' | 'ready' | 'error' | 'notfound';
type TabKey = 'plan' | 'quote';

const fmtMoney = (v?: number | string | null) =>
  v == null ? '—' : `¥${Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;

const fmtDim = (d?: Product['dimensions']) => {
  if (!d) return '';
  const parts: string[] = [];
  if (d.w) parts.push(`${d.w}宽`);
  if (d.d) parts.push(`${d.d}深`);
  if (d.h) parts.push(`${d.h}高`);
  return parts.join('·');
};

export default function SharePlanPage() {
  const params = useParams<{ planId: string }>();
  const planId = params?.planId ?? '';

  const [state, setState] = useState<LoadState>('loading');
  const [detail, setDetail] = useState<PlanDetail | null>(null);

  const [tab, setTab] = useState<TabKey>('plan');
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [quoteState, setQuoteState] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    if (!planId) {
      setState('notfound');
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/plan/${encodeURIComponent(planId)}`, {
          cache: 'no-store',
        });
        if (res.status === 404) {
          if (!cancelled) setState('notfound');
          return;
        }
        if (!res.ok) {
          if (!cancelled) setState('error');
          return;
        }
        const data = (await res.json()) as PlanDetail;
        if (!cancelled) {
          setDetail(data);
          setState('ready');
        }
      } catch {
        if (!cancelled) setState('error');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [planId]);

  // 自动加载报价单（未生成则生成）
  useEffect(() => {
    if (state !== 'ready' || !planId) return;
    let cancelled = false;
    (async () => {
      try {
        let q: QuoteResponse;
        try {
          q = await getQuoteByPlan(planId);
        } catch (err) {
          // 404 = 尚未生成 → 自动生成
          q = await createQuote(planId);
        }
        if (!cancelled) {
          setQuote(q);
          setQuoteState('ready');
        }
      } catch {
        if (!cancelled) setQuoteState('error');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [state, planId]);

  // 加载态
  if (state === 'loading') {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center gap-4 bg-[#F7F5F2] px-6">
        <Loader2 className="w-8 h-8 animate-spin text-[#8B6F47]" />
        <p className="text-sm text-neutral-500">正在加载方案…</p>
      </div>
    );
  }

  // 错误 / 未找到
  if (state === 'error' || state === 'notfound') {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center gap-3 bg-[#F7F5F2] px-6 text-center">
        <AlertTriangle className="w-10 h-10 text-[#C9A87C]" />
        <p className="text-base font-medium text-neutral-800">
          {state === 'notfound' ? '方案不存在或链接已失效' : '加载失败，请稍后重试'}
        </p>
        <p className="text-xs text-neutral-400">请联系门店导购重新获取分享链接</p>
      </div>
    );
  }

  const plan = detail?.plan;
  const items = plan?.items ?? [];
  const totalEstimated = plan?.total_estimated ?? 0;
  const totalBudget = plan?.total_budget ?? detail?.total_budget ?? 0;
  const maxLead = Math.max(0, ...items.flatMap((i) =>
    (i.products ?? []).map((p) => p.lead_time_days ?? 0)
  ));
  const outOfStock = items.flatMap((i) => (i.products ?? [])).filter((p) => (p.stock ?? 0) <= 0).length;
  const matchedItems = items.filter((i) => (i.products ?? []).length > 0);

  const q = quote?.quote;
  const qItems = q?.items ?? [];
  const qSummary = q?.summary;

  return (
    <div className="min-h-dvh bg-[#F7F5F2]">
      <div className="mx-auto max-w-[375px] min-h-dvh bg-white shadow-[0_0_40px_rgba(0,0,0,0.06)] pb-10">
        {/* 顶部品牌条 */}
        <div className="bg-[#2B2B2B] text-white px-5 pt-6 pb-6">
          <div className="flex items-center gap-2 text-[#C9A87C]">
            <Store className="w-4 h-4" />
            <span className="text-xs tracking-widest">门店 AI 导购 · 可成交方案</span>
          </div>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">您的家居配置方案</h1>
          <p className="mt-1 text-xs text-neutral-400">
            生成时间：{detail ? new Date(detail.created_at).toLocaleString('zh-CN') : ''}
          </p>
        </div>

        {/* Tab 切换 */}
        <div className="px-5 mt-4">
          <div className="grid grid-cols-2 rounded-xl bg-[#F2EFEA] p-1">
            <button
              onClick={() => setTab('plan')}
              className={`flex items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm font-medium transition ${
                tab === 'plan' ? 'bg-white shadow-sm text-neutral-900' : 'text-neutral-500'
              }`}
            >
              <Armchair className="w-4 h-4" /> 方案详情
            </button>
            <button
              onClick={() => setTab('quote')}
              className={`flex items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm font-medium transition ${
                tab === 'quote' ? 'bg-white shadow-sm text-[#8B6F47]' : 'text-neutral-500'
              }`}
            >
              <ReceiptText className="w-4 h-4" /> 报价单
              {quoteState === 'loading' && tab === 'quote' && (
                <Loader2 className="w-3 h-3 animate-spin" />
              )}
            </button>
          </div>
        </div>

        {tab === 'plan' ? (
          <>
            {/* 方案总览 */}
            <div className="px-5 -mt-1">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-white shadow-sm border border-neutral-100 p-4">
                  <p className="text-xs text-neutral-400">方案总价</p>
                  <p className="mt-1 text-xl font-semibold text-[#8B6F47]">{fmtMoney(totalEstimated)}</p>
                </div>
                <div className="rounded-xl bg-white shadow-sm border border-neutral-100 p-4">
                  <p className="text-xs text-neutral-400">您的预算</p>
                  <p className="mt-1 text-xl font-semibold text-neutral-900">{fmtMoney(totalBudget)}</p>
                </div>
                <div className="rounded-xl bg-white shadow-sm border border-neutral-100 p-4">
                  <p className="text-xs text-neutral-400">家具件数</p>
                  <p className="mt-1 text-xl font-semibold text-neutral-900">{items.length} 件</p>
                </div>
                <div className="rounded-xl bg-white shadow-sm border border-neutral-100 p-4">
                  <p className="text-xs text-neutral-400">最快交付</p>
                  <p className="mt-1 text-xl font-semibold text-neutral-900">
                    {maxLead > 0 ? `${maxLead} 天` : '现货'}
                  </p>
                </div>
              </div>

              {/* 缺货提示 */}
              {outOfStock > 0 && (
                <div className="mt-3 flex items-start gap-2 rounded-xl bg-[#FFF7ED] border border-[#F4D9C0] p-3 text-xs text-[#A85B2D]">
                  <PackageX className="w-4 h-4 shrink-0 mt-0.5" />
                  <p>
                    有 {outOfStock} 件商品当前门店缺货，导购会与您确认后安排调货或提供替代款。
                  </p>
                </div>
              )}

              {/* 预算覆盖提示 */}
              <div className="mt-3 rounded-xl bg-[#F5F0E8] border border-[#E7DCC8] p-3 text-xs text-neutral-600">
                <span className="font-medium text-neutral-800">
                  {totalEstimated <= totalBudget
                    ? `方案总价在预算内，可安心选购`
                    : `方案总价超出预算 ${fmtMoney(totalEstimated - totalBudget)}，可联系导购调整配置`}
                </span>
              </div>
            </div>

            {/* 分项清单 */}
            <div className="px-5 mt-6">
              <h2 className="text-base font-semibold text-neutral-900 flex items-center gap-2">
                <Armchair className="w-4 h-4 text-[#8B6F47]" />
                分项清单
                <span className="text-xs font-normal text-neutral-400">{matchedItems.length}/{items.length} 件已匹配</span>
              </h2>

              <div className="mt-3 space-y-4">
                {items.map((item) => {
                  const product = item.products?.[0];
                  const matched = !!product;
                  return (
                    <div
                      key={item.furniture_id}
                      className="rounded-xl border border-neutral-100 overflow-hidden bg-white"
                    >
                      {/* 家具头 */}
                      <div className="flex items-center justify-between px-4 py-3 bg-[#FAF8F5]">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-neutral-800">
                            {item.furniture_label.replace(/_/g, ' ')}
                          </span>
                          {item.budget_allocated != null && (
                            <span className="text-xs text-neutral-400">预算 {fmtMoney(item.budget_allocated)}</span>
                          )}
                        </div>
                        {matched ? (
                          <span className="inline-flex items-center gap-1 text-[11px] text-[#5B8A5B] bg-[#EAF4EA] rounded-full px-2 py-0.5">
                            <PackageCheck className="w-3 h-3" /> 已匹配
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] text-[#A85B2D] bg-[#FFF7ED] rounded-full px-2 py-0.5">
                            <PackageX className="w-3 h-3" /> 待确认
                          </span>
                        )}
                      </div>

                      {/* 商品卡 */}
                      {matched && product ? (
                        <div className="p-4">
                          <div className="flex gap-3">
                            <div className="w-20 h-20 shrink-0 rounded-lg bg-neutral-50 overflow-hidden flex items-center justify-center">
                              {product.thumbnail ? (
                                <img
                                  src={product.thumbnail}
                                  alt={product.title}
                                  className="w-full h-full object-contain"
                                />
                              ) : (
                                <ShoppingBag className="w-6 h-6 text-neutral-300" />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-neutral-900 leading-snug line-clamp-2">
                                {product.title}
                              </p>
                              <p className="mt-1 text-[11px] text-neutral-400 line-clamp-1">
                                {[product.category, product.style, product.material].filter(Boolean).join(' · ') || product.source}
                              </p>
                              <p className="mt-2 text-base font-semibold text-[#8B6F47]">
                                {fmtMoney(product.price ?? product.price_raw)}
                              </p>
                            </div>
                          </div>
                          {/* 规格行 */}
                          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-neutral-50 pt-2.5 text-[11px] text-neutral-500">
                            {fmtDim(product.dimensions) && (
                              <span>尺寸 {fmtDim(product.dimensions)}</span>
                            )}
                            <span className="inline-flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {product.lead_time_days ? `${product.lead_time_days} 天交付` : '现货'}
                            </span>
                            <span
                              className={
                                (product.stock ?? 0) > 0
                                  ? 'text-[#5B8A5B]'
                                  : 'text-[#A85B2D]'
                              }
                            >
                              {(product.stock ?? 0) > 0 ? `库存 ${product.stock} 件` : '门店缺货'}
                            </span>
                          </div>
                        </div>
                      ) : (
                        <div className="px-4 py-4 text-xs text-neutral-400">
                          {item.error || '暂未匹配到合适商品，请与导购确认'}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 底部落款 */}
            <div className="mt-8 px-5">
              <div className="rounded-xl bg-[#2B2B2B] text-white px-4 py-4 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">方案编号</p>
                  <p className="text-[11px] text-neutral-400 mt-0.5">{detail?.plan_id}</p>
                </div>
                <ChevronRight className="w-4 h-4 text-neutral-500" />
              </div>
              <p className="mt-4 text-center text-[11px] text-neutral-400">
                本方案由门店 AI 导购生成，价格与库存以门店实际确认为准
              </p>
            </div>
          </>
        ) : (
          <>
            {/* 报价单 Tab */}
            {quoteState === 'loading' && (
              <div className="px-5 mt-10 flex flex-col items-center gap-3 text-sm text-neutral-500">
                <Loader2 className="w-6 h-6 animate-spin text-[#8B6F47]" />
                <p>正在生成报价单…</p>
              </div>
            )}
            {quoteState === 'error' && (
              <div className="px-5 mt-10 text-center">
                <AlertTriangle className="w-8 h-8 mx-auto text-[#C9A87C]" />
                <p className="mt-2 text-sm text-neutral-600">报价单生成失败，请联系门店导购</p>
              </div>
            )}
            {quoteState === 'ready' && q && qSummary && (
              <>
                {/* 报价单头部 */}
                <div className="px-5 mt-4">
                  <div className="rounded-xl border border-[#E7DCC8] bg-[#FBF9F5] p-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-[11px] text-neutral-400">报价单编号</p>
                        <p className="mt-0.5 text-sm font-semibold text-neutral-900">{quote?.quote_id}</p>
                      </div>
                      <span className="inline-flex items-center gap-1 text-[11px] text-[#8B6F47] bg-white border border-[#E7DCC8] rounded-full px-2 py-0.5">
                        <FileText className="w-3 h-3" /> 正式报价
                      </span>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-neutral-500">
                      <div className="flex items-center gap-1.5">
                        <MapPin className="w-3 h-3 text-[#8B6F47]" /> {q.store.store_name}
                      </div>
                      <div className="flex items-center gap-1.5">
                        <UserRound className="w-3 h-3 text-[#8B6F47]" /> 导购 {q.store.sales_name}
                      </div>
                      <div className="flex items-center gap-1.5 col-span-2">
                        <Phone className="w-3 h-3 text-[#8B6F47]" /> {q.store.store_phone}
                      </div>
                    </div>
                  </div>
                </div>

                {/* 报价汇总 */}
                <div className="px-5 mt-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl bg-white shadow-sm border border-neutral-100 p-4">
                      <p className="text-xs text-neutral-400">报价总价</p>
                      <p className="mt-1 text-xl font-semibold text-[#8B6F47]">{fmtMoney(qSummary.total_price)}</p>
                    </div>
                    <div className="rounded-xl bg-white shadow-sm border border-neutral-100 p-4">
                      <p className="text-xs text-neutral-400">交付周期</p>
                      <p className="mt-1 text-xl font-semibold text-neutral-900">
                        {qSummary.max_lead_time_days ? `${qSummary.max_lead_time_days} 天` : '现货'}
                      </p>
                    </div>
                    <div className="rounded-xl bg-white shadow-sm border border-neutral-100 p-4">
                      <p className="text-xs text-neutral-400">现货 / 需调货</p>
                      <p className="mt-1 text-xl font-semibold text-neutral-900">
                        {qSummary.in_stock_count} / {qSummary.out_of_stock_count}
                      </p>
                    </div>
                    <div className="rounded-xl bg-white shadow-sm border border-neutral-100 p-4">
                      <p className="text-xs text-neutral-400">预算核对</p>
                      <p className="mt-1 text-lg font-semibold text-neutral-900">
                        {qSummary.total_price <= qSummary.total_budget ? '预算内' : `超 ${fmtMoney(qSummary.total_price - qSummary.total_budget)}`}
                      </p>
                    </div>
                  </div>
                </div>

                {/* 明细表 */}
                <div className="px-5 mt-6">
                  <h2 className="text-base font-semibold text-neutral-900 flex items-center gap-2">
                    <ReceiptText className="w-4 h-4 text-[#8B6F47]" />
                    报价明细
                    <span className="text-xs font-normal text-neutral-400">{qItems.length} 件</span>
                  </h2>
                  <div className="mt-3 rounded-xl border border-neutral-100 overflow-hidden">
                    <div className="grid grid-cols-[1fr_64px_72px] bg-[#FAF8F5] px-4 py-2.5 text-[11px] text-neutral-400">
                      <span>商品</span>
                      <span className="text-right">交付</span>
                      <span className="text-right">小计</span>
                    </div>
                    {qItems.map((it, idx) => {
                      const p = it.product;
                      return (
                        <div
                          key={`${it.furniture_id}-${idx}`}
                          className="grid grid-cols-[1fr_64px_72px] items-center px-4 py-3 border-t border-neutral-50"
                        >
                          <div className="min-w-0 pr-2">
                            <p className="text-sm font-medium text-neutral-900 leading-snug line-clamp-1">
                              {p.title || it.furniture_label}
                            </p>
                            <p className="mt-0.5 text-[11px] text-neutral-400 line-clamp-1">
                              {it.furniture_label}
                              {p.sku_id ? ` · ${p.sku_id}` : ''}
                              {p.dimensions?.w ? ` · ${fmtDim(p.dimensions)}` : ''}
                            </p>
                            <p className="mt-1 text-[11px]">
                              {it.in_stock ? (
                                <span className="text-[#5B8A5B]">现货</span>
                              ) : (
                                <span className="text-[#A85B2D]">需调货</span>
                              )}
                              <span className="text-neutral-400"> · {fmtMoney(p.price)}/件</span>
                            </p>
                          </div>
                          <div className="text-right text-xs text-neutral-500">
                            {it.lead_time_days ? `${it.lead_time_days}天` : '现货'}
                          </div>
                          <div className="text-right text-sm font-semibold text-[#8B6F47]">
                            {fmtMoney(it.line_total)}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* 合计 */}
                  <div className="mt-3 rounded-xl bg-[#2B2B2B] text-white px-4 py-3 flex items-center justify-between">
                    <span className="text-sm">报价总价</span>
                    <span className="text-lg font-semibold text-[#C9A87C]">{fmtMoney(qSummary.total_price)}</span>
                  </div>

                  {/* 打印按钮 */}
                  <button
                    onClick={() => openQuoteHtml(quote!.quote_id)}
                    className="mt-4 w-full flex items-center justify-center gap-2 rounded-xl bg-[#8B6F47] text-white py-3.5 text-sm font-medium active:scale-[0.98] transition"
                  >
                    <Printer className="w-4 h-4" />
                    打开打印版报价单
                  </button>
                  <p className="mt-3 text-center text-[11px] text-neutral-400">
                    报价单编号 {quote?.quote_id} · 由门店 AI 导购系统自动生成
                  </p>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
