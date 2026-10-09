'use client';

import { useState, useCallback } from 'react';
import { analyzeRoom } from '@/lib/api';
import type { AnalyzeResponse } from '@/lib/types';

export function useAnalyze() {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<AnalyzeResponse | null>(null);

    const analyze = useCallback(async (imageBase64: string) => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await analyzeRoom(imageBase64);
            setData(response);
            return response;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Analysis failed';
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

    return { analyze, isLoading, error, data, reset };
}
