// 日付を日本語の年月日にする

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
