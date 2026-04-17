/**
 * ドキュメント詳細を取得するフック
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
import { DocumentDetail, ApiError, FeedbackRequest } from '@/types';
import { ragClient } from '@/lib/api/rag-client';

export function useDocumentDetail(docId: string | null) {
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDocument = useCallback(async () => {
    if (!docId) return;

    setIsLoading(true);
    setError(null);

    try {
      const doc = await ragClient.getDocument(docId);
      setDocument(doc);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.error || 'ドキュメントの取得に失敗しました');
      setDocument(null);
    } finally {
      setIsLoading(false);
    }
  }, [docId]);

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
      };

      await ragClient.submitFeedback(feedbackRequest);
    },
    [docId]
  );

  return {
    document,
    loading: isLoading,
    error,
    submitFeedback,
  };
}