/**
 * API Client for Pocket Planner Backend
 * 
 * FIXES APPLIED:
 * 1. analyzeRoom now uses longApi (120s timeout) instead of api (60s)
 *    - Gemini vision cold-start on first call can exceed 60s
 * 2. Kept standard api client for truly fast endpoints (health, render)
 */

import axios, { AxiosError } from 'axios';
import type {
    AnalyzeRequest,
    AnalyzeResponse,
    OptimizeRequest,
    OptimizeResponse,
    RenderRequest,
    RenderResponse,
    PerspectiveRequest,
    PerspectiveResponse,
    ChatEditRequest,
    ChatEditResponse,
    ShopRequest,
    ShopResponse,
    AdminSkuItem,
    AdminSkuListResponse,
    AdminSkuPayload,
    AdminPriceStockPayload,
    AdminImportResponse,
    AdminCategoryCount,
    QuoteResponse,
    LeadItem,
    LeadListResponse,
    LeadCreatePayload,
    LeadStatus,
} from './types';

// 本地开发默认连后端 8001（可用 NEXT_PUBLIC_API_URL 覆盖）
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

// Standard API client - for fast endpoints (health, simple render)
const api = axios.create({
    baseURL: `${API_URL}/api/v1`,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 60000, // 60 second default timeout
});

// Long-running operations client (for analyze, optimize, perspective, chat)
const longApi = axios.create({
    baseURL: `${API_URL}/api/v1`,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 180000, // 3 minute timeout for AI operations
});

// Error handler
function handleApiError(error: unknown): never {
    if (error instanceof AxiosError) {
        if (error.code === 'ECONNABORTED') {
            throw new Error('Request timed out. The server is taking too long to respond.');
        }
        const message = error.response?.data?.detail || error.message;
        throw new Error(message);
    }
    throw error;
}

/**
 * Analyze a room image and extract furniture objects
 * Uses longApi - Gemini vision can be slow on first call (cold start)
 */
export async function analyzeRoom(imageBase64: string): Promise<AnalyzeResponse> {
    try {
        const response = await longApi.post<AnalyzeResponse>('/analyze', {
            image_base64: imageBase64,
        } satisfies AnalyzeRequest);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

/**
 * Optimize room layout while respecting locked objects
 * Uses longer timeout due to multiple AI operations
 */
export async function optimizeLayout(request: OptimizeRequest): Promise<OptimizeResponse> {
    try {
        const response = await longApi.post<OptimizeResponse>('/optimize', request);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

/**
 * Render the optimized layout as an edited image
 */
export async function renderLayout(request: RenderRequest): Promise<RenderResponse> {
    try {
        const response = await api.post<RenderResponse>('/render', request);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

/**
 * Generate a photorealistic perspective view of the layout
 * Uses longer timeout due to image generation
 */
export async function generatePerspective(request: PerspectiveRequest): Promise<PerspectiveResponse> {
    try {
        const response = await longApi.post<PerspectiveResponse>('/render/perspective', request);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

/**
 * Process a chat edit command
 */
export async function chatEdit(request: ChatEditRequest): Promise<ChatEditResponse> {
    try {
        const response = await longApi.post<ChatEditResponse>('/chat/edit', request);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

/**
 * Find products matching room furniture
 */
export async function shopProducts(request: ShopRequest): Promise<ShopResponse> {
    try {
        const response = await longApi.post<ShopResponse>('/shop', request);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

/**
 * Check backend health
 */
export async function checkHealth(): Promise<{ status: string; version: string }> {
    try {
        const response = await axios.get(`${API_URL}/health`, { timeout: 5000 });
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

// === P1：SKU 管理后台 API ===

export async function adminListSkus(params: {
    page?: number;
    page_size?: number;
    keyword?: string;
    category?: string;
    in_stock?: boolean;
}): Promise<AdminSkuListResponse> {
    try {
        const response = await api.get<AdminSkuListResponse>('/sku/admin/products', { params });
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

export async function adminCategories(): Promise<AdminCategoryCount[]> {
    try {
        const response = await api.get<AdminCategoryCount[]>('/sku/admin/categories');
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

export async function adminCreateSku(payload: AdminSkuPayload): Promise<AdminSkuItem> {
    try {
        const response = await api.post<AdminSkuItem>('/sku/admin/products', payload);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

export async function adminUpdateSku(id: string, payload: AdminSkuPayload): Promise<AdminSkuItem> {
    try {
        const response = await api.put<AdminSkuItem>(`/sku/admin/products/${encodeURIComponent(id)}`, payload);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

export async function adminQuickUpdate(id: string, payload: AdminPriceStockPayload): Promise<AdminSkuItem> {
    try {
        const response = await api.patch<AdminSkuItem>(`/sku/admin/products/${encodeURIComponent(id)}/price-stock`, payload);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

export async function adminDeleteSku(id: string): Promise<void> {
    try {
        await api.delete(`/sku/admin/products/${encodeURIComponent(id)}`);
    } catch (error) {
        handleApiError(error);
    }
}

export async function adminImportSkus(file: File): Promise<AdminImportResponse> {
    try {
        const formData = new FormData();
        formData.append('file', file);
        const response = await api.post<AdminImportResponse>('/sku/admin/products/import-csv', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 120000,
        });
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

// === P2：报价单 API ===

/** 基于方案生成报价单（幂等：已存在返回既有报价单） */
export async function createQuote(planId: string): Promise<QuoteResponse> {
    try {
        const response = await api.post<QuoteResponse>(`/quote/${encodeURIComponent(planId)}`);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

/** 查询某方案最新报价单（未生成时 404） */
export async function getQuoteByPlan(planId: string): Promise<QuoteResponse> {
    try {
        const response = await api.get<QuoteResponse>(`/quote/by-plan/${encodeURIComponent(planId)}`);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

/** 打开打印版 HTML（浏览器直接可打印） */
export function openQuoteHtml(quoteId: string): void {
    window.open(`${API_URL}/api/v1/quote/${encodeURIComponent(quoteId)}/html`, '_blank');
}

// === P2：导购跟进线索 API ===

export async function leadList(params: {
    page?: number;
    page_size?: number;
    keyword?: string;
    status?: string;
}): Promise<LeadListResponse> {
    try {
        const response = await api.get<LeadListResponse>('/leads', { params });
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

export async function leadCreate(payload: LeadCreatePayload): Promise<LeadItem> {
    try {
        const response = await api.post<LeadItem>('/leads', payload);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

export async function leadUpdate(id: string, payload: Partial<Omit<LeadCreatePayload, 'status'>>): Promise<LeadItem> {
    try {
        const response = await api.put<LeadItem>(`/leads/${encodeURIComponent(id)}`, payload);
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

export async function leadChangeStatus(id: string, status: LeadStatus): Promise<LeadItem> {
    try {
        const response = await api.patch<LeadItem>(`/leads/${encodeURIComponent(id)}/status`, { status });
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

export async function leadAddRecord(id: string, content: string): Promise<LeadItem> {
    try {
        const response = await api.post<LeadItem>(`/leads/${encodeURIComponent(id)}/records`, { content });
        return response.data;
    } catch (error) {
        handleApiError(error);
    }
}

export async function leadDelete(id: string): Promise<void> {
    try {
        await api.delete(`/leads/${encodeURIComponent(id)}`);
    } catch (error) {
        handleApiError(error);
    }
}