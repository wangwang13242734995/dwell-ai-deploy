'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'react-hot-toast';
import {
    ArrowLeft,
    Plus,
    Upload,
    RefreshCw,
    Search,
    Pencil,
    Trash2,
    Save,
    Loader2,
    Boxes,
    AlertTriangle,
} from 'lucide-react';
import {
    adminListSkus,
    adminCategories,
    adminCreateSku,
    adminUpdateSku,
    adminQuickUpdate,
    adminDeleteSku,
    adminImportSkus,
} from '@/lib/api';
import type {
    AdminSkuItem,
    AdminSkuPayload,
    AdminCategoryCount,
    AdminImportResponse,
} from '@/lib/types';

const PAGE_SIZE = 10;
const CATEGORY_OPTIONS = ['客厅', '卧室', '餐厅', '书房', '玄关', '软装'];

interface QuickDraft {
    price: string;
    stock: string;
    lead_time_days: string;
}

interface FormState {
    id: string;
    name: string;
    category: string;
    subcategory: string;
    material: string;
    color: string;
    style: string;
    dim_w: string;
    dim_d: string;
    dim_h: string;
    unit: string;
    price: string;
    stock: string;
    lead_time_days: string;
    space_tags: string;
    keywords: string;
    image_url: string;
}

const EMPTY_FORM: FormState = {
    id: '',
    name: '',
    category: '客厅',
    subcategory: '',
    material: '',
    color: '',
    style: '',
    dim_w: '',
    dim_d: '',
    dim_h: '',
    unit: 'cm',
    price: '',
    stock: '0',
    lead_time_days: '7',
    space_tags: '',
    keywords: '',
    image_url: '',
};

function itemToForm(item: AdminSkuItem): FormState {
    return {
        id: item.id,
        name: item.name,
        category: item.category,
        subcategory: item.subcategory || '',
        material: item.material || '',
        color: item.color || '',
        style: item.style || '',
        dim_w: item.dimensions?.w != null ? String(item.dimensions.w) : '',
        dim_d: item.dimensions?.d != null ? String(item.dimensions.d) : '',
        dim_h: item.dimensions?.h != null ? String(item.dimensions.h) : '',
        unit: item.dimensions?.unit || 'cm',
        price: String(item.price),
        stock: String(item.stock),
        lead_time_days: String(item.lead_time_days),
        space_tags: (item.space_list || []).join('|'),
        keywords: '',
        image_url: item.image_url || '',
    };
}

