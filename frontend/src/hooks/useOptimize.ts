'use client';

import { useState, useCallback } from 'react';
import type { OptimizeRequest, OptimizeResponse } from '@/lib/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useOptimize() {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<OptimizeResponse | null>(null);

    const optimize = useCallback(async (request: OptimizeRequest): Promise<OptimizeResponse> => {
        setIsLoading(true);
        setError(null);

        // Create AbortController for timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minute timeout

        try {
            const response = await fetch(`${API_URL}/api/v1/optimize`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(request),
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Request failed' }));
                throw new Error(errorData.detail || `HTTP error ${response.status}`);
            }

            const result: OptimizeResponse = await response.json();
            setData(result);
            return result;
        } catch (err) {
            clearTimeout(timeoutId);

            let message = 'Optimization failed';
            if (err instanceof Error) {
                if (err.name === 'AbortError') {
                    message = 'Request timed out. Please try again.';
                } else {
                    message = err.message;
                }
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

    return { optimize, isLoading, error, data, reset };
}