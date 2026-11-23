export const APP_NAME = 'AssistChat';
export const APP_DESCRIPTION = '故障対応検索システム - 過去の故障事例から似た対処を探す';


export const SEARCH_CONFIG = {
  DEFAULT_RESULTS_LIMIT: 10,
  MIN_QUERY_LENGTH: 1,
  MAX_QUERY_LENGTH: 200,
} as const;


export const API_CONFIG = {
  BASE_URL_DEV: 'http://localhost:8001',
  TIMEOUT: 30000,  // 30秒
} as const;


export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'ネットワークエラーが発生しました。接続を確認してください。',
  TIMEOUT: 'リクエストがタイムアウトしました。しばらくしてから再度お試しください。',
  SERVER_ERROR: 'サーバーエラーが発生しました。しばらくしてから再度お試しください。',
} as const;


export const API_ENDPOINTS = {
  SEARCH: '/api/search',
  DOCUMENT: '/api/docs',
  FILTER_METADATA: '/api/search/metadata',
  FEEDBACK: '/api/feedback',
  CHAT: '/api/chat',
} as const;


export const CHAT_CONFIG = {
  MAX_MESSAGE_LENGTH: 500,
  MAX_HISTORY_TO_SEND: 10,
  DEFAULT_K: 5,
  INITIAL_GREETING:
    'こんにちは。過去の保全記録を基にトラブル対応をお手伝いします。気になる故障内容や症状をお送りください。',
} as const;
