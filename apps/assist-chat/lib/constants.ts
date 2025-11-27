// アプリケーション定数
// マジックナンバーを排除するために一元管理

import { CategoryDefinition } from '@/types';

// ==================== アプリ情報 ====================

export const APP_NAME = 'AssistChat';
export const APP_DESCRIPTION = '故障対応検索システム - 過去の故障事例から最適な対処法を瞬時に検索';
export const APP_VERSION = '2.0.0';

// ==================== 検索設定 ====================

export const SEARCH_CONFIG = {
  DEFAULT_RESULTS_LIMIT: 20,
  MIN_RESULTS_LIMIT: 1,
  MAX_RESULTS_LIMIT: 50,
  DEBOUNCE_DELAY: 500,  // 入力後500msで検索実行
  MIN_QUERY_LENGTH: 1,
  MAX_QUERY_LENGTH: 200,
  MAX_SNIPPET_LENGTH: 200,
  MAX_SUMMARY_LENGTH: 150,
} as const;

// ==================== 重要度 ====================

export const SEVERITY_LEVELS = {
  CRITICAL: {
    label: '重大',
    color: 'bg-red-100 text-red-800 border-red-200',
    keywords: ['緊急', '停止', '重大', '交換', '破損', '火災', '漏洩'],
  },
  NORMAL: {
    label: '通常',
    color: 'bg-gray-100 text-gray-800 border-gray-200',
    keywords: [],
  },
} as const;

// ==================== 日付範囲 ====================

export const DATE_RANGES = {
  LAST_WEEK: 7,
  LAST_MONTH: 30,
  LAST_3_MONTHS: 90,
  LAST_6_MONTHS: 180,
  LAST_YEAR: 365,
} as const;

// ==================== UI設定 ====================

export const UI_CONFIG = {
  TOAST_DURATION: 3000,
  ANIMATION_DELAY: 200,
  MIN_LOADING_TIME: 300,
  INFINITE_SCROLL_THRESHOLD: 200,
  MOBILE_BREAKPOINT: 768,
  TABLET_BREAKPOINT: 1024,
} as const;

export const COLORS = {
  PRIMARY: 'blue',
  SECONDARY: 'green',
  ACCENT: 'orange',
  DANGER: 'red',
  WARNING: 'yellow',
  SUCCESS: 'green',
  INFO: 'blue',
} as const;

// ==================== ページネーション ====================

export const PAGINATION_CONFIG = {
  DEFAULT_PAGE_SIZE: 20,
  PAGE_SIZE_OPTIONS: [10, 20, 50, 100] as const,
  MAX_PAGE_DISPLAY: 5,
} as const;

// ==================== キャッシュ ====================

export const CACHE_CONFIG = {
  SEARCH_RESULTS_TTL: 300,     // 5分
  FILTER_METADATA_TTL: 3600,   // 1時間
  DOCUMENT_DETAIL_TTL: 600,    // 10分
} as const;

// ==================== API設定 ====================

export const API_CONFIG = {
  BASE_URL_DEV: 'http://localhost:8001',
  BASE_URL_PROD: process.env.NEXT_PUBLIC_API_URL || '',
  TIMEOUT: 30000,  // 30秒
  RETRY_COUNT: 3,
  RETRY_DELAY: 1000,
} as const;

// ==================== エラーメッセージ ====================

export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'ネットワークエラーが発生しました。接続を確認してください。',
  TIMEOUT: 'リクエストがタイムアウトしました。しばらくしてから再度お試しください。',
  SERVER_ERROR: 'サーバーエラーが発生しました。しばらくしてから再度お試しください。',
  VALIDATION_ERROR: '入力内容に誤りがあります。確認してください。',
  NO_RESULTS: '検索結果が見つかりませんでした。キーワードを変更してお試しください。',
  UNKNOWN_ERROR: '予期しないエラーが発生しました。',
  BACKEND_CONNECTION_ERROR: 'バックエンドサービスに接続できません。Docker Composeが起動しているか確認してください。',
} as const;

// ==================== 成功メッセージ ====================

export const SUCCESS_MESSAGES = {
  SEARCH_SUCCESS: '検索が完了しました。',
  FEEDBACK_SUBMITTED: 'フィードバックを送信しました。ありがとうございます。',
  COPIED_TO_CLIPBOARD: 'クリップボードにコピーしました。',
} as const;

// ==================== LocalStorageキー ====================

export const STORAGE_KEYS = {
  RECENT_SEARCHES: 'assistchat_recent_searches',
  USER_PREFERENCES: 'assistchat_user_preferences',
  FILTER_STATE: 'assistchat_filter_state',
  THEME: 'assistchat_theme',
} as const;

// ==================== 機能フラグ ====================

// 開発中の機能のオン/オフ
export const FEATURE_FLAGS = {
  ENABLE_FEEDBACK: true,
  ENABLE_EXPORT: false,        // 未実装
  ENABLE_ADVANCED_SEARCH: false,  // 未実装
  ENABLE_DARK_MODE: false,     // 未実装
} as const;

// ==================== 正規表現 ====================

export const REGEX_PATTERNS = {
  EMAIL: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
  DATE: /^\d{4}-\d{2}-\d{2}$/,
  DATE_SLASH: /^\d{4}\/\d{2}\/\d{2}$/,
  DOCUMENT_ID: /^doc_\d{6}$/,
} as const;

// ==================== ルート ====================

export const ROUTES = {
  HOME: '/',
  SEARCH: '/search',
  DOCUMENT: '/document',
  SETTINGS: '/settings',
} as const;

// ==================== APIエンドポイント ====================

export const API_ENDPOINTS = {
  SEARCH: '/api/search',
  DOCUMENT: '/api/docs',
  FILTER_METADATA: '/api/search/metadata',
  FEEDBACK: '/api/feedback',
  HEALTH: '/health',
} as const;
