'use client';

import { createContext, useContext, ReactNode } from 'react';
import { useSearch } from '@/hooks/useSearch';

// 1. コンテキストを作成
const SearchContext = createContext<ReturnType<typeof useSearch> | undefined>(
  undefined
);

// 2. 使いやすいようにカスタムフックを作成
export function useSearchContext() {
  const context = useContext(SearchContext);
  if (!context) {
    throw new Error('useSearchContextはSearchProvider内で使用する必要があります');
  }
  return context;
}

// 3. Providerコンポーネントを作成
export function SearchProvider({ children }: { children: ReactNode }) {
  const searchState = useSearch();

  return (
    <SearchContext.Provider value={searchState}>
      {children}
    </SearchContext.Provider>
  );
}
