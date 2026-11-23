'use client';

import { DocumentDetail, SearchResult } from '@/types';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { DocumentHeader } from './DocumentHeader';
import { useDocumentDetail } from '@/hooks/useDocumentDetail';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';

interface DetailPanelProps {
  result: SearchResult;
  onClose: () => void;
  /** 開いた結果を返した検索のID（利用ログ用） */
  searchId?: string | null;
  /** その検索での表示順位（1始まり、利用ログ用） */
  rank?: number;
  /** 検索クエリ（フィードバックに付ける） */
  query?: string;
}

export function DetailPanel({ result, onClose, searchId, rank, query }: DetailPanelProps) {
  const { document: documentDetail, loading, error, submitFeedback } = useDocumentDetail(
    result.doc_id,
    { searchId, rank, query },
  );

  const handleFeedback = async (helpful: boolean) => {
    try {
      await submitFeedback(helpful, helpful ? 5 : 2);
      toast.success('フィードバックありがとうございます', {
        description: '貴重なご意見をありがとうございます。',
      });
    } catch (error) {
      toast.error('エラー', {
        description: 'フィードバックの送信に失敗しました',
      });
    }
  };

  if (loading) {
    return (
      <Card className="h-full p-6">
        <div className="flex justify-center items-center h-full">
          <LoadingSpinner />
        </div>
      </Card>
    );
  }

  if (!documentDetail) {
    return (
      <Card className="h-full p-6">
        <div className="flex flex-col justify-center items-center h-full">
          <p className="text-slate-500 mb-2">詳細情報を読み込めませんでした</p>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      </Card>
    );
  }

  return (
    <Card className="h-full flex flex-col bg-white shadow-xl border-0">
      <DocumentHeader document={documentDetail} onClose={onClose} />

      {/* コンテンツ */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 sm:space-y-6">
        
        {/* 検索スコア表示 */}
        <div className="space-y-2">
          <h3 className="text-sm sm:text-base font-semibold text-slate-800">検索スコア</h3>
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3 p-3 bg-slate-50 rounded-lg border">
            <Badge className="text-base sm:text-lg px-3 sm:px-4 py-1 bg-blue-100 text-blue-800 border-blue-200">
              {result.confidence}%
            </Badge>
            <div className='flex-1'>
              <p className='text-xs text-slate-600'>
                検索クエリとこの文書の類似度スコアです。
              </p>
            </div>
          </div>
        </div>

        {/* メインコンテンツ */}
        <div>
          <h3 className="text-sm sm:text-base font-semibold text-slate-800 mb-3">詳細内容</h3>
          <div className="prose prose-sm max-w-none">
            <div className="whitespace-pre-wrap text-sm sm:text-base text-slate-700 leading-relaxed break-words">
              {documentDetail.full_text}
            </div>
          </div>
        </div>

        {/* 実施した対処 */}
        {documentDetail.action_taken && (
          <div>
            <h3 className="font-semibold text-slate-800 mb-3">実施した対処</h3>
            <div className="bg-green-50 p-4 rounded-lg border border-green-200">
              <p className="text-green-800">{documentDetail.action_taken}</p>
            </div>
          </div>
        )}

      </div>

      {/* フッターアクション */}
      <div className="p-4 sm:p-6 border-t border-slate-200">
        <div className="flex flex-col sm:flex-row gap-2 sm:justify-between">
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleFeedback(true)}
              className="text-green-600 hover:bg-green-50 flex-1"
            >
              <ThumbsUp className="h-4 w-4 mr-1" />
              役立った
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleFeedback(false)}
              className="text-red-600 hover:bg-red-50 flex-1"
            >
              <ThumbsDown className="h-4 w-4 mr-1" />
              役立たない
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
