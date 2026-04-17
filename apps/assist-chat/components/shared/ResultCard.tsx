'use client';

import { MouseEvent } from 'react';
import { Calendar, MapPin, Sparkles, Wrench } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { getCategoryColor, getCategoryIcon } from '@/lib/utils/category';
import { formatDate } from '@/lib/utils/date';
import { SearchResult } from '@/types';

interface ResultCardProps {
  result: SearchResult;
  onClick: (docId: string) => void;
  isSelected?: boolean;
  className?: string;
  /**
   * 「AI に質問」ボタン押下時のコールバック
   *
   * 指定された場合のみボタンが表示される。呼び出し側は検索結果を
   * AI モードに受け渡して会話のシードとして利用する。
   */
  onAskAi?: (result: SearchResult) => void;
}

export function ResultCard({
  result,
  onClick,
  isSelected = false,
  className,
  onAskAi,
}: ResultCardProps) {
  const categoryColor = getCategoryColor(result.category);

  // confidence (0-100) を使用。古いキャッシュ等で未定義なら score から計算
  const displayScore =
    typeof result.confidence === 'number'
      ? result.confidence
      : typeof result.score === 'number'
        ? Math.round(result.score * 100)
        : 0;

  const handleAskAi = (e: MouseEvent) => {
    e.stopPropagation();
    onAskAi?.(result);
  };

  return (
    <Card
      className={cn(
        'p-4 cursor-pointer transition-all hover:shadow-md',
        isSelected && 'ring-2 ring-blue-500 shadow-md',
        className,
      )}
      onClick={() => onClick(result.doc_id)}
    >
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-semibold text-slate-900 leading-tight flex-1">
            {result.title}
          </h3>
          <Badge className="text-xs bg-blue-50 text-blue-700 border-blue-200 flex-shrink-0">
            スコア: {displayScore}%
          </Badge>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
          {result.date && (
            <div className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              <span>{formatDate(result.date)}</span>
            </div>
          )}
          {result.line && (
            <div className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              <span>{result.line}</span>
            </div>
          )}
          {result.machine && (
            <div className="flex items-center gap-1">
              <Wrench className="h-3 w-3" />
              <span>{result.machine}</span>
            </div>
          )}
        </div>

        <p className="text-sm text-slate-700 line-clamp-2">{result.snippet}</p>

        <div className="flex items-center justify-between gap-2">
          {result.category ? (
            <Badge variant="secondary" className={cn('text-xs', categoryColor)}>
              {getCategoryIcon(result.category)} {result.category}
            </Badge>
          ) : (
            <span />
          )}

          {onAskAi && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleAskAi}
              aria-label="AI に質問"
              className={cn(
                'h-7 px-2 text-[11px] text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50',
                'border border-transparent hover:border-indigo-200',
              )}
            >
              <Sparkles className="h-3 w-3 mr-1" />
              AI に質問
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
