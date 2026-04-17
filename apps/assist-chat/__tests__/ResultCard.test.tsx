/**
 * ResultCard のコンポーネントテスト
 *
 * - 基本レンダリング
 * - クリック時のハンドラ呼び出し
 * - AI モード導線ボタンの動作
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { ResultCard } from '@/components/shared/ResultCard';
import type { SearchResult } from '@/types';

const makeResult = (overrides: Partial<SearchResult> = {}): SearchResult => ({
  doc_id: 'doc_1',
  title: 'モーター異音',
  summary: 'ベアリング摩耗の事例',
  score: 0.85,
  confidence: 85,
  snippet: '主軸回転時に異音発生、ベアリング交換で復旧',
  date: '2024-01-05',
  machine: 'NC旋盤 #1',
  line: 'B1000',
  category: '機械',
  match_fields: {},
  ...overrides,
});

describe('ResultCard', () => {
  it('タイトル・スニペット・スコアが表示される', () => {
    render(<ResultCard result={makeResult()} onClick={() => {}} />);

    expect(screen.getByText('モーター異音')).toBeInTheDocument();
    expect(screen.getByText(/ベアリング交換で復旧/)).toBeInTheDocument();
    expect(screen.getByText(/85%/)).toBeInTheDocument();
  });

  it('カード本体クリックで onClick が呼ばれる', () => {
    const onClick = vi.fn();
    render(<ResultCard result={makeResult()} onClick={onClick} />);

    fireEvent.click(screen.getByText('モーター異音'));
    expect(onClick).toHaveBeenCalledWith('doc_1');
  });

  it('isSelected の時に選択スタイルが当たる', () => {
    const { container } = render(
      <ResultCard result={makeResult()} onClick={() => {}} isSelected />,
    );
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain('ring-2');
  });

  it('AI モード導線ボタンが表示されて、クリックで onAskAi が呼ばれる', () => {
    const onAskAi = vi.fn();
    render(
      <ResultCard
        result={makeResult()}
        onClick={() => {}}
        onAskAi={onAskAi}
      />,
    );

    const askButton = screen.getByRole('button', { name: /AI に質問/ });
    expect(askButton).toBeInTheDocument();

    fireEvent.click(askButton);
    expect(onAskAi).toHaveBeenCalledWith(
      expect.objectContaining({ doc_id: 'doc_1' }),
    );
  });

  it('AI モード導線ボタンは onAskAi が未指定なら非表示', () => {
    render(<ResultCard result={makeResult()} onClick={() => {}} />);
    expect(
      screen.queryByRole('button', { name: /AI に質問/ }),
    ).not.toBeInTheDocument();
  });
});
