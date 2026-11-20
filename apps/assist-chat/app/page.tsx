'use client';

import { useState, useEffect } from 'react';
import { FilterMetadata } from '@/types';
import { SearchInterface } from '@/components/features/search/SearchInterface';
import { FilterPanel } from '@/components/features/filters/FilterPanel';
import { DetailPanel } from '@/components/features/detail/DetailPanel';
import { Button } from '@/components/ui/button';
import { useSearchContext } from '@/contexts/SearchContext';
import { ragClient } from '@/lib/api/rag-client';
import { ErrorBoundary } from '@/components/shared/ErrorBoundary';
import { APP_NAME } from '@/lib/constants';
import { Filter } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';

export default function HomePage() {
  const [filterMetadata, setFilterMetadata] = useState<FilterMetadata | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [showDetailPanel, setShowDetailPanel] = useState(false);
  const [showFilterSheet, setShowFilterSheet] = useState(false);
  // 詳細を開いた時点の検索IDと順位。開いたまま検索をやり直したときに、
  // クリックしていない新しい検索の閲覧として記録しないよう、最新の検索の値ではなくこれを渡す
  const [openedFrom, setOpenedFrom] = useState<{ searchId: string | null; rank?: number }>({
    searchId: null,
  });

  const { results, searchId, query, filters, updateFilters, clearSearch } = useSearchContext();

  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const metadata = await ragClient.getFilterMetadata();
        setFilterMetadata(metadata);
      } catch (error) {
        console.error('フィルターメタデータの取得に失敗しました:', error);
      }
    };
    fetchMetadata();
  }, []);

  const handleResultClick = (docId: string) => {
    const index = results.findIndex((r) => r.doc_id === docId);
    setOpenedFrom(
      index >= 0 ? { searchId, rank: index + 1 } : { searchId: null, rank: undefined },
    );
    setSelectedDocId(docId);
    setShowDetailPanel(true);
  };

  const selectedResult = results.find((r) => r.doc_id === selectedDocId);

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-slate-50">
        <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
          <div className="container mx-auto px-4 py-3 sm:py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-xl sm:text-2xl font-bold text-slate-900">{APP_NAME}</h1>
                <p className="text-xs sm:text-sm text-slate-600">
                  故障対応検索システム - 過去の事例から似た対処を探す
                </p>
              </div>
            </div>
          </div>
        </header>

        <main className="container mx-auto px-4 py-6">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* デスクトップ：サイドバーに表示 */}
            <aside className="hidden lg:block lg:col-span-1">
              {filterMetadata && (
                <FilterPanel
                  filters={filters}
                  onChange={updateFilters}
                  metadata={filterMetadata}
                  onReset={clearSearch}
                />
              )}
            </aside>

            {/* メインコンテンツ */}
            <div className="lg:col-span-3">
              {/* モバイル：フィルターボタン */}
              <div className="lg:hidden mb-4">
                <Sheet open={showFilterSheet} onOpenChange={setShowFilterSheet}>
                  <SheetTrigger asChild>
                    <Button variant="outline" className="w-full">
                      <Filter className="h-4 w-4 mr-2" />
                      フィルター
                    </Button>
                  </SheetTrigger>
                  <SheetContent side="left" className="w-[300px] sm:w-[400px] overflow-y-auto">
                    <SheetHeader>
                      <SheetTitle>フィルター</SheetTitle>
                      <SheetDescription>
                        検索条件を絞り込んでください
                      </SheetDescription>
                    </SheetHeader>
                    <div className="mt-4">
                      {filterMetadata && (
                        <FilterPanel
                          filters={filters}
                          onChange={updateFilters}
                          metadata={filterMetadata}
                          onReset={clearSearch}
                        />
                      )}
                    </div>
                  </SheetContent>
                </Sheet>
              </div>

              <SearchInterface
                onResultClick={handleResultClick}
                selectedDocId={selectedDocId || undefined}
              />
            </div>
          </div>
        </main>

        {showDetailPanel && selectedResult && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-2 sm:p-4">
            <div className="w-full max-w-3xl h-[90vh] sm:h-[80vh]">
              <DetailPanel
                result={selectedResult}
                searchId={openedFrom.searchId}
                rank={openedFrom.rank}
                query={query}
                onClose={() => {
                  setShowDetailPanel(false);
                  setSelectedDocId(null);
                }}
              />
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}
