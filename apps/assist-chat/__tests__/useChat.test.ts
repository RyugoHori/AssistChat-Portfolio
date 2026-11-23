/**
 * useChat フックのユニットテスト
 *
 * NDJSON ストリームのモックを差し込んで、メッセージ差分更新と
 * キャンセル動作を検証する。
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';

import { useChat } from '@/hooks/useChat';
import { ragClient } from '@/lib/api/rag-client';
import type { ChatStreamEvent } from '@/types';

vi.mock('@/lib/api/rag-client', () => ({
  ragClient: {
    streamChat: vi.fn(),
  },
}));

async function* makeStream(events: ChatStreamEvent[]): AsyncGenerator<ChatStreamEvent> {
  for (const e of events) {
    yield e;
  }
}

describe('useChat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sendMessage で user と assistant の 2 メッセージが順に追加される', async () => {
    (ragClient.streamChat as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      makeStream([
        { type: 'stage', stage: 'rewriting' },
        { type: 'stage', stage: 'searching' },
        {
          type: 'meta',
          rewritten_query: '異音',
          original_query: '異音',
          sources: [{ doc_id: 'doc_1', title: 'ベアリング事例', score: 0.9 }],
          result_count: 1,
        },
        { type: 'stage', stage: 'generating' },
        { type: 'token', content: '原因' },
        { type: 'token', content: 'は' },
        { type: 'token', content: 'ベアリング' },
        { type: 'done', confidence: 'high', processingTime: 1234 },
      ]),
    );

    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.sendMessage('異音');
    });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });

    const [user, assistant] = result.current.messages;
    expect(user.role).toBe('user');
    expect(user.content).toBe('異音');
    expect(user.status).toBe('complete');

    expect(assistant.role).toBe('assistant');
    expect(assistant.content).toBe('原因はベアリング');
    expect(assistant.status).toBe('complete');
    expect(assistant.confidence).toBe('high');
    expect(assistant.sources).toHaveLength(1);
    expect(assistant.sources?.[0].doc_id).toBe('doc_1');
  });

  it('rewritten_query が original_query と異なる場合のみ UI に反映される', async () => {
    (ragClient.streamChat as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      makeStream([
        {
          type: 'meta',
          rewritten_query: '書き換え後',
          original_query: '元の質問',
          sources: [],
          result_count: 0,
        },
        { type: 'done', confidence: 'low', processingTime: 0 },
      ]),
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage('元の質問');
    });

    await waitFor(() => {
      expect(result.current.messages[1].rewrittenQuery).toBe('書き換え後');
    });
  });

  it('rewritten_query が original_query と同じ場合は rewrittenQuery は未定義', async () => {
    (ragClient.streamChat as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      makeStream([
        {
          type: 'meta',
          rewritten_query: '同じ質問',
          original_query: '同じ質問',
          sources: [],
          result_count: 0,
        },
        { type: 'done', confidence: 'low', processingTime: 0 },
      ]),
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage('同じ質問');
    });

    await waitFor(() => {
      expect(result.current.messages[1].rewrittenQuery).toBeUndefined();
    });
  });

  it('error イベントでは status=error と errorMessage が設定される', async () => {
    (ragClient.streamChat as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      makeStream([
        { type: 'error', message: 'テストエラー', detail: 'detail' },
      ]),
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage('エラー');
    });

    await waitFor(() => {
      expect(result.current.messages[1].status).toBe('error');
      expect(result.current.messages[1].errorMessage).toBe('テストエラー');
    });
  });

  it('空文字や空白のみの入力は送信されない', async () => {
    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage('   ');
    });
    expect(result.current.messages).toHaveLength(0);
    expect(ragClient.streamChat).not.toHaveBeenCalled();
  });

  it('resetChat でメッセージがクリアされる', async () => {
    (ragClient.streamChat as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      makeStream([
        { type: 'token', content: 'hello' },
        { type: 'done', confidence: 'high', processingTime: 1 },
      ]),
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage('q');
    });
    await waitFor(() => expect(result.current.messages).toHaveLength(2));

    act(() => {
      result.current.resetChat();
    });
    expect(result.current.messages).toHaveLength(0);
    expect(result.current.isStreaming).toBe(false);
  });
});
