/**
 * useSearch フックのユニットテスト
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';

import { useSearch } from '@/hooks/useSearch';
import { searchService } from '@/lib/api/search.service';

vi.mock('@/lib/api/search.service', () => ({
  searchService: {
    search: vi.fn(),
    getDocument: vi.fn(),
    getFilterMetadata: vi.fn(),
  },
}));

describe('useSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('初期状態は空', () => {
    const { result } = renderHook(() => useSearch());
    expect(result.current.query).toBe('');
    expect(result.current.results).toEqual([]);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('updateQuery でクエリが更新される', () => {
    const { result } = renderHook(() => useSearch());
    act(() => {
      result.current.updateQuery('モーター異音');
    });
    expect(result.current.query).toBe('モーター異音');
  });

  it('executeSearch で結果が取得される', async () => {
    (searchService.search as ReturnType<typeof vi.fn>).mockResolvedValue({
      results: [
        { doc_id: 'doc_1', title: 'テスト', score: 0.9 } as any,
      ],
      total: 1,
      processingTime: 100,
    });

    const { result } = renderHook(() => useSearch());
    act(() => {
      result.current.updateQuery('異音');
    });
    await act(async () => {
      await result.current.executeSearch();
    });

    await waitFor(() => {
      expect(result.current.results).toHaveLength(1);
    });
    expect(result.current.results[0].doc_id).toBe('doc_1');
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('executeSearch 失敗時に error が設定される', async () => {
    (searchService.search as ReturnType<typeof vi.fn>).mockRejectedValue({
      error: 'サーバエラー',
      statusCode: 500,
    });

    const { result } = renderHook(() => useSearch());
    act(() => {
      result.current.updateQuery('異音');
    });
    await act(async () => {
      await result.current.executeSearch();
    });

    await waitFor(() => {
      expect(result.current.error).toBe('サーバエラー');
    });
    expect(result.current.results).toEqual([]);
  });

  it('空クエリでは検索しない', async () => {
    const { result } = renderHook(() => useSearch());
    await act(async () => {
      await result.current.executeSearch();
    });
    expect(searchService.search).not.toHaveBeenCalled();
  });

  it('clearSearch で全状態がリセットされる', async () => {
    (searchService.search as ReturnType<typeof vi.fn>).mockResolvedValue({
      results: [{ doc_id: 'x', title: 'T', score: 0.5 } as any],
      total: 1,
      processingTime: 1,
    });
    const { result } = renderHook(() => useSearch());

    act(() => {
      result.current.updateQuery('x');
    });
    await act(async () => {
      await result.current.executeSearch();
    });
    await waitFor(() => expect(result.current.results).toHaveLength(1));

    act(() => {
      result.current.clearSearch();
    });

    expect(result.current.query).toBe('');
    expect(result.current.results).toEqual([]);
    expect(result.current.filters).toEqual({});
  });
});
