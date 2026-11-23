import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('@/lib/api/rag-client', () => ({
  ragClient: {
    getFilterMetadata: vi.fn().mockResolvedValue({
      categories: [],
      productionLines: [],
      workTypes: [],
      equipment1s: [],
      equipment2s: [],
      equipment3s: [],
      yearRange: { startYear: 2021, endYear: 2025 },
      totalDocuments: 1,
      hierarchy: [],
    }),
    search: vi.fn().mockResolvedValue({
      results: [
        {
          doc_id: 'doc_000123',
          title: 'コンベアが止まる',
          score: 0.9,
          confidence: 90,
          snippet: '【現象】 コンベアが止まる。',
          date: '2024-01-05',
          machine: 'ベルトコンベア #1',
          line: 'A1000 生産ラインA',
          category: '機械',
          symptom: 'コンベアが止まる。',
        },
      ],
      total: 1,
      processingTime: 10,
      searchId: 'search_1',
    }),
    getDocument: vi.fn(),
    submitFeedback: vi.fn(),
    streamChat: vi.fn(async function* () {
      yield { type: 'stage', stage: 'searching' };
      yield { type: 'token', content: '回答です' };
      yield { type: 'done', confidence: 'high', processingTime: 10 };
    }),
  },
}));

// jsdom には scrollTo がない（AI モードの自動スクロールで使う）
Element.prototype.scrollTo = () => {};

import HomePage from '@/app/page';
import { SearchProvider } from '@/contexts/SearchContext';
import { ragClient } from '@/lib/api/rag-client';

it('「AI に質問」で AI モードに切り替わり、質問が 1 回だけ送られる', async () => {
  // 開発時と同じく StrictMode で描画する（effect が 2 回動いても質問は 1 回だけ）
  render(
    <StrictMode>
      <SearchProvider>
        <HomePage />
      </SearchProvider>
    </StrictMode>,
  );

  fireEvent.change(screen.getByPlaceholderText('故障内容や設備名で検索...'), {
    target: { value: 'コンベア' },
  });
  fireEvent.click(screen.getByRole('button', { name: '検索' }));
  const askAi = await screen.findByRole('button', { name: 'AI に質問' });

  await act(async () => {
    fireEvent.click(askAi);
  });

  await waitFor(() =>
    expect(screen.getByRole('tab', { name: /AI モード/ }).getAttribute('data-state')).toBe('active'),
  );
  await waitFor(() => expect(ragClient.streamChat).toHaveBeenCalledTimes(1));
  expect(vi.mocked(ragClient.streamChat).mock.calls[0][0].query).toContain('ベルトコンベア #1');
});
