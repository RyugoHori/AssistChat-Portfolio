/**
 * Search results list with empty state
 */

'use client';

import { SearchResult } from '@/types';
import { ResultCard } from '@/components/shared/ResultCard';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { SearchX } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SearchResultsProps {
  results: SearchResult[];
  isLoading: boolean;
  onResultClick: (docId: string) => void;
  selectedDocId?: string;
  className?: string;
}

export function SearchResults({
  results,
  isLoading,
  onResultClick,
  selectedDocId,
  className,
}: SearchResultsProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner message="検索中..." />
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <SearchX className="h-12 w-12 text-slate-300 mb-4" />
        <h3 className="text-lg font-semibold text-slate-700 mb-2">
          検索結果が見つかりませんでした
        </h3>
        <p className="text-sm text-slate-500 max-w-md">
          別のキーワードで検索するか、フィルター条件を変更してください。
        </p>
      </div>
    );
  }

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-slate-600">
          {results.length}件の検索結果
        </p>
      </div>
      
      {results.map((result) => (
        <ResultCard
          key={result.doc_id}
          result={result}
          onClick={onResultClick}
          isSelected={result.doc_id === selectedDocId}
        />
      ))}
    </div>
  );
}