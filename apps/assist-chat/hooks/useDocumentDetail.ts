/**
 * ドキュメント詳細を取得するフック
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
import { DocumentDetail, ApiError, FeedbackRequest } from '@/types';
import { ragClient } from '@/lib/api/rag-client';

/**
 * @param context - 検索結果から開いたときの検索ID・順位・クエリ。閲覧ログとフィードバックに付けて、
 *                  どの検索の何位の結果かを結び付ける
 */
export function useDocumentDetail(
  docId: string | null,
  context?: { searchId?: string | null; rank?: number; query?: string },
) {
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 依存配列にはオブジェクトではなく値を入れる（呼び出し側が毎回新しいオブジェクトを渡すと、再取得が繰り返されるため）
  const searchId = context?.searchId ?? null;
  const rank = context?.rank;
  const query = context?.query;

  const fetchDocument = useCallback(async () => {
    if (!docId) return;

    setIsLoading(true);
    setError(null);

    try {
      const doc = await ragClient.getDocument(docId, { searchId, rank });
      setDocument(doc);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.error || 'ドキュメントの取得に失敗しました');
      setDocument(null);
    } finally {
      setIsLoading(false);
    }
  }, [docId, searchId, rank]);

  useEffect(() => {
    fetchDocument();
  }, [fetchDocument]);

  const submitFeedback = useCallback(
    async (helpful: boolean, rating: number, comment?: string) => {
      if (!docId) throw new Error('ドキュメントIDが利用できません');

      const feedbackRequest: FeedbackRequest = {
        doc_id: docId,
        helpful,
        rating,
        comment,
        search_id: searchId ?? undefined,
        rank,
        query,
        mode: 'search',
      };

      await ragClient.submitFeedback(feedbackRequest);
    },
    [docId, searchId, rank, query]
  );

  return {
    document,
    loading: isLoading,
    error,
    submitFeedback,
  };
}
