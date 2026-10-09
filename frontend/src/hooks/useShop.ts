'use client';

import { useState, useCallback } from 'react';
import type { ShopRequest, ShopResponse } from '@/lib/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useShop() {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<ShopResponse | null>(null);

    const findProducts = useCallback(async (request: ShopRequest): Promise<ShopResponse> => {
        setIsLoading(true);
        setError(null);

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 min timeout

        try {
            const response = await fetch(`${API_URL}/api/v1/shop`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(request),
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Request failed' }));
                throw new Error(errorData.detail || `HTTP error ${response.status}`);
            }

            const result: ShopResponse = await response.json();
            setData(result);
            return result;
        } catch (err) {
            clearTimeout(timeoutId);
            let message = 'Product search failed';
            if (err instanceof Error) {
                message = err.name === 'AbortError' ? 'Request timed out.' : err.message;
            }
            setError(message);
            throw new Error(message);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const reset = useCallback(() => {
        setData(null);
        setError(null);
    }, []);

    return { findProducts, isLoading, error, data, reset };
}