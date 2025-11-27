/**
 * Type Definitions for AssistChat
 * 
 * 完全な型安全性を保証するための型定義集
 * フロントエンド ↔ バックエンド間でPydanticと一致
 */

// ==================== ドメインモデル ====================

/**
 * 検索結果の個別アイテム
 * バックエンドのSearchResultと完全一致
 */
export interface SearchResult {
  /** ドキュメント一意識別子 (例: "doc_000123") */
  doc_id: string;
  
  /** ドキュメントタイトル (例: "A84前工程 - モーター異音") */
  title: string;
  
  /** 要約テキスト (150文字程度) */
  summary: string;
  
  /** 検索スコア (0-1の範囲、FAISSコサイン類似度) */
  score: number;

  /** 信頼度 (0-100%) - UI表示用 */
  confidence: number;
  
  /** 抜粋テキスト (200文字程度) */
  snippet: string;
  
  /** 発生日時 (ISO 8601形式) */
  date: string;
  
  /** 設備名 (例: "面取設備", "乾燥冷却設備") */
  machine: string | null;
  
  /** 生産ライン (例: "B2321 製3BT切面") */
  line: string | null;
  
  /** 故障分類 (例: "電気", "機械", "PC") */
  category: string | null;
  
  /** マッチしたフィールドとそのスコア */
  match_fields: Record<string, number>;
  
  /** 発生場所 (オプション) */
  location?: string;
  
  /** 症状詳細 (オプション) */
  symptom?: string;
  
  /** 実施した対応 (オプション) */
  action_taken?: string;
  
  /** 交換部品 (オプション) */
  parts_replaced?: string;
  
  /** 作業者 (匿名化済み、オプション) */
  operator?: string;
}

/**
 * 検索フィルター条件
 * 
 * フィルター階層:
 * 1. 作業種別 (categories): 機械/電気
 * 2. 故障分類 (workTypes): 重大故障/修理票/作業票/連絡票
 * 3. 生産ライン (productionLines)
 * 4. 設備階層 (equipment1s → equipment2s → equipment3s)
 */
export interface SearchFilters {
  /** 年度範囲フィルター */
  yearRange?: {
    startYear: number;
    endYear: number;
  };
  
  /** 作業種別フィルター (複数選択可): 機械/電気 */
  categories?: string[];

  /** 工場フィルター (複数選択可) */
  locations?: string[];
  
  /** 故障分類フィルター (複数選択可): 重大故障/修理票/作業票/連絡票 */
  workTypes?: string[];
  
  /** 生産ラインフィルター (複数選択可) */
  productionLines?: string[];
  
  /** 設備1フィルター (複数選択可) - 大分類 */
  equipment1s?: string[];
  
  /** 設備2フィルター (複数選択可) - 中分類 */
  equipment2s?: string[];
  
  /** 設備3フィルター (複数選択可) - 小分類 */
  equipment3s?: string[];
  
  /** 重要度フィルター (複数選択可) */
  severity?: string[];
  
  /** キーワードフィルター (複数選択可) */
  keywords?: string[];
}

/**
 * 検索リクエスト
 * POST /api/search のボディ
 */
export interface SearchRequest {
  /** 検索クエリ文字列 */
  query: string;
  
  /** フィルター条件 (オプション) */
  filters?: SearchFilters;
  
  /** 取得する結果数 (デフォルト: 5, 最大: 20) */
  k?: number;
}

/**
 * 検索レスポンス
 * POST /api/search の返却値
 */
export interface SearchResponse {
  /** 検索結果の配列 */
  results: SearchResult[];
  
  /** 総件数 */
  total: number;
  
  /** 処理時間 (ミリ秒) */
  processingTime: number;
}

// ==================== ドキュメント詳細 ====================

/**
 * ドキュメントの詳細情報
 * GET /api/docs/{doc_id} の返却値
 */
export interface DocumentDetail {
  /** ドキュメント一意識別子 */
  doc_id: string;
  
  /** タイトル */
  title: string;
  
  /** コンテンツ本文 */
  content: string;
  
  /** メタデータ (任意のキー・バリュー) */
  metadata: Record<string, unknown>;
  
  /** 添付ファイルURL一覧 */
  attachments: string[];
  
  /** 全文テキスト */
  full_text: string;
  
  /** チャンク分割されたテキスト */
  chunks: DocumentChunk[];

  /** 実施した対応 (オプション) */
  action_taken?: string;

  /** 交換部品 (オプション) */
  parts_replaced?: string;
}

/**
 * ドキュメントのチャンク
 * Embeddingに使用される単位
 */
export interface DocumentChunk {
  /** チャンク一意識別子 */
  chunk_id: string;
  
  /** チャンクのテキスト内容 */
  text: string;
  
  /** チャンクのインデックス番号 (0始まり) */
  chunk_index: number;
  
  /** 元のドキュメントID */
  source_doc_id: string;
}



// ==================== フィードバック ====================

/**
 * フィードバックリクエスト
 * POST /api/feedback のボディ
 */
export interface FeedbackRequest {
  /** 対象ドキュメントID */
  doc_id: string;
  
  /** 評価 (1-5) */
  rating: number;
  
  /** コメント (オプション) */
  comment?: string;
  
  /** 役に立ったか */
  helpful: boolean;
}

/**
 * フィードバックレスポンス
 */
export interface FeedbackResponse {
  /** 成功フラグ */
  success: boolean;
  
