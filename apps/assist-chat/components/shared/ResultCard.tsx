// 検索結果カード

'use client';

import { SearchResult } from '@/types';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Calendar, MapPin, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getCategoryColor, getCategoryIcon } from '@/lib/utils/category';
import { formatDate } from '@/lib/utils/date';


interface ResultCardProps {
  result: SearchResult;
  onClick: (docId: string) => void;
  isSelected?: boolean;
  className?: string;
}

export function ResultCard({
  result,
  onClick,
  isSelected = false,
  className,
}: ResultCardProps) {
  const categoryColor = getCategoryColor(result.category);

  // confidence (0-100) を使用。もし古いキャッシュ等で未定義ならscoreから計算
  const displayScore = typeof result.confidence === 'number' 
    ? result.confidence 
    : (typeof result.score === 'number' ? Math.round(result.score * 100) : 0);

  return (
    <Card
      className={cn(
        'p-4 cursor-pointer transition-all hover:shadow-md',
        isSelected && 'ring-2 ring-blue-500 shadow-md',
        className
      )}
      onClick={() => onClick(result.doc_id)}
    >
      <div className="space-y-3">
        {/* ヘッダー */}
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-semibold text-slate-900 leading-tight flex-1">
            {result.title}
          </h3>
          {/* スコア表示 */}
          <Badge className="text-xs bg-blue-50 text-blue-700 border-blue-200">
            スコア: {displayScore}%
          </Badge>
        </div>

        {/* メタデータ */}
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

        {/* スニペット */}
        <p className="text-sm text-slate-700 line-clamp-2">
          {result.snippet}
        </p>

        {/* フッター */}
        <div className="flex items-center justify-between">
          {result.category && (
            <Badge variant="secondary" className={cn('text-xs', categoryColor)}>
              {getCategoryIcon(result.category)} {result.category}
            </Badge>
          )}
        </div>
      </div>
    </Card>
  );
}
