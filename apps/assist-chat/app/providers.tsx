'use client';

import { ReactNode } from 'react';
import { SearchProvider } from '@/contexts/SearchContext';

// クライアント側のコンテキストプロバイダーをまとめるコンポーネント
export function Providers({ children }: { children: ReactNode }) {
  return <SearchProvider>{children}</SearchProvider>;
}
