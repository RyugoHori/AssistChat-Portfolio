// 日付処理のユーティリティ
// フォーマット、相対時間表示など

import { REGEX_PATTERNS } from '@/lib/constants';

// 日本語形式の日付に変換（2024年1月15日）
export function formatDate(isoString: string): string {
  try {
    const date = new Date(isoString);
    
    if (isNaN(date.getTime())) {
      return isoString; // パース失敗時は元の文字列を返す
    }
    
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    
    return `${year}年${month}月${day}日`;
  } catch (error) {
    console.error('日付フォーマットエラー:', error);
    return isoString;
  }
}

// 日時形式に変換（2024年1月15日 10:30）
export function formatDateTime(isoString: string, includeSeconds = false): string {
  try {
    const date = new Date(isoString);
    
    if (isNaN(date.getTime())) {
      return isoString;
    }
    
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    let result = `${year}年${month}月${day}日 ${hours}:${minutes}`;
    
    if (includeSeconds) {
      const seconds = String(date.getSeconds()).padStart(2, '0');
      result += `:${seconds}`;
    }
    
    return result;
  } catch (error) {
    console.error('日時フォーマットエラー:', error);
    return isoString;
  }
}

// 相対時間表示（3日前、2ヶ月前など）
export function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    const now = new Date();
    
    if (isNaN(date.getTime())) {
      return isoString;
    }
    
    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);
    const diffMonths = Math.floor(diffDays / 30);
    const diffYears = Math.floor(diffDays / 365);
    
    if (diffSeconds < 60) {
      return 'たった今';
    } else if (diffMinutes < 60) {
      return `${diffMinutes}分前`;
    } else if (diffHours < 24) {
      return `${diffHours}時間前`;
    } else if (diffDays < 30) {
      return `${diffDays}日前`;
    } else if (diffMonths < 12) {
      return `${diffMonths}ヶ月前`;
    } else {
      return `${diffYears}年前`;
    }
  } catch (error) {
    console.error('相対時間フォーマットエラー:', error);
    return isoString;
  }
}

// 2つの日付間の日数を計算
export function getDaysBetween(startDate: string, endDate?: string): number {
  try {
    const start = new Date(startDate);
    const end = endDate ? new Date(endDate) : new Date();
    
    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      return 0;
    }
    
    const diffMs = end.getTime() - start.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    return Math.abs(diffDays);
  } catch (error) {
    console.error('日数計算エラー:', error);
    return 0;
  }
}

// 日付文字列が有効かチェック
export function isValidDate(dateString: string): boolean {
  try {
    const date = new Date(dateString);
    return !isNaN(date.getTime());
  } catch {
    return false;
  }
}

// YYYY-MM-DD形式かチェック
export function isYYYYMMDD(dateString: string): boolean {
  return REGEX_PATTERNS.DATE.test(dateString);
}

// YYYY-MM-DD形式に変換
export function toYYYYMMDD(date: Date | string): string {
  try {
    const d = typeof date === 'string' ? new Date(date) : date;
    
    if (isNaN(d.getTime())) {
      return '';
    }
    
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    
    return `${year}-${month}-${day}`;
  } catch (error) {
    console.error('日付変換エラー:', error);
    return '';
  }
}

// ISO 8601形式に変換
export function toISO8601(date: Date | string): string {
  try {
    const d = typeof date === 'string' ? new Date(date) : date;
    
    if (isNaN(d.getTime())) {
      return '';
    }
    
    return d.toISOString();
  } catch (error) {
    console.error('ISO変換エラー:', error);
    return '';
  }
}

// 年度を抽出
export function getYear(isoString: string): number {
  try {
    const date = new Date(isoString);
    
    if (isNaN(date.getTime())) {
      return 0;
    }
    
    return date.getFullYear();
  } catch (error) {
    console.error('年度抽出エラー:', error);
    return 0;
  }
}

// 日付範囲内かチェック
export function isInDateRange(
  targetDate: string,
  startDate: string | null,
  endDate: string | null
): boolean {
  try {
    const target = new Date(targetDate);
    
    if (isNaN(target.getTime())) {
      return false;
    }
    
    if (startDate) {
      const start = new Date(startDate);
      if (!isNaN(start.getTime()) && target < start) {
        return false;
      }
    }
    
    if (endDate) {
      const end = new Date(endDate);
      if (!isNaN(end.getTime()) && target > end) {
        return false;
      }
    }
    
    return true;
  } catch (error) {
    console.error('日付範囲チェックエラー:', error);
    return false;
  }
}

// 今日の日付（YYYY-MM-DD）
export function getToday(): string {
  return toYYYYMMDD(new Date());
}

// N日前の日付
export function getDaysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return toYYYYMMDD(date);
}

// 月の最初の日
export function getFirstDayOfMonth(year: number, month: number): string {
  const date = new Date(year, month - 1, 1);
  return toYYYYMMDD(date);
}

// 月の最後の日
export function getLastDayOfMonth(year: number, month: number): string {
  const date = new Date(year, month, 0);
  return toYYYYMMDD(date);
}
