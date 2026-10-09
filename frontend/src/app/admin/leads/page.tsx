'use client';

/**
 * 导购跟进管理页（P2）
 * 路由：/admin/leads
 * 功能：线索列表（分页/搜索/状态筛选）、新建线索、编辑、状态流转、跟进记录填写与查看、删除。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'react-hot-toast';
import {
    ArrowLeft,
    Plus,
    RefreshCw,
    Search,
    Pencil,
    Trash2,
    Save,
    Loader2,
    Users,
    Phone,
    MapPin,
    FileText,
    MessageSquarePlus,
    ChevronLeft,
    ChevronRight,
    CheckCircle2,
} from 'lucide-react';
import { leadList, leadCreate, leadUpdate, leadChangeStatus, leadAddRecord, leadDelete } from '@/lib/api';
import type { LeadItem, LeadStatus, LeadCreatePayload } from '@/lib/types';
import { LEAD_STATUS_LABELS, LEAD_STATUS_COLORS } from '@/lib/types';

const PAGE_SIZE = 10;
const STATUS_OPTIONS: LeadStatus[] = ['new', 'following', 'negotiating', 'won', 'lost'];

const EMPTY_FORM: LeadCreatePayload = {
    customer_name: '',
    phone: '',
    store_name: '',
    plan_id: '',
    status: 'new',
    remark: '',
};

export default function AdminLeadsPage() {
    const [items, setItems] = useState<LeadItem[]>([]);
    const [total, setTotal] = useState(0);
    const [totalPages, setTotalPages] = useState(0);
    const [page, setPage] = useState(1);
    const [keyword, setKeyword] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [loading, setLoading] = useState(false);

    // 新建/编辑表单
    const [showForm, setShowForm] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [form, setForm] = useState<LeadCreatePayload>(EMPTY_FORM);
    const [saving, setSaving] = useState(false);

    // 详情抽屉（含跟进记录）
    const [detailLead, setDetailLead] = useState<LeadItem | null>(null);
    const [recordText, setRecordText] = useState('');
    const [savingRecord, setSavingRecord] = useState(false);

    // 状态流转 loading
    const [statusBusy, setStatusBusy] = useState<string | null>(null);

    const load = useCallback(async (p = page, kw = keyword, st = statusFilter) => {
        setLoading(true);
        try {
            const res = await leadList({ page: p, page_size: PAGE_SIZE, keyword: kw || undefined, status: st || undefined });
            setItems(res.items);
            setTotal(res.total);
            setTotalPages(res.total_pages);
        } catch (e) {
            toast.error(e instanceof Error ? e.message : '加载失败');
        } finally {
            setLoading(false);
        }
    }, [page, keyword, statusFilter]);

    useEffect(() => {
        load(1, keyword, statusFilter);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [page]);

    const refresh = () => load(page, keyword, statusFilter);

    const openCreate = () => {
        setEditingId(null);
        setForm(EMPTY_FORM);
        setShowForm(true);
    };

    const openEdit = (lead: LeadItem) => {
        setEditingId(lead.id);
        setForm({
            customer_name: lead.customer_name,
            phone: lead.phone || '',
            store_name: lead.store_name || '',
            plan_id: lead.plan_id || '',
            status: lead.status,
            remark: lead.remark || '',
        });
        setShowForm(true);
    };

    const submitForm = async () => {
        if (!form.customer_name.trim()) {
            toast.error('请填写顾客姓名');
            return;
        }
        setSaving(true);
        try {
            const payload = {
                ...form,
                customer_name: form.customer_name.trim(),
                phone: form.phone?.trim() || undefined,
                store_name: form.store_name?.trim() || undefined,
                plan_id: form.plan_id?.trim() || undefined,
                remark: form.remark?.trim() || undefined,
            };
            if (editingId) {
                await leadUpdate(editingId, payload);
                toast.success('线索已更新');
            } else {
                await leadCreate(payload);
                toast.success('线索已创建');
            }
            setShowForm(false);
            refresh();
        } catch (e) {
            toast.error(e instanceof Error ? e.message : '保存失败');
        } finally {
            setSaving(false);
        }
    };

    const changeStatus = async (lead: LeadItem, status: LeadStatus) => {
        if (lead.status === status) return;
        setStatusBusy(lead.id);
        try {
            const updated = await leadChangeStatus(lead.id, status);
            toast.success(`状态已流转为「${LEAD_STATUS_LABELS[status]}」`);
            setItems((prev) => prev.map((it) => (it.id === updated.id ? updated : it)));
            setDetailLead((prev) => (prev && prev.id === updated.id ? updated : prev));
        } catch (e) {
            toast.error(e instanceof Error ? e.message : '状态流转失败');
        } finally {
            setStatusBusy(null);
        }
    };

    const submitRecord = async () => {
        if (!detailLead) return;
        if (!recordText.trim()) {
            toast.error('请填写跟进内容');
            return;
        }
        setSavingRecord(true);
        try {
            const updated = await leadAddRecord(detailLead.id, recordText.trim());
            toast.success('跟进记录已添加');
            setDetailLead(updated);
            setItems((prev) => prev.map((it) => (it.id === updated.id ? updated : it)));
            setRecordText('');
        } catch (e) {
            toast.error(e instanceof Error ? e.message : '添加失败');
        } finally {
            setSavingRecord(false);
        }
    };

    const removeLead = async (lead: LeadItem) => {
        if (!window.confirm(`确定删除线索「${lead.customer_name}」？删除后不可恢复。`)) return;
        try {
            await leadDelete(lead.id);
            toast.success('线索已删除');
            setDetailLead(null);
            refresh();
        } catch (e) {
            toast.error(e instanceof Error ? e.message : '删除失败');
        }
    };

    const statusCounts = useMemo(() => {
        const map: Record<string, number> = {};
        for (const it of items) map[it.status] = (map[it.status] || 0) + 1;
        return map;
    }, [items]);

    return (
        <div className="min-h-dvh bg-[#F7F5F2]">
            {/* 顶栏 */}
            <div className="bg-[#2B2B2B] text-white sticky top-0 z-20 shadow-md">
                <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Users className="w-5 h-5 text-[#C9A87C]" />
                        <div>
                            <h1 className="text-base font-semibold">导购跟进管理</h1>
                            <p className="text-[11px] text-neutral-400 mt-0.5">共 {total} 条线索 · 按状态跟踪成交</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={refresh}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-2 text-xs text-neutral-200 hover:bg-white/20 transition"
                        >
                            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> 刷新
                        </button>
                        <button
                            onClick={openCreate}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-[#8B6F47] px-3 py-2 text-xs font-medium hover:bg-[#7A5F3D] transition"
                        >
                            <Plus className="w-3.5 h-3.5" /> 新建线索
                        </button>
                    </div>
                </div>
            </div>

            <div className="mx-auto max-w-6xl px-6 py-6 space-y-5">
                {/* 筛选栏 */}
                <div className="flex flex-wrap items-center gap-3 bg-white rounded-xl border border-neutral-100 p-4 shadow-sm">
                    <div className="relative flex-1 min-w-[220px]">
                        <Search className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                            value={keyword}
                            onChange={(e) => setKeyword(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') { setPage(1); load(1, keyword, statusFilter); } }}
                            placeholder="搜索顾客姓名 / 电话 / 门店"
                            className="w-full rounded-lg border border-neutral-200 pl-9 pr-3 py-2 text-sm outline-none focus:border-[#8B6F47]"
                        />
                    </div>
                    <div className="flex items-center gap-1.5 flex-wrap">
                        <button
                            onClick={() => { setStatusFilter(''); setPage(1); load(1, keyword, ''); }}
                            className={`rounded-full px-3 py-1.5 text-xs border transition ${
                                statusFilter === '' ? 'bg-[#2B2B2B] text-white border-[#2B2B2B]' : 'bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400'
                            }`}
                        >
                            全部
                        </button>
                        {STATUS_OPTIONS.map((s) => (
                            <button
                                key={s}
                                onClick={() => { setStatusFilter(s); setPage(1); load(1, keyword, s); }}
                                className={`rounded-full px-3 py-1.5 text-xs border transition ${
                                    statusFilter === s ? 'bg-[#2B2B2B] text-white border-[#2B2B2B]' : 'bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400'
                                }`}
                            >
                                {LEAD_STATUS_LABELS[s]}
                            </button>
                        ))}
                    </div>
                </div>

                {/* 列表 */}
                <div className="bg-white rounded-xl border border-neutral-100 shadow-sm overflow-hidden">
                    {loading ? (
                        <div className="flex items-center justify-center gap-3 py-16 text-sm text-neutral-500">
                            <Loader2 className="w-5 h-5 animate-spin text-[#8B6F47]" /> 加载中…
                        </div>
                    ) : items.length === 0 ? (
                        <div className="py-16 text-center">
                            <Users className="w-8 h-8 mx-auto text-neutral-300" />
                            <p className="mt-3 text-sm text-neutral-500">暂无线索{keyword || statusFilter ? '，可调整筛选条件' : '，点击右上角新建'}</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-neutral-50">
                            {items.map((lead) => (
                                <div key={lead.id} className="px-5 py-4 flex flex-wrap items-center gap-4 hover:bg-[#FAF8F5] transition">
                                    <div className="flex-1 min-w-[220px]">
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm font-semibold text-neutral-900">{lead.customer_name}</span>
                                            <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] ${LEAD_STATUS_COLORS[lead.status]}`}>
                                                {LEAD_STATUS_LABELS[lead.status]}
                                            </span>
                                        </div>
                                        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-neutral-400">
                                            {lead.phone && <span className="inline-flex items-center gap-1"><Phone className="w-3 h-3" /> {lead.phone}</span>}
                                            {lead.store_name && <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" /> {lead.store_name}</span>}
                                            {lead.plan_id && <span className="inline-flex items-center gap-1"><FileText className="w-3 h-3" /> {lead.plan_id}</span>}
                                            <span className="inline-flex items-center gap-1"><MessageSquarePlus className="w-3 h-3" /> {lead.follow_up_records?.length || 0} 条记录</span>
                                        </div>
                                        {lead.remark && <p className="mt-1 text-[11px] text-neutral-500 line-clamp-1">备注：{lead.remark}</p>}
                                    </div>

                                    {/* 状态流转 */}
                                    <div className="flex items-center gap-1 flex-wrap">
                                        {STATUS_OPTIONS.filter((s) => s !== lead.status).map((s) => (
                                            <button
                                                key={s}
                                                disabled={statusBusy === lead.id}
                                                onClick={() => changeStatus(lead, s)}
                                                className="rounded-lg border border-neutral-200 px-2 py-1 text-[11px] text-neutral-600 hover:border-[#8B6F47] hover:text-[#8B6F47] disabled:opacity-50 transition"
                                            >
                                                {statusBusy === lead.id ? <Loader2 className="w-3 h-3 animate-spin inline" /> : null}
                                                转为{LEAD_STATUS_LABELS[s]}
                                            </button>
                                        ))}
                                    </div>

                                    <div className="flex items-center gap-1.5">
                                        <button
                                            onClick={() => setDetailLead(lead)}
                                            className="inline-flex items-center gap-1 rounded-lg bg-[#F5F0E8] px-2.5 py-1.5 text-[11px] text-neutral-700 hover:bg-[#E7DCC8] transition"
                                        >
                                            跟进
                                        </button>
                                        <button
                                            onClick={() => openEdit(lead)}
                                            className="inline-flex items-center gap-1 rounded-lg bg-white border border-neutral-200 px-2.5 py-1.5 text-[11px] text-neutral-600 hover:border-[#8B6F47] hover:text-[#8B6F47] transition"
                                        >
                                            <Pencil className="w-3 h-3" /> 编辑
                                        </button>
                                        <button
                                            onClick={() => removeLead(lead)}
                                            className="inline-flex items-center gap-1 rounded-lg bg-white border border-neutral-200 px-2.5 py-1.5 text-[11px] text-neutral-400 hover:border-red-300 hover:text-red-500 transition"
                                        >
                                            <Trash2 className="w-3 h-3" /> 删除
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* 分页 */}
                    {totalPages > 1 && (
                        <div className="flex items-center justify-between px-5 py-3 border-t border-neutral-50 text-xs text-neutral-500">
                            <span>第 {page}/{totalPages} 页 · 共 {total} 条</span>
                            <div className="flex items-center gap-1">
                                <button
                                    disabled={page <= 1}
                                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                                    className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 px-2.5 py-1.5 hover:border-[#8B6F47] disabled:opacity-40 transition"
                                >
                                    <ChevronLeft className="w-3.5 h-3.5" /> 上一页
                                </button>
                                <button
                                    disabled={page >= totalPages}
                                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                                    className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 px-2.5 py-1.5 hover:border-[#8B6F47] disabled:opacity-40 transition"
                                >
                                    下一页 <ChevronRight className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        </div>
                    )}
                </div>

                <p className="text-[11px] text-neutral-400 text-center">
                    {Object.entries(statusCounts).map(([s, c]) => (
                        <span key={s} className="mx-1.5">
                            {LEAD_STATUS_LABELS[s as LeadStatus]} <b className="text-neutral-600">{c}</b>
                        </span>
                    ))}
                </p>
            </div>

            {/* 新建/编辑弹窗 */}
            {showForm && (
                <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 p-4" onClick={() => !saving && setShowForm(false)}>
                    <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-between">
                            <h2 className="text-base font-semibold text-neutral-900">
                                {editingId ? '编辑线索' : '新建线索'}
                            </h2>
                            <button onClick={() => !saving && setShowForm(false)} className="text-neutral-400 hover:text-neutral-600">
                                <ArrowLeft className="w-4 h-4" />
                            </button>
                        </div>
                        <div className="mt-5 space-y-4">
                            <div>
                                <label className="text-xs text-neutral-500">顾客姓名 *</label>
                                <input
                                    value={form.customer_name}
                                    onChange={(e) => setForm({ ...form, customer_name: e.target.value })}
                                    placeholder="如：张女士"
                                    className="mt-1 w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm outline-none focus:border-[#8B6F47]"
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs text-neutral-500">电话</label>
                                    <input
                                        value={form.phone}
                                        onChange={(e) => setForm({ ...form, phone: e.target.value })}
                                        placeholder="手机号"
                                        className="mt-1 w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm outline-none focus:border-[#8B6F47]"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs text-neutral-500">门店</label>
                                    <input
                                        value={form.store_name}
                                        onChange={(e) => setForm({ ...form, store_name: e.target.value })}
                                        placeholder="如：旗舰店"
                                        className="mt-1 w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm outline-none focus:border-[#8B6F47]"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="text-xs text-neutral-500">关联方案ID</label>
                                <input
                                    value={form.plan_id}
                                    onChange={(e) => setForm({ ...form, plan_id: e.target.value })}
                                    placeholder="方案编号（可选）"
                                    className="mt-1 w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm outline-none focus:border-[#8B6F47]"
                                />
                            </div>
                            <div>
                                <label className="text-xs text-neutral-500">状态</label>
                                <div className="mt-1.5 flex flex-wrap gap-1.5">
                                    {STATUS_OPTIONS.map((s) => (
                                        <button
                                            key={s}
                                            type="button"
                                            onClick={() => setForm({ ...form, status: s })}
                                            className={`rounded-full px-3 py-1.5 text-xs border transition ${
                                                form.status === s ? 'bg-[#2B2B2B] text-white border-[#2B2B2B]' : 'bg-white text-neutral-600 border-neutral-200'
                                            }`}
                                        >
                                            {LEAD_STATUS_LABELS[s]}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <label className="text-xs text-neutral-500">备注</label>
                                <textarea
                                    value={form.remark}
                                    onChange={(e) => setForm({ ...form, remark: e.target.value })}
                                    rows={3}
                                    placeholder="补充说明（可选）"
                                    className="mt-1 w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm outline-none focus:border-[#8B6F47] resize-none"
                                />
                            </div>
                        </div>
                        <div className="mt-6 flex gap-3">
                            <button
                                onClick={() => !saving && setShowForm(false)}
                                className="flex-1 rounded-xl border border-neutral-200 py-2.5 text-sm text-neutral-600 hover:bg-neutral-50 transition"
                            >
                                取消
                            </button>
                            <button
                                onClick={submitForm}
                                disabled={saving}
                                className="flex-1 rounded-xl bg-[#8B6F47] py-2.5 text-sm font-medium text-white hover:bg-[#7A5F3D] disabled:opacity-60 transition inline-flex items-center justify-center gap-1.5"
                            >
                                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                                {editingId ? '保存修改' : '创建线索'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* 跟进详情抽屉 */}
            {detailLead && (
                <div className="fixed inset-0 z-30 flex justify-end bg-black/40" onClick={() => setDetailLead(null)}>
                    <div
                        className="w-full max-w-md h-full bg-white shadow-2xl overflow-y-auto"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="bg-[#2B2B2B] text-white px-6 py-5 flex items-center justify-between sticky top-0 z-10">
                            <div>
                                <div className="flex items-center gap-2">
                                    <h2 className="text-base font-semibold">{detailLead.customer_name}</h2>
                                    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] ${LEAD_STATUS_COLORS[detailLead.status]}`}>
                                        {LEAD_STATUS_LABELS[detailLead.status]}
                                    </span>
                                </div>
                                <p className="text-[11px] text-neutral-400 mt-1">线索编号 {detailLead.id}</p>
                            </div>
                            <button onClick={() => setDetailLead(null)} className="text-neutral-400 hover:text-white">
                                <ArrowLeft className="w-4 h-4" />
                            </button>
                        </div>

                        <div className="px-6 py-5 space-y-5">
                            {/* 基本信息 */}
                            <div className="grid grid-cols-2 gap-3">
                                <div className="rounded-xl border border-neutral-100 p-3">
                                    <p className="text-[11px] text-neutral-400">电话</p>
                                    <p className="mt-1 text-sm text-neutral-800">{detailLead.phone || '—'}</p>
                                </div>
                                <div className="rounded-xl border border-neutral-100 p-3">
                                    <p className="text-[11px] text-neutral-400">门店</p>
                                    <p className="mt-1 text-sm text-neutral-800">{detailLead.store_name || '—'}</p>
                                </div>
                                <div className="rounded-xl border border-neutral-100 p-3 col-span-2">
                                    <p className="text-[11px] text-neutral-400">关联方案</p>
                                    <p className="mt-1 text-sm text-neutral-800">{detailLead.plan_id || '—'}</p>
                                </div>
                                <div className="rounded-xl border border-neutral-100 p-3 col-span-2">
                                    <p className="text-[11px] text-neutral-400">备注</p>
                                    <p className="mt-1 text-sm text-neutral-800">{detailLead.remark || '—'}</p>
                                </div>
                            </div>

                            {/* 状态流转 */}
                            <div>
                                <h3 className="text-sm font-semibold text-neutral-800">状态流转</h3>
                                <div className="mt-2 flex flex-wrap gap-1.5">
                                    {STATUS_OPTIONS.map((s) => {
                                        const active = detailLead.status === s;
                                        return (
                                            <button
                                                key={s}
                                                disabled={statusBusy === detailLead.id}
                                                onClick={() => changeStatus(detailLead, s)}
                                                className={`rounded-full px-3 py-1.5 text-xs border transition ${
                                                    active
                                                        ? 'bg-[#8B6F47] text-white border-[#8B6F47]'
                                                        : 'bg-white text-neutral-600 border-neutral-200 hover:border-[#8B6F47]'
                                                }`}
                                            >
                                                {active && <CheckCircle2 className="w-3 h-3 inline mr-1" />}
                                                {LEAD_STATUS_LABELS[s]}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* 跟进记录 */}
                            <div>
                                <h3 className="text-sm font-semibold text-neutral-800">跟进记录</h3>
                                <div className="mt-2 space-y-2">
                                    {detailLead.follow_up_records?.length === 0 ? (
                                        <p className="text-xs text-neutral-400 py-3 text-center">暂无跟进记录</p>
                                    ) : (
                                        detailLead.follow_up_records.map((r, idx) => (
                                            <div key={idx} className="rounded-xl bg-[#FAF8F5] border border-neutral-100 p-3">
                                                <p className="text-sm text-neutral-800 leading-relaxed">{r.content}</p>
                                                <p className="mt-1.5 text-[11px] text-neutral-400">
                                                    {new Date(r.created_at).toLocaleString('zh-CN')}
                                                </p>
                                            </div>
                                        ))
                                    )}
                                </div>
                                <div className="mt-3 flex gap-2">
                                    <textarea
                                        value={recordText}
                                        onChange={(e) => setRecordText(e.target.value)}
                                        rows={2}
                                        placeholder="记录本次跟进内容…"
                                        className="flex-1 rounded-lg border border-neutral-200 px-3 py-2 text-sm outline-none focus:border-[#8B6F47] resize-none"
                                    />
                                    <button
                                        onClick={submitRecord}
                                        disabled={savingRecord || !recordText.trim()}
                                        className="inline-flex items-center gap-1 rounded-lg bg-[#8B6F47] px-3 py-2 text-xs font-medium text-white hover:bg-[#7A5F3D] disabled:opacity-50 transition"
                                    >
                                        {savingRecord ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <MessageSquarePlus className="w-3.5 h-3.5" />}
                                        添加
                                    </button>
                                </div>
                            </div>

                            <p className="text-[11px] text-neutral-400">
                                创建于 {new Date(detailLead.created_at).toLocaleString('zh-CN')}
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
