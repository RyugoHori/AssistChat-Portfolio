/**
 * フロントの型。バックエンドの Pydantic モデルと項目を揃えている。
 */

/** 検索結果の1件 */
export interface SearchResult {
  /** ドキュメントID (例: "doc_000123") */
  doc_id: string;
  
  /** タイトル (例: "切断機 切断圧低下") */
  title: string;
  
  /** 検索スコア（0-1） */
  score: number;

  /** 信頼度 (0-100%) - UI表示用 */
  confidence: number;
  
  /** 抜粋テキスト (200文字程度) */
  snippet: string;
  
  /** 発生日時 (ISO 8601形式) */
  date: string;
  
  /** 設備名 (例: "切断機", "ローラーコンベア") */
  machine: string | null;
  
  /** 生産ライン (例: "A1000 生産ラインA") */
  line: string | null;
  
  /** 分類 (例: "機械", "電気") */
  category: string | null;
  
  /** 発生場所 (オプション) */
  location?: string;
  
  /** 症状詳細 (オプション) */
  symptom?: string;
  
  /** 実施した対応 (オプション) */
  action_taken?: string;
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
  
  /** 取得する結果数 (最大: 10) */
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

  /** 検索ID。利用ログで、閲覧とフィードバックをこの検索に結び付ける */
  searchId?: string;
}


/**
 * ドキュメントの詳細情報
 * GET /api/docs/{doc_id} の返却値
 */
export interface DocumentDetail {
  /** ドキュメント一意識別子 */
  doc_id: string;
  
  /** タイトル */
  title: string;
  
  /** メタデータ (任意のキー・バリュー) */
  metadata: Record<string, unknown>;
  
  /** 全文テキスト */
  full_text: string;

  /** 実施した対応 (オプション) */
  action_taken?: string;
}

/**
 * チャットメッセージの役割
 */
export type ChatRole = 'user' | 'assistant';

/**
 * チャットメッセージ（UI とバックエンド双方で共有）
 *
 * UI 専用フィールド（id, sources, status 等）は Message 型側で拡張する。
 */
export interface ChatMessage {
  role: ChatRole;
  content: string;
}

/**
 * AI 回答の引用元
 */
export interface ChatSource {
  doc_id: string;
  title: string;
  score: number;
}

/**
 * /api/chat リクエスト
 *
 * `messages` は直近のユーザー発言を含まない会話履歴。
 * 直近のユーザー質問は `query` に入れる。
 */
export interface ChatRequest {
  query: string;
  messages?: ChatMessage[];
  filters?: SearchFilters;
  k?: number;
}

/**
 * ストリーミングイベントの型
 *
 * バックエンドは NDJSON を 1 行ずつ送出し、各行はこの型のいずれか。
 */
export type ChatStreamEvent =
  | { type: 'stage'; stage: 'rewriting' | 'searching' | 'generating' }
  | {
      type: 'meta';
      rewritten_query: string;
      original_query: string;
      sources: ChatSource[];
      result_count: number;
    }
  | { type: 'token'; content: string }
  | { type: 'done'; confidence: ChatConfidence; processingTime: number }
  | { type: 'error'; message: string; detail?: string };

/**
 * 回答の信頼度
 */
export type ChatConfidence = 'high' | 'low' | 'unavailable' | 'unknown';

/**
 * UI 側のチャットメッセージ（履歴表示用）
 *
 * バックエンドに送るときは role と content のみを抽出する。
 */
export interface ChatUiMessage extends ChatMessage {
  /** クライアント一意 ID（React の key 用） */
  id: string;
  /** ストリーミング状態 */
  status: 'pending' | 'streaming' | 'complete' | 'error';
  /** AI 回答の引用元（assistant のみ） */
  sources?: ChatSource[];
  /** 書き換え後の検索クエリ（UI に薄く表示） */
  rewrittenQuery?: string;
  /** 信頼度 */
  confidence?: ChatConfidence;
  /** エラーメッセージ（status=error のとき） */
  errorMessage?: string;
}


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

  /** どの検索の結果か (オプション) */
  search_id?: string;

  /** その検索での表示順位 (1始まり、オプション) */
  rank?: number;

  /** 検索クエリ (オプション) */
  query?: string;

  /** 送信元のモード (オプション、省略時はバックエンドで search) */
  mode?: 'search' | 'chat';
}

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
}

