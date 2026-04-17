'use client';

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  ReactNode,
} from 'react';

import { useSearch } from '@/hooks/useSearch';
import type { SearchResult } from '@/types';

/**
 * 検索モード → AI モードへのバトン
 *
 * 検索結果カードの「AI に質問」から AI モードに遷移したときに、
 * 選択されたドキュメントを文脈として自動で最初の質問を組み立てる。
 */
export interface PendingAskAi {
  /** AI モードで最初に送信する質問文 */
  prompt: string;
  /** 起点となった検索結果（AI モード UI で視覚的に確認できるよう渡す） */
  seed: SearchResult;
}

type SearchContextValue = ReturnType<typeof useSearch> & {
  /** AI モードで自動送信する保留中の質問（単発） */
  pendingAskAi: PendingAskAi | null;
  /** 「AI に質問」ボタン押下時に呼ばれる */
  queueAskAi: (seed: SearchResult) => void;
  /** AI モード側が受け取って消費する */
  consumePendingAskAi: () => PendingAskAi | null;
  /** AI モードに切り替える要求 */
  setActiveModeRequest: (mode: 'search' | 'chat') => void;
  /** 現在要求されているアクティブモード（タブの制御に使う） */
  activeModeRequest: 'search' | 'chat' | null;
  /** モード切り替え要求を消費する */
  consumeActiveModeRequest: () => 'search' | 'chat' | null;
};

const SearchContext = createContext<SearchContextValue | undefined>(undefined);

export function useSearchContext(): SearchContextValue {
  const context = useContext(SearchContext);
  if (!context) {
    throw new Error('useSearchContextはSearchProvider内で使用する必要があります');
  }
  return context;
}

/**
 * 検索結果から初回の質問文を組み立てる
 *
 * LLM が文脈を理解しやすいように、事例のメタデータ（設備・症状）を
 * 明示したクエリを生成する。
 */
function buildAskAiPrompt(result: SearchResult): string {
  const parts: string[] = [];
  if (result.machine) parts.push(`設備「${result.machine}」`);
  if (result.symptom) parts.push(`症状「${result.symptom}」`);
  if (result.line) parts.push(`ライン「${result.line}」`);

  const lead = parts.length
    ? `検索結果の事例（${parts.join(' / ')}）`
    : `検索結果の事例「${result.title}」`;

  return (
    `${lead}について、原因の切り分けと具体的な対処手順を、` +
    `過去の類似事例も踏まえて詳しく教えてください。`
  );
}

export function SearchProvider({ children }: { children: ReactNode }) {
  const searchState = useSearch();
  const [pendingAskAi, setPendingAskAi] = useState<PendingAskAi | null>(null);
  const [activeModeRequest, setActiveModeRequest] = useState<'search' | 'chat' | null>(
    null,
  );

  const queueAskAi = useCallback((seed: SearchResult) => {
    setPendingAskAi({ prompt: buildAskAiPrompt(seed), seed });
    setActiveModeRequest('chat');
  }, []);

  const consumePendingAskAi = useCallback((): PendingAskAi | null => {
    let captured: PendingAskAi | null = null;
    setPendingAskAi((prev) => {
      captured = prev;
      return null;
    });
    return captured;
  }, []);

  const consumeActiveModeRequest = useCallback((): 'search' | 'chat' | null => {
    let captured: 'search' | 'chat' | null = null;
    setActiveModeRequest((prev) => {
      captured = prev;
      return null;
    });
    return captured;
  }, []);

  const value = useMemo<SearchContextValue>(
    () => ({
      ...searchState,
      pendingAskAi,
      queueAskAi,
      consumePendingAskAi,
      activeModeRequest,
      setActiveModeRequest,
      consumeActiveModeRequest,
    }),
    [
      searchState,
      pendingAskAi,
      queueAskAi,
      consumePendingAskAi,
      activeModeRequest,
      consumeActiveModeRequest,
    ],
  );

  return <SearchContext.Provider value={value}>{children}</SearchContext.Provider>;
}
