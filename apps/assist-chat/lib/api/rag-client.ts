// RAGバックエンドとの通信
// FastAPIサーバーにリクエストを送る

import {
  SearchRequest,
  SearchResponse,
  DocumentDetail,
  FilterMetadata,
  ApiError,
  FeedbackRequest,
} from '@/types';
import { API_CONFIG, API_ENDPOINTS, ERROR_MESSAGES } from '@/lib/constants';

class RagApiClient {
  private baseUrl: string;
  private timeout: number;

  constructor() {
    // 開発環境と本番環境でURLを切り替え
    this.baseUrl = process.env.NODE_ENV === 'production'
      ? API_CONFIG.BASE_URL_PROD
      : API_CONFIG.BASE_URL_DEV;
    this.timeout = API_CONFIG.TIMEOUT;
  }

  // 共通のfetch処理。タイムアウトとエラーハンドリングを一元化
  private async fetch<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const url = `${this.baseUrl}${endpoint}`;
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const error: ApiError = {
          error: response.statusText,
          statusCode: response.status,
        };

        try {
          const errorData = await response.json();
          error.error = errorData.error || error.error;
          error.details = errorData.details;
        } catch {
          // JSONパース失敗時はデフォルトエラーを使う
        }

        throw error;
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);

      // タイムアウト
      if (error instanceof Error && error.name === 'AbortError') {
        throw {
          error: ERROR_MESSAGES.TIMEOUT,
          statusCode: 408,
        } as ApiError;
      }

      // すでにApiError形式ならそのまま投げる
      if ((error as ApiError).statusCode) {
        throw error;
      }

      // ネットワークエラー
      throw {
        error: ERROR_MESSAGES.NETWORK_ERROR,
        statusCode: 0,
      } as ApiError;
    }
  }

  // 検索
  async search(request: SearchRequest): Promise<SearchResponse> {
    return this.fetch<SearchResponse>(API_ENDPOINTS.SEARCH, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // ドキュメント詳細取得
  async getDocument(docId: string): Promise<DocumentDetail> {
    return this.fetch<DocumentDetail>(`${API_ENDPOINTS.DOCUMENT}/${docId}`);
  }

  // フィルター用メタデータ取得
  async getFilterMetadata(): Promise<FilterMetadata> {
    return this.fetch<FilterMetadata>(API_ENDPOINTS.FILTER_METADATA);
  }

  // フィードバック送信
  async submitFeedback(request: FeedbackRequest): Promise<void> {
    return this.fetch<void>(API_ENDPOINTS.FEEDBACK, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // ヘルスチェック（バックエンドが起動してるか確認）
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
}

export const ragClient = new RagApiClient();
