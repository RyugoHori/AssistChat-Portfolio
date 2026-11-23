/**
 * SearchResults のコンポーネントテスト
 *
 * - まだ検索していないときは、0 件の表示ではなく案内を出す
 * - 検索して 0 件のときは「見つかりませんでした」を出す
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { SearchResults } from '@/components/features/search/SearchResults';

describe('SearchResults', () => {
  it('まだ検索していないときは案内を出す', () => {
    render(<SearchResults results={[]} isLoading={false} onResultClick={() => {}} hasSearched={false} />);

    expect(screen.getByText('症状やエラーコードを入れて検索してください')).toBeInTheDocument();
    expect(screen.queryByText('検索結果が見つかりませんでした')).not.toBeInTheDocument();
  });

  it('検索して 0 件のときは「見つかりませんでした」を出す', () => {
    render(<SearchResults results={[]} isLoading={false} onResultClick={() => {}} hasSearched />);

    expect(screen.getByText('検索結果が見つかりませんでした')).toBeInTheDocument();
  });
});
