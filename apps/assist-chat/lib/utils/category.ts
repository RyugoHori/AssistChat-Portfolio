// カテゴリと故障分類の色・アイコン
// バックエンドから動的に取得したカテゴリに対応

// カテゴリの色（Tailwindクラス）
export function getCategoryColor(category: string | null | undefined): string {
  if (!category) {
    return 'bg-gray-100 text-gray-800';
  }

  switch (category) {
    case '電気':
      return 'bg-yellow-100 text-yellow-800';
    case '機械':
      return 'bg-blue-100 text-blue-800';
    case 'PC':
      return 'bg-green-100 text-green-800';
    case '配管':
      return 'bg-purple-100 text-purple-800';
    case 'その他':
      return 'bg-gray-100 text-gray-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

// カテゴリのアイコン（絵文字）
export function getCategoryIcon(category: string | null | undefined): string {
  if (!category) {
    return '📋';
  }

  switch (category) {
    case '電気':
      return '⚡';
    case '機械':
      return '⚙️';
    case 'PC':
      return '💻';
    case '配管':
      return '🔧';
    case 'その他':
      return '📋';
    default:
      return '📋';
  }
}

// 故障分類（work_type）の色
// 重要度に応じて色を変えてる
// - 重大故障: 赤（目立つように）
// - 修理票: オレンジ
// - 作業票: 青
// - 連絡票: 緑
export function getWorkTypeColor(workType: string | null | undefined): string {
  if (!workType) {
    return 'bg-gray-100 text-gray-800';
  }

  switch (workType) {
    case '重大故障':
      return 'bg-red-100 text-red-800 font-medium';
    case '修理票':
      return 'bg-orange-100 text-orange-800';
    case '作業票':
      return 'bg-blue-100 text-blue-800';
    case '連絡票':
      return 'bg-green-100 text-green-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

// 故障分類のアイコン
export function getWorkTypeIcon(workType: string | null | undefined): string {
  if (!workType) {
    return '📋';
  }

  switch (workType) {
    case '重大故障':
      return '🚨';
    case '修理票':
      return '🔧';
    case '作業票':
      return '⚙️';
    case '連絡票':
      return '📝';
    default:
      return '📋';
  }
}
