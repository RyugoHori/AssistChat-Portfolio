'use client';

import { useEffect, useState } from 'react';
import { MessageSquare, Search as SearchIcon } from 'lucide-react';

import { ChatMode } from '@/components/features/chat/ChatMode';
import { Card } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useSearchContext } from '@/contexts/SearchContext';
import { SearchInput } from './SearchInput';
import { SearchResults } from './SearchResults';

interface SearchInterfaceProps {
  onResultClick: (docId: string) => void;
  selectedDocId?: string;
}

/**
 * 検索と AI 対話モードを切り替えるラッパー
 *
 * - 検索モード: 従来のハイブリッド検索（上部の検索バーを使用）
 * - AI モード:  会話型 RAG（自前の入力 UI を持ち、検索バーは使わない）
 * - 検索結果カードの「AI に質問」が押されたとき、AI モードに自動遷移して
 *   該当事例を起点にした質問を自動送信する（SearchContext 経由でバトンを渡す）
 */
export function SearchInterface({
  onResultClick,
  selectedDocId,
}: SearchInterfaceProps) {
  const {
    query,
    updateQuery,
    results,
    loading,
    error,
    executeSearch,
    queueAskAi,
    activeModeRequest,
    consumeActiveModeRequest,
  } = useSearchContext();
  const [activeTab, setActiveTab] = useState<'search' | 'chat'>('search');

  // 検索結果から「AI に質問」された時、コンテキスト経由で chat タブに切り替える
  useEffect(() => {
    if (!activeModeRequest) return;
    const requested = consumeActiveModeRequest();
    if (requested) {
      setActiveTab(requested);
    }
  }, [activeModeRequest, consumeActiveModeRequest]);

  const handleShowSearchResults = () => setActiveTab('search');

  return (
    <div className="space-y-4">
      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as 'search' | 'chat')}
      >
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="search" className="gap-1.5">
            <SearchIcon className="h-4 w-4" />
            検索モード
          </TabsTrigger>
          <TabsTrigger value="chat" className="gap-1.5">
            <MessageSquare className="h-4 w-4" />
            AI モード
          </TabsTrigger>
        </TabsList>

        <TabsContent value="search" className="mt-4 space-y-4">
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
            onAskAi={queueAskAi}
            selectedDocId={selectedDocId}
          />
        </TabsContent>

        <TabsContent value="chat" className="mt-4">
          <ChatMode
            onShowSearchResults={handleShowSearchResults}
            onResultClick={onResultClick}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