export default function AdminSkuPage() {
    const [items, setItems] = useState<AdminSkuItem[]>([]);
    const [total, setTotal] = useState(0);
    const [totalPages, setTotalPages] = useState(0);
    const [page, setPage] = useState(1);
    const [keyword, setKeyword] = useState('');
    const [category, setCategory] = useState('');
    const [inStockOnly, setInStockOnly] = useState(false);
    const [categories, setCategories] = useState<AdminCategoryCount[]>([]);
    const [loading, setLoading] = useState(false);
    const [savingId, setSavingId] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [importing, setImporting] = useState(false);
    const [importResult, setImportResult] = useState<AdminImportResponse | null>(null);

    // 行内快速调整草稿：key=skuId
    const [drafts, setDrafts] = useState<Record<string, QuickDraft>>({});

    // 新增/编辑表单
    const [formOpen, setFormOpen] = useState(false);
    const [editing, setEditing] = useState<AdminSkuItem | null>(null);
    const [form, setForm] = useState<FormState>(EMPTY_FORM);
    const [formSaving, setFormSaving] = useState(false);

    const fileInputRef = useRef<HTMLInputElement>(null);

    const loadList = useCallback(async () => {
        setLoading(true);
        try {
            const data = await adminListSkus({
                page,
                page_size: PAGE_SIZE,
                keyword: keyword.trim() || undefined,
                category: category || undefined,
                in_stock: inStockOnly || undefined,
            });
            setItems(data.items);
            setTotal(data.total);
            setTotalPages(data.total_pages);
        } catch (e) {
            toast.error(e instanceof Error ? e.message : '加载失败');
        } finally {
            setLoading(false);
        }
    }, [page, keyword, category, inStockOnly]);

    const loadCategories = useCallback(async () => {
        try {
            setCategories(await adminCategories());
        } catch {
            // 忽略：筛选下拉仍可用默认品类
        }
    }, []);

    useEffect(() => {
        loadList();
    }, [loadList]);

    useEffect(() => {
        loadCategories();
    }, [loadCategories]);

    const draftFor = (item: AdminSkuItem): QuickDraft =>
        drafts[item.id] || {
            price: String(item.price),
            stock: String(item.stock),
            lead_time_days: String(item.lead_time_days),
        };

    const setDraft = (id: string, patch: Partial<QuickDraft>) => {
        setDrafts(prev => ({
            ...prev,
            [id]: { ...draftForById(id), ...patch },
        }));
    };

    // 注意：draftForById 在 setDrafts 内不可用当前 items，直接由调用处兜底
    function draftForById(id: string): QuickDraft {
        const item = items.find(i => i.id === id);
        if (!item) return { price: '', stock: '', lead_time_days: '' };
        return {
            price: String(item.price),
            stock: String(item.stock),
            lead_time_days: String(item.lead_time_days),
        };
    }

    const handleQuickSave = async (item: AdminSkuItem) => {
        const d = draftFor(item);
        const price = Number(d.price);
        const stock = Number(d.stock);
        const lead = Number(d.lead_time_days);
        if (Number.isNaN(price) || price < 0) {
            toast.error('价格需为非负数字');
            return;
        }
        if (Number.isNaN(stock) || stock < 0) {
            toast.error('库存需为非负整数');
            return;
        }
        if (Number.isNaN(lead) || lead < 0) {
            toast.error('交付周期需为非负整数');
            return;
        }
        setSavingId(item.id);
        try {
            await adminQuickUpdate(item.id, {
                price,
                stock: Math.round(stock),
                lead_time_days: Math.round(lead),
            });
            toast.success(`已更新 ${item.id} 库存价格`);
            setDrafts(prev => {
                const next = { ...prev };
                delete next[item.id];
                return next;
            });
            await loadList();
            await loadCategories();
        } catch (e) {
            toast.error(e instanceof Error ? e.message : '保存失败');
        } finally {
            setSavingId(null);
        }
    };

    const openCreate = () => {
        setEditing(null);
        setForm(EMPTY_FORM);
        setFormOpen(true);
    };

    const openEdit = (item: AdminSkuItem) => {
        setEditing(item);
        setForm(itemToForm(item));
        setFormOpen(true);
    };

    const handleFormSubmit = async () => {
        if (!form.name.trim()) {
            toast.error('商品名称不能为空');
            return;
        }
        if (!form.category.trim()) {
            toast.error('品类不能为空');
            return;
        }
        if (form.price === '' || Number.isNaN(Number(form.price)) || Number(form.price) < 0) {
            toast.error('价格需为非负数字');
            return;
        }
        const payload: AdminSkuPayload = {
            id: form.id.trim(),
            name: form.name.trim(),
            category: form.category.trim(),
            subcategory: form.subcategory.trim() || undefined,
            material: form.material.trim() || undefined,
            color: form.color.trim() || undefined,
            style: form.style.trim() || undefined,
            dim_w: form.dim_w !== '' ? Number(form.dim_w) : undefined,
            dim_d: form.dim_d !== '' ? Number(form.dim_d) : undefined,
            dim_h: form.dim_h !== '' ? Number(form.dim_h) : undefined,
            unit: form.unit.trim() || 'cm',
            price: Number(form.price),
            stock: Math.round(Number(form.stock) || 0),
            lead_time_days: Math.round(Number(form.lead_time_days) || 0),
            space_tags: form.space_tags.trim() || undefined,
            keywords: form.keywords.trim() || undefined,
            image_url: form.image_url.trim() || undefined,
        };
        setFormSaving(true);
        try {
            if (editing) {
                await adminUpdateSku(editing.id, payload);
                toast.success(`已保存 ${editing.id}`);
            } else {
                if (!payload.id) {
                    toast.error('新增时商品 ID 不能为空');
                    setFormSaving(false);
                    return;
                }
                await adminCreateSku(payload);
                toast.success('已新增 SKU');
            }
            setFormOpen(false);
            await loadList();
            await loadCategories();
        } catch (e) {
            toast.error(e instanceof Error ? e.message : '保存失败');
        } finally {
            setFormSaving(false);
        }
    };

    const handleDelete = async (item: AdminSkuItem) => {
        if (!window.confirm(`确认删除 SKU「${item.name}」(ID: ${item.id})？删除后不可恢复。`)) {
            return;
        }
        setDeletingId(item.id);
        try {
            await adminDeleteSku(item.id);
            toast.success(`已删除 ${item.id}`);
            await loadList();
            await loadCategories();
        } catch (e) {
            toast.error(e instanceof Error ? e.message : '删除失败');
        } finally {
            setDeletingId(null);
        }
    };

    const handleImportFile = async (file: File | undefined) => {
        if (!file) return;
        setImporting(true);
        setImportResult(null);
        try {
            const result = await adminImportSkus(file);
            setImportResult(result);
            toast.success(`导入完成：新增 ${result.created}，更新 ${result.updated}`);
            await loadList();
            await loadCategories();
        } catch (e) {
            toast.error(e instanceof Error ? e.message : '导入失败');
        } finally {
            setImporting(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const categoryOptions = useMemo(() => {
        const fromApi = categories.map(c => c.category);
        const merged = [...CATEGORY_OPTIONS, ...fromApi.filter(c => !CATEGORY_OPTIONS.includes(c))];
        return Array.from(new Set(merged));
    }, [categories]);

    const outOfStockCount = useMemo(
        () => items.filter(i => i.stock === 0).length,
        [items]
    );

    const inputCls =
        'w-full px-3 py-2 border border-gray-200 text-sm focus:outline-none focus:border-black transition-colors rounded-lg';
    const labelCls = 'block text-xs font-semibold text-gray-500 uppercase tracking-widest mb-1.5';

    return (
        <div className="min-h-screen bg-white">
            {/* Header */}
            <header className="py-5 border-b border-gray-100 sticky top-0 bg-white/90 backdrop-blur z-40">
                <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <a
                            href="/"
                            className="p-2 bg-black text-white rounded-full hover:bg-gray-800 transition-colors"
                            title="返回导购前台"
                        >
                            <ArrowLeft className="w-4 h-4" />
                        </a>
                        <div>
                            <h1 className="text-xl font-bold text-black tracking-tight flex items-center gap-2">
                                <Boxes className="w-5 h-5" />
                                SKU 管理后台
                            </h1>
                            <p className="text-xs text-gray-400">门店商品库 · 库存价格同步 · 导购方案数据源</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => {
                                setKeyword('');
                                setCategory('');
                                setInStockOnly(false);
                                setPage(1);
                            }}
                            className="px-4 py-2 text-sm border border-gray-200 text-gray-600 hover:border-black hover:text-black transition-colors flex items-center gap-1.5 rounded-full"
                        >
                            <RefreshCw className="w-3.5 h-3.5" />
                            重置
                        </button>
                        <button
                            onClick={openCreate}
                            className="px-5 py-2 bg-black text-white text-sm font-medium hover:bg-gray-800 transition-colors flex items-center gap-1.5 rounded-full"
                        >
                            <Plus className="w-4 h-4" />
                            新增 SKU
                        </button>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
                {/* 统计条 */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="border border-gray-100 p-4">
                        <div className="text-2xl font-bold text-black">{total}</div>
                        <div className="text-xs text-gray-400 mt-1">商品总数</div>
                    </div>
                    <div className="border border-gray-100 p-4">
                        <div className="text-2xl font-bold text-black">{categories.length}</div>
                        <div className="text-xs text-gray-400 mt-1">品类数</div>
                    </div>
                    <div className="border border-gray-100 p-4">
                        <div className="text-2xl font-bold text-amber-600">
                            {categories.reduce((sum, c) => sum + c.count, 0)}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">库内 SKU 总条数</div>
                    </div>
                    <div className="border border-gray-100 p-4">
                        <div className="text-2xl font-bold text-red-500">{outOfStockCount}</div>
                        <div className="text-xs text-gray-400 mt-1">当前页缺货数</div>
                    </div>
                </div>

                {/* 筛选栏 */}
                <div className="flex flex-col lg:flex-row items-stretch lg:items-end gap-3 p-5 border border-gray-100 bg-gray-50/50">
                    <div className="flex-1 min-w-[200px]">
                        <label className={labelCls}>关键词</label>
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                            <input
                                value={keyword}
                                onChange={e => setKeyword(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter') { setPage(1); loadList(); } }}
                                placeholder="ID / 名称 / 材质 / 风格..."
                                className={`${inputCls} pl-9`}
                            />
                        </div>
                    </div>
                    <div className="w-full lg:w-48">
                        <label className={labelCls}>品类</label>
                        <select
                            value={category}
                            onChange={e => { setCategory(e.target.value); setPage(1); }}
                            className={inputCls}
                        >
                            <option value="">全部品类</option>
                            {categoryOptions.map(c => (
                                <option key={c} value={c}>{c}</option>
                            ))}
                        </select>
                    </div>
                    <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer pb-2.5">
                        <input
                            type="checkbox"
                            checked={inStockOnly}
                            onChange={e => { setInStockOnly(e.target.checked); setPage(1); }}
                            className="w-4 h-4 accent-black"
                        />
                        仅看有库存
                    </label>
                    <button
                        onClick={() => { setPage(1); loadList(); }}
                        className="px-6 py-2.5 bg-black text-white text-sm font-medium hover:bg-gray-800 transition-colors flex items-center gap-1.5 rounded-full"
                    >
                        <Search className="w-4 h-4" />
                        查询
                    </button>
                    <div className="flex items-center gap-2 pb-1">
                        <button
                            onClick={() => fileInputRef.current?.click()}
                            disabled={importing}
                            className="px-5 py-2.5 border border-gray-300 text-sm text-gray-700 hover:border-black hover:text-black transition-colors flex items-center gap-1.5 disabled:opacity-50 rounded-full"
                        >
                            {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                            CSV 导入
                        </button>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".csv"
                            className="hidden"
                            onChange={e => handleImportFile(e.target.files?.[0])}
                        />
                    </div>
                </div>

                {/* CSV 导入结果 */}
                {importResult && (
                    <div className="border border-gray-100 p-4 bg-gray-50/50 text-sm">
                        <div className="font-semibold text-black mb-2 flex items-center gap-2">
                            <Upload className="w-4 h-4" />
                            CSV 导入结果
                        </div>
                        <div className="flex gap-6">
                            <span>新增 <b className="text-green-600">{importResult.created}</b></span>
                            <span>更新 <b className="text-blue-600">{importResult.updated}</b></span>
                            <span>跳过 <b className="text-red-500">{importResult.skipped}</b></span>
                        </div>
                        {importResult.errors.length > 0 && (
                            <div className="mt-2 text-xs text-red-500 max-h-32 overflow-y-auto space-y-0.5">
                                {importResult.errors.slice(0, 20).map((err, i) => (
                                    <div key={i}>{err}</div>
                                ))}
                                {importResult.errors.length > 20 && (
                                    <div>...共 {importResult.errors.length} 条错误</div>
                                )}
                            </div>
                        )}
                        <p className="mt-2 text-xs text-gray-400">
                            表头：id,name,category,subcategory,material,color,style,dim_w,dim_d,dim_h,unit,price,stock,lead_time_days,space_tags,keywords,image_url
                        </p>
                    </div>
                )}

                {/* 商品列表 */}
                <div className="border border-gray-100 overflow-x-auto">
                    <table className="w-full text-sm min-w-[1080px]">
                        <thead>
                            <tr className="border-b border-gray-100 bg-gray-50/50 text-left text-xs uppercase tracking-wider text-gray-500">
                                <th className="px-4 py-3 font-semibold">ID</th>
                                <th className="px-4 py-3 font-semibold">名称</th>
                                <th className="px-4 py-3 font-semibold">品类</th>
                                <th className="px-4 py-3 font-semibold w-32">价格 (¥)</th>
                                <th className="px-4 py-3 font-semibold w-28">库存</th>
                                <th className="px-4 py-3 font-semibold w-24">交期(天)</th>
                                <th className="px-4 py-3 font-semibold">适用空间</th>
                                <th className="px-4 py-3 font-semibold text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items.map(item => {
                                const draft = draftFor(item);
                                return (
                                    <tr key={item.id} className="border-b border-gray-50 hover:bg-gray-50/40 transition-colors">
                                        <td className="px-4 py-3 font-mono text-xs text-gray-500">{item.id}</td>
                                        <td className="px-4 py-3">
                                            <div className="font-medium text-gray-800">{item.name}</div>
                                            <div className="text-xs text-gray-400">
                                                {[item.style, item.material, item.color].filter(Boolean).join(' · ') || '—'}
                                            </div>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
                                                {item.category}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <input
                                                type="number"
                                                value={draft.price}
                                                onChange={e => setDraft(item.id, { price: e.target.value })}
                                                className="w-full px-2 py-1.5 border border-gray-200 text-sm focus:outline-none focus:border-black rounded-lg"
                                            />
                                        </td>
                                        <td className="px-4 py-3">
                                            <input
                                                type="number"
                                                value={draft.stock}
                                                onChange={e => setDraft(item.id, { stock: e.target.value })}
                                                className={`w-full px-2 py-1.5 border border-gray-200 text-sm focus:outline-none focus:border-black rounded-lg ${item.stock === 0 ? 'text-red-500 font-semibold' : ''}`}
                                            />
                                        </td>
                                        <td className="px-4 py-3">
                                            <input
                                                type="number"
                                                value={draft.lead_time_days}
                                                onChange={e => setDraft(item.id, { lead_time_days: e.target.value })}
                                                className="w-full px-2 py-1.5 border border-gray-200 text-sm focus:outline-none focus:border-black rounded-lg"
                                            />
                                        </td>
                                        <td className="px-4 py-3 text-xs text-gray-500">
                                            {item.space_list?.length ? item.space_list.join('、') : '—'}
                                            {item.stock === 0 && (
                                                <span className="ml-2 inline-flex items-center gap-1 text-red-500 font-medium">
                                                    <AlertTriangle className="w-3 h-3" />
                                                    缺货
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex items-center justify-end gap-2">
                                                <button
                                                    onClick={() => handleQuickSave(item)}
                                                    disabled={savingId === item.id}
                                                    className="px-3 py-1.5 text-xs border border-black text-black hover:bg-black hover:text-white transition-colors disabled:opacity-50 flex items-center gap-1 rounded-full"
                                                    title="保存库存价格"
                                                >
                                                    {savingId === item.id ? (
                                                        <Loader2 className="w-3 h-3 animate-spin" />
                                                    ) : (
                                                        <Save className="w-3 h-3" />
                                                    )}
                                                    保存
                                                </button>
                                                <button
                                                    onClick={() => openEdit(item)}
                                                    className="p-1.5 text-gray-500 hover:text-black transition-colors"
                                                    title="编辑"
                                                >
                                                    <Pencil className="w-4 h-4" />
                                                </button>
                                                <button
                                                    onClick={() => handleDelete(item)}
                                                    disabled={deletingId === item.id}
                                                    className="p-1.5 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
                                                    title="删除"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                            {items.length === 0 && !loading && (
                                <tr>
                                    <td colSpan={8} className="px-4 py-12 text-center text-gray-400">
                                        未找到匹配的商品，请调整筛选条件。
                                    </td>
                                </tr>
                            )}
                            {loading && (
                                <tr>
                                    <td colSpan={8} className="px-4 py-12 text-center">
                                        <Loader2 className="w-6 h-6 animate-spin text-gray-400 mx-auto" />
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {/* 分页 */}
                <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-400">
                        共 <b className="text-gray-600">{total}</b> 条商品 · 第 {page}/{totalPages || 1} 页
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setPage(p => Math.max(1, p - 1))}
                            disabled={page <= 1}
                            className="px-4 py-2 text-sm border border-gray-200 text-gray-600 hover:border-black hover:text-black transition-colors disabled:opacity-40 rounded-full"
                        >
                            上一页
                        </button>
                        <button
                            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                            disabled={page >= totalPages}
                            className="px-4 py-2 text-sm border border-gray-200 text-gray-600 hover:border-black hover:text-black transition-colors disabled:opacity-40 rounded-full"
                        >
                            下一页
                        </button>
                    </div>
                </div>
            </main>

            {/* 新增/编辑表单 Modal */}
            {formOpen && (
                <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/30 p-4 sm:p-8">
                    <div className="w-full max-w-2xl bg-white border border-gray-100 shadow-2xl my-8">
                        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                            <h2 className="text-lg font-bold text-black">
                                {editing ? `编辑 SKU：${editing.id}` : '新增 SKU'}
                            </h2>
                            <button
                                onClick={() => setFormOpen(false)}
                                className="text-gray-400 hover:text-black text-xl leading-none transition-colors"
                            >
                                ×
                            </button>
                        </div>

                        <div className="px-6 py-5 grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                                <label className={labelCls}>商品 ID *</label>
                                <input
                                    value={form.id}
                                    disabled={!!editing}
                                    onChange={e => setForm(f => ({ ...f, id: e.target.value }))}
                                    placeholder="如 SKU-XX-001"
                                    className={`${inputCls} ${editing ? 'bg-gray-50 text-gray-400' : ''}`}
                                />
                                {editing && <p className="text-xs text-gray-400 mt-1">ID 不可修改</p>}
                            </div>
                            <div>
                                <label className={labelCls}>商品名称 *</label>
                                <input
                                    value={form.name}
                                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                                    placeholder="如 云朵三人位布艺沙发 2.4m"
                                    className={inputCls}
                                />
                            </div>
                            <div>
                                <label className={labelCls}>品类 *</label>
                                <select
                                    value={form.category}
                                    onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                                    className={inputCls}
                                >
                                    {CATEGORY_OPTIONS.map(c => (
                                        <option key={c} value={c}>{c}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className={labelCls}>子品类</label>
                                <input
                                    value={form.subcategory}
                                    onChange={e => setForm(f => ({ ...f, subcategory: e.target.value }))}
                                    placeholder="如 沙发 / 茶几 / 床"
                                    className={inputCls}
                                />
                            </div>
                            <div>
                                <label className={labelCls}>材质</label>
                                <input
                                    value={form.material}
                                    onChange={e => setForm(f => ({ ...f, material: e.target.value }))}
                                    placeholder="如 科技布"
                                    className={inputCls}
                                />
                            </div>
                            <div>
                                <label className={labelCls}>颜色</label>
                                <input
                                    value={form.color}
                                    onChange={e => setForm(f => ({ ...f, color: e.target.value }))}
                                    placeholder="如 米白"
                                    className={inputCls}
                                />
                            </div>
                            <div>
                                <label className={labelCls}>风格</label>
                                <input
                                    value={form.style}
                                    onChange={e => setForm(f => ({ ...f, style: e.target.value }))}
                                    placeholder="如 现代简约"
                                    className={inputCls}
                                />
                            </div>
                            <div>
                                <label className={labelCls}>适用空间（竖线分隔）</label>
                                <input
                                    value={form.space_tags}
                                    onChange={e => setForm(f => ({ ...f, space_tags: e.target.value }))}
                                    placeholder="如 客厅|卧室"
                                    className={inputCls}
                                />
                            </div>
                            <div className="grid grid-cols-4 gap-2">
                                <div>
                                    <label className={labelCls}>宽</label>
                                    <input type="number" value={form.dim_w} onChange={e => setForm(f => ({ ...f, dim_w: e.target.value }))} className={inputCls} />
                                </div>
                                <div>
                                    <label className={labelCls}>深</label>
                                    <input type="number" value={form.dim_d} onChange={e => setForm(f => ({ ...f, dim_d: e.target.value }))} className={inputCls} />
                                </div>
                                <div>
                                    <label className={labelCls}>高</label>
                                    <input type="number" value={form.dim_h} onChange={e => setForm(f => ({ ...f, dim_h: e.target.value }))} className={inputCls} />
                                </div>
                                <div>
                                    <label className={labelCls}>单位</label>
                                    <input value={form.unit} onChange={e => setForm(f => ({ ...f, unit: e.target.value }))} className={inputCls} />
                                </div>
                            </div>
                            <div>
                                <label className={labelCls}>价格 (¥) *</label>
                                <input type="number" value={form.price} onChange={e => setForm(f => ({ ...f, price: e.target.value }))} className={inputCls} />
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                                <div>
                                    <label className={labelCls}>库存 *</label>
                                    <input type="number" value={form.stock} onChange={e => setForm(f => ({ ...f, stock: e.target.value }))} className={inputCls} />
                                </div>
                                <div>
                                    <label className={labelCls}>交付周期(天)</label>
                                    <input type="number" value={form.lead_time_days} onChange={e => setForm(f => ({ ...f, lead_time_days: e.target.value }))} className={inputCls} />
                                </div>
                            </div>
                            <div className="sm:col-span-2">
                                <label className={labelCls}>检索关键词</label>
                                <input
                                    value={form.keywords}
                                    onChange={e => setForm(f => ({ ...f, keywords: e.target.value }))}
                                    placeholder="空格分隔，如 沙发 布艺 现代"
                                    className={inputCls}
                                />
                            </div>
                            <div className="sm:col-span-2">
                                <label className={labelCls}>图片 URL</label>
                                <input
                                    value={form.image_url}
                                    onChange={e => setForm(f => ({ ...f, image_url: e.target.value }))}
                                    placeholder="https://..."
                                    className={inputCls}
                                />
                            </div>
                        </div>

                        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100">
                            <button
                                onClick={() => setFormOpen(false)}
                                className="px-5 py-2.5 text-sm text-gray-500 hover:text-black transition-colors rounded-full"
                            >
                                取消
                            </button>
                            <button
                                onClick={handleFormSubmit}
                                disabled={formSaving}
                                className="px-6 py-2.5 bg-black text-white text-sm font-medium hover:bg-gray-800 transition-colors disabled:opacity-50 flex items-center gap-2 rounded-full"
                            >
                                {formSaving && <Loader2 className="w-4 h-4 animate-spin" />}
                                {editing ? '保存修改' : '创建 SKU'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
