// RAG バックエンドクライアント
//
// `/api/search` など JSON レスポンスを返すエンドポイントは `fetch<T>()` を経由し、
// `/api/chat` のストリーミング（NDJSON）は `streamChat()` で別系統として扱う。

import {
  ApiError,
  ChatRequest,
  ChatStreamEvent,
  DocumentDetail,
  FeedbackRequest,
  FilterMetadata,
  SearchRequest,
  SearchResponse,
} from '@/types';
import { API_CONFIG, API_ENDPOINTS, CHAT_CONFIG, ERROR_MESSAGES } from '@/lib/constants';

class RagApiClient {
  private readonly baseUrl: string;
  private readonly timeout: number;

  constructor() {
    // ブラウザ実行時は NEXT_PUBLIC_API_URL が優先。ビルド時に値が無ければ開発用 URL。
    const configured = process.env.NEXT_PUBLIC_API_URL;
    this.baseUrl =
      configured && configured.length > 0 ? configured : API_CONFIG.BASE_URL_DEV;
    this.timeout = API_CONFIG.TIMEOUT;
  }

  /**
   * JSON レスポンスを返すエンドポイント用の共通 fetch
   * タイムアウトとエラー整形を一元化する。
   */
  private async fetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const apiError: ApiError = {
          error: response.statusText,
          statusCode: response.status,
        };
        try {
          const errorData = await response.json();
          apiError.error = errorData.detail || errorData.error || apiError.error;
          apiError.details = errorData.details;
        } catch {
          // JSON パース失敗時は既定のエラー情報のまま投げる
        }
        throw apiError;
      }

      return (await response.json()) as T;
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof Error && error.name === 'AbortError') {
        throw { error: ERROR_MESSAGES.TIMEOUT, statusCode: 408 } as ApiError;
      }
      if ((error as ApiError).statusCode !== undefined) {
        throw error;
      }
      throw { error: ERROR_MESSAGES.NETWORK_ERROR, statusCode: 0 } as ApiError;
    }
  }

  // ==================== 検索系 API ====================

  search(request: SearchRequest): Promise<SearchResponse> {
    return this.fetch<SearchResponse>(API_ENDPOINTS.SEARCH, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  getDocument(docId: string): Promise<DocumentDetail> {
    return this.fetch<DocumentDetail>(`${API_ENDPOINTS.DOCUMENT}/${docId}`);
  }

  getFilterMetadata(): Promise<FilterMetadata> {
    return this.fetch<FilterMetadata>(API_ENDPOINTS.FILTER_METADATA);
  }

  submitFeedback(request: FeedbackRequest): Promise<void> {
    return this.fetch<void>(API_ENDPOINTS.FEEDBACK, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async health(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}${API_ENDPOINTS.HEALTH}`, {
        method: 'GET',
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  // ==================== チャット API（ストリーミング） ====================

  /**
   * AI チャットのストリーミングエンドポイントへ POST し、
   * NDJSON を 1 行ずつ `ChatStreamEvent` としてイテレートする。
   *
   * 呼び出し例:
   * ```ts
   * const controller = new AbortController();
   * for await (const event of ragClient.streamChat(req, controller.signal)) {
   *   // handle event
   * }
   * ```
   *
   * @param signal - 呼び出し側からストリームをキャンセルするための AbortSignal
   */
  async *streamChat(
    request: ChatRequest,
    signal?: AbortSignal,
  ): AsyncGenerator<ChatStreamEvent, void, void> {
    const response = await fetch(`${this.baseUrl}${API_ENDPOINTS.CHAT}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...request,
        messages: (request.messages ?? []).slice(-CHAT_CONFIG.MAX_HISTORY_TO_SEND),
      }),
      signal,
    });

    if (!response.ok) {
      let detail: string | undefined;
      try {
        const errJson = await response.json();
        detail = errJson.detail || errJson.error;
      } catch {
        // noop
      }
      throw {
        error: detail || response.statusText,
        statusCode: response.status,
      } as ApiError;
    }
    if (!response.body) {
      throw { error: ERROR_MESSAGES.NETWORK_ERROR, statusCode: 0 } as ApiError;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        // NDJSON: 改行ごとに 1 イベント
        let newlineIndex: number;
        while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
          const line = buffer.slice(0, newlineIndex).trim();
          buffer = buffer.slice(newlineIndex + 1);
          if (!line) continue;
          try {
            yield JSON.parse(line) as ChatStreamEvent;
          } catch (err) {
            console.warn('[streamChat] JSON パース失敗:', line, err);
          }
        }
      }
      // 最終バッファに残った 1 行を処理
      const tail = buffer.trim();
      if (tail) {
        try {
          yield JSON.parse(tail) as ChatStreamEvent;
        } catch (err) {
          console.warn('[streamChat] 末尾 JSON パース失敗:', tail, err);
        }
      }
    } finally {
      reader.releaseLock();
    }
  }
}

export const ragClient = new RagApiClient();