  /** メッセージ */
  message: string;
}

// ==================== フィルターメタデータ ====================

export interface HierarchyNode {
  /** ノードID (値) */
  id: string;
  
  /** 表示ラベル */
  label: string;
  
  /** 子ノード */
  children: HierarchyNode[];
}

/**
 * フィルターメタデータ
 * GET /api/search/metadata の返却値
 * 
 * 各フィルターで利用可能な値のリストを提供
 */
export interface FilterMetadata {
  /** 利用可能な作業種別一覧: 機械/電気 */
  categories: string[];
  
  /** 利用可能な故障分類一覧: 重大故障/修理票/作業票/連絡票 */
  workTypes: string[];
  
  /** 利用可能な生産ライン一覧 */
  productionLines: string[];
  
  /** 利用可能な設備1一覧（大分類） */
  equipment1s: string[];
  
  /** 利用可能な設備2一覧（中分類） */
  equipment2s: string[];
  
  /** 利用可能な設備3一覧（小分類） */
  equipment3s: string[];
  
  /** 年度範囲 */
  yearRange: {
    startYear: number;
    endYear: number;
  };
  
  /** 総ドキュメント数 */
  totalDocuments: number;
  
  /** 階層構造（工場 → ライン → 設備1 → 設備2 → 設備3） */
  hierarchy?: HierarchyNode[];
}

// ==================== エラー型 ====================

/**
 * APIエラーレスポンス
 */
export interface ApiError {
  /** エラーメッセージ */
  error: string;
  
  /** HTTPステータスコード */
  statusCode: number;
  
  /** 詳細情報 (オプション) */
  details?: string;
  
  /** タイムスタンプ */
  timestamp?: string;
}

/**
 * バリデーションエラー
 */
export interface ValidationError {
  /** フィールド名 */
  field: string;
  
  /** エラーメッセージ */
  message: string;
}

// ==================== UI状態型 ====================

/**
 * ローディング状態
 */
export interface LoadingState {
  /** ローディング中フラグ */
  isLoading: boolean;
  
  /** ローディングメッセージ (オプション) */
  message?: string;
}

/**
 * エラー状態
 */
export interface ErrorState {
  /** エラーフラグ */
  hasError: boolean;
  
  /** エラーメッセージ */
  message: string;
  
  /** エラーコード (オプション) */
  code?: string;
}

/**
 * ページネーション情報
 */
export interface PaginationInfo {
  /** 現在のページ番号 (1始まり) */
  currentPage: number;
  
  /** 総ページ数 */
  totalPages: number;
  
  /** 1ページあたりの件数 */
  pageSize: number;
  
  /** 総件数 */
  totalItems: number;
}

// ==================== コンポーネントProps型 ====================

/**
 * 検索バーのProps
 */
export interface SearchInputProps {
  /** 検索クエリ */
  value: string;
  
  /** 値変更ハンドラー */
  onChange: (value: string) => void;
  
  /** 検索実行ハンドラー */
  onSearch: () => void;
  
  /** ローディング中フラグ */
  isLoading?: boolean;
  
  /** プレースホルダーテキスト */
  placeholder?: string;
  
  /** 無効化フラグ */
  disabled?: boolean;
}

/**
 * 検索結果カードのProps
 */
export interface ResultCardProps {
  /** 検索結果データ */
  result: SearchResult;
  
  /** クリックハンドラー */
  onClick: (docId: string) => void;
  
  /** 選択中フラグ */
  isSelected?: boolean;
  
  /** ハイライトするキーワード */
  highlightKeywords?: string[];
}

/**
 * フィルターパネルのProps
 */
export interface FilterPanelProps {
  /** 現在のフィルター状態 */
  filters: SearchFilters;
  
  /** フィルター変更ハンドラー */
  onChange: (filters: SearchFilters) => void;
  
  /** フィルターメタデータ */
  metadata: FilterMetadata;
  
  /** リセットハンドラー */
  onReset: () => void;
}

// ==================== ユーティリティ型 ====================

/**
 * カテゴリー定義
 */
export interface CategoryDefinition {
  /** ラベル */
  label: string;
  
  /** カラークラス (Tailwind) */
  color: string;
  
  /** マッチングキーワード */
  keywords: string[];
}

/**
 * 日付範囲
 */
export interface DateRange {
  /** 開始日 (ISO 8601) */
  start: string;
  
  /** 終了日 (ISO 8601) */
  end: string;
}

/**
 * ソート順序
 */
export type SortOrder = 'asc' | 'desc';

/**
 * ソート条件
 */
export interface SortCriteria {
  /** ソートフィールド */
  field: keyof SearchResult;
  
  /** ソート順序 */
  order: SortOrder;
}

// ==================== 型ガード ====================

/**
 * SearchResult型ガード
 */
export function isSearchResult(obj: unknown): obj is SearchResult {
  if (typeof obj !== 'object' || obj === null) return false;
  const result = obj as Partial<SearchResult>;
  return (
    typeof result.doc_id === 'string' &&
    typeof result.title === 'string' &&
    typeof result.score === 'number'
  );
}

/**
 * ApiError型ガード
 */
export function isApiError(obj: unknown): obj is ApiError {
  if (typeof obj !== 'object' || obj === null) return false;
  const error = obj as Partial<ApiError>;
  return (
    typeof error.error === 'string' &&
    typeof error.statusCode === 'number'
  );
}
