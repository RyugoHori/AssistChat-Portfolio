'use client';

import { useSearchContext } from '@/contexts/SearchContext';
import { SearchInput } from './SearchInput';
import { SearchResults } from './SearchResults';
import { Card } from '@/components/ui/card';

interface SearchInterfaceProps {
  onResultClick: (docId: string) => void;
  selectedDocId?: string;
}

export function SearchInterface({
  onResultClick,
  selectedDocId,
}: SearchInterfaceProps) {
  // コンテキストから検索関連の状態と関数を取得
  const { query, updateQuery, results, loading, error, executeSearch } = useSearchContext();

  return (
    <div className="space-y-4">
      {/* 
        モバイル対応: stickyで検索窓を上部に固定
      */}
      <div className="sticky top-[72px] z-20 bg-slate-50 py-2 -mx-4 px-4 shadow-sm sm:static sm:top-auto sm:bg-transparent sm:py-0 sm:mx-0 sm:px-0 sm:shadow-none transition-all">
        <SearchInput
          value={query}
          onChange={updateQuery}
          onSearch={executeSearch}
          isLoading={loading}
        />
      </div>

      {error && (
        <Card className="p-4 bg-red-50 border-red-200">
          <p className="text-sm text-red-600">{error}</p>
        </Card>
      )}

      <SearchResults
        results={results}
        isLoading={loading}
        onResultClick={onResultClick}
        selectedDocId={selectedDocId}
      />
    </div>
  );
}
