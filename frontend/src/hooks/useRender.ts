'use client';

import { useState, useCallback } from 'react';
import { renderLayout } from '@/lib/api';
import type { RenderRequest, RenderResponse } from '@/lib/types';

export function useRender() {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<RenderResponse | null>(null);

    const render = useCallback(async (request: RenderRequest) => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await renderLayout(request);
            setData(response);
            return response;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Rendering failed';
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

    return { render, isLoading, error, data, reset };
}
