'use client';

import { useState, useMemo, useCallback } from 'react';
import { SearchResult, SearchFilters, ApiError } from '@/types';
import { searchService } from '@/lib/api/search.service';
import { SEARCH_CONFIG } from '@/lib/constants';

export function useSearch() {
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<SearchFilters>({});
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const executeSearch = useCallback(async () => {
    if (query.trim().length < SEARCH_CONFIG.MIN_QUERY_LENGTH) {
      setResults([]);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await searchService.search({
        query: query.trim(),
        filters,
        k: SEARCH_CONFIG.DEFAULT_RESULTS_LIMIT,
      });
      setResults(response.results || []);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.error || '検索に失敗しました');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [query, filters]);

  const updateQuery = (newQuery: string) => {
    setQuery(newQuery);
  };

  const updateFilters = (newFilters: SearchFilters) => {
    setFilters(newFilters);
  };

  const clearSearch = () => {
    setQuery('');
    setFilters({});
    setResults([]);
    setError(null);
  };

  const returnValue = useMemo(
    () => ({
      query,
      results,
      loading,
      error,
      filters,
      updateQuery,
      updateFilters,
      clearSearch,
      executeSearch, // 手動検索関数を公開
    }),
    [query, results, loading, error, filters, executeSearch] // executeSearchを依存配列に追加
  );

  return returnValue;
}
