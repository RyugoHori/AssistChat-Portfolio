'use client';

import { useCallback, useRef, useState } from 'react';

import { ragClient } from '@/lib/api/rag-client';
import { CHAT_CONFIG, ERROR_MESSAGES } from '@/lib/constants';
import {
  ApiError,
  ChatConfidence,
  ChatMessage,
  ChatUiMessage,
  SearchFilters,
} from '@/types';

/**
 * クライアント一意 ID（React key 用）
 *
 * crypto.randomUUID が使えない環境（非 HTTPS / 古いブラウザ）にも対応。
 */
function generateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `msg_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export interface UseChatOptions {
  /** フィルターを検索クエリに反映させる（検索モードのフィルターと共有する想定） */
  filters?: SearchFilters;
}

/**
 * AI チャットモード用のステートフルフック
 *
 * - 会話履歴をメモリに保持し、送信時にバックエンドへ渡す
 * - サーバーからの NDJSON ストリームを段階的に UI に反映
 * - 入力 → 送信 → ストリーミング → 完了 までのライフサイクルを管理
 */
export function useChat(options: UseChatOptions = {}) {
  const [messages, setMessages] = useState<ChatUiMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  /**
   * assistant メッセージを id で差分更新する内部ヘルパー
   */
  const updateAssistantMessage = useCallback(
    (id: string, updater: (msg: ChatUiMessage) => ChatUiMessage) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? updater(m) : m)),
      );
    },
    [],
  );

  /**
   * 会話をリセット
   */
  const resetChat = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setMessages([]);
    setIsStreaming(false);
  }, []);

  /**
   * 進行中のストリーミングを中断
   */
  const stopStreaming = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
  }, []);

  /**
   * ユーザー発言を送信して AI 回答をストリーミング取得する
   */
  const sendMessage = useCallback(
    async (rawInput: string) => {
      const query = rawInput.trim();
      if (!query || isStreaming) return;

      const userMessage: ChatUiMessage = {
        id: generateId(),
        role: 'user',
        content: query,
        status: 'complete',
      };
      const assistantId = generateId();
      const assistantPlaceholder: ChatUiMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        status: 'pending',
      };

      // 送信前のメッセージ（ユーザー発言を含まない過去履歴）を snapshot
      const historyBeforeSend: ChatMessage[] = messages
        .filter((m) => m.status === 'complete')
        .map(({ role, content }) => ({ role, content }));

      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const stream = ragClient.streamChat(
          {
            query,
            messages: historyBeforeSend,
            filters: options.filters,
            k: CHAT_CONFIG.DEFAULT_K,
          },
          controller.signal,
        );

        for await (const event of stream) {
          switch (event.type) {
            case 'stage':
              updateAssistantMessage(assistantId, (msg) => ({
                ...msg,
                status: event.stage === 'generating' ? 'streaming' : 'pending',
              }));
              break;

            case 'meta':
              updateAssistantMessage(assistantId, (msg) => ({
                ...msg,
                sources: event.sources,
                rewrittenQuery:
                  event.rewritten_query !== event.original_query
                    ? event.rewritten_query
                    : undefined,
              }));
              break;

            case 'token':
              updateAssistantMessage(assistantId, (msg) => ({
                ...msg,
                status: 'streaming',
                content: msg.content + event.content,
              }));
              break;

            case 'done':
              updateAssistantMessage(assistantId, (msg) => ({
                ...msg,
                status: 'complete',
                confidence: (event.confidence as ChatConfidence) || 'unknown',
              }));
              break;

            case 'error':
              updateAssistantMessage(assistantId, (msg) => ({
                ...msg,
                status: 'error',
                errorMessage: event.message,
                confidence: 'unavailable',
              }));
              break;
          }
        }
      } catch (err) {
        // AbortError（ユーザー操作でキャンセル）は正常終了扱い
        if ((err as Error)?.name === 'AbortError') {
          updateAssistantMessage(assistantId, (msg) => ({
            ...msg,
            status: 'complete',
            content: msg.content || '（応答を中断しました）',
          }));
        } else {
          const apiError = err as ApiError;
          updateAssistantMessage(assistantId, (msg) => ({
            ...msg,
            status: 'error',
            errorMessage:
              apiError?.error || ERROR_MESSAGES.SERVER_ERROR,
          }));
        }
      } finally {
        abortControllerRef.current = null;
        setIsStreaming(false);
      }
    },
    [isStreaming, messages, options.filters, updateAssistantMessage],
  );

  return {
    messages,
    isStreaming,
    sendMessage,
    resetChat,
    stopStreaming,
  };
}
