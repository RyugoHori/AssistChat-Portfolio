'use client';

import { useState, useMemo, useCallback } from 'react';
import { SearchResult, SearchFilters, ApiError } from '@/types';
import { ragClient } from '@/lib/api/rag-client';
import { SEARCH_CONFIG } from '@/lib/constants';

export function useSearch() {
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<SearchFilters>({});
  const [results, setResults] = useState<SearchResult[]>([]);
  // いま表示している results を返した検索のID（利用ログで閲覧・フィードバックと結び付ける）
  const [searchId, setSearchId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const executeSearch = useCallback(async () => {
    if (query.trim().length < SEARCH_CONFIG.MIN_QUERY_LENGTH) {
      setResults([]);
      setSearchId(null);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await ragClient.search({
        query: query.trim(),
        filters,
        k: SEARCH_CONFIG.DEFAULT_RESULTS_LIMIT,
      });
      setResults(response.results || []);
      setSearchId(response.searchId ?? null);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.error || '検索に失敗しました');
      setResults([]);
      setSearchId(null);
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
    setSearchId(null);
    setError(null);
  };

  const returnValue = useMemo(
    () => ({
      query,
      results,
      searchId,
      loading,
      error,
      filters,
      updateQuery,
      updateFilters,
      clearSearch,
      executeSearch,
    }),
    [query, results, searchId, loading, error, filters, executeSearch]
  );

  return returnValue;
}
