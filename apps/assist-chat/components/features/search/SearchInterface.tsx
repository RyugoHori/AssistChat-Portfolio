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
      <SearchInput
        value={query}
        onChange={updateQuery}
        onSearch={executeSearch} // executeSearchを入力コンポーネントに渡す
        isLoading={loading}
      />

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
