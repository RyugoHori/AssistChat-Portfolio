// テキスト処理のユーティリティ
// 切り詰め、ハイライト、検索など

import { SEARCH_CONFIG } from '@/lib/constants';

// テキストを指定文字数で切り詰める
export function truncate(
  text: string,
  maxLength: number,
  suffix = '...'
): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  
  return text.slice(0, maxLength) + suffix;
}

// スニペット生成
// キーワードがあればその周辺を優先的に表示
export function createSnippet(
  text: string,
  keywords: string[] = [],
  maxLength = SEARCH_CONFIG.MAX_SNIPPET_LENGTH
): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  
  // キーワードが含まれている場合、その周辺を抽出
  if (keywords.length > 0) {
    for (const keyword of keywords) {
      const index = text.toLowerCase().indexOf(keyword.toLowerCase());
      if (index !== -1) {
        // キーワードを中心に前後の文字を取得
        const start = Math.max(0, index - Math.floor(maxLength / 2));
        const end = Math.min(text.length, start + maxLength);
        
        let snippet = text.slice(start, end);
        
        if (start > 0) snippet = '...' + snippet;
        if (end < text.length) snippet = snippet + '...';
        
        return snippet;
      }
    }
  }
  
  // キーワードが見つからない場合は先頭から
  return text.slice(0, maxLength) + '...';
}

// キーワードをハイライト（<mark>タグで囲む）
export function highlightKeywords(
  text: string,
  keywords: string[]
): string {
  if (!text || keywords.length === 0) return text;
  
  let result = text;
  
  // 長いキーワードから処理（短いキーワードが先だと部分一致で壊れる）
  const sortedKeywords = [...keywords].sort((a, b) => b.length - a.length);
  
  for (const keyword of sortedKeywords) {
    if (!keyword.trim()) continue;
    
    const regex = new RegExp(`(${escapeRegExp(keyword)})`, 'gi');
    result = result.replace(regex, '<mark class="bg-yellow-200">$1</mark>');
  }
  
  return result;
}

// 正規表現用にエスケープ
function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// HTMLタグを除去
export function stripHtml(html: string): string {
  if (!html) return '';
  return html.replace(/<[^>]*>/g, '');
}

// HTMLエンティティをエスケープ（XSS対策）
export function escapeHtml(text: string): string {
  if (!text) return '';
  
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  };
  
  return text.replace(/[&<>"']/g, (char) => map[char] || char);
}

// 改行を<br>に変換
export function nl2br(text: string): string {
  if (!text) return '';
  return text.replace(/\n/g, '<br>');
}

// テキスト検索（大文字小文字区別なし）
export function searchText(text: string, query: string): boolean {
  if (!text || !query) return false;
  return text.toLowerCase().includes(query.toLowerCase());
}

// AND検索（すべてのキーワードを含む）
export function searchTextAND(text: string, keywords: string[]): boolean {
  if (!text || keywords.length === 0) return false;
  
  const lowerText = text.toLowerCase();
  return keywords.every((keyword) =>
    lowerText.includes(keyword.toLowerCase())
  );
}

// OR検索（いずれかのキーワードを含む）
export function searchTextOR(text: string, keywords: string[]): boolean {
  if (!text || keywords.length === 0) return false;
  
  const lowerText = text.toLowerCase();
  return keywords.some((keyword) =>
    lowerText.includes(keyword.toLowerCase())
  );
}
