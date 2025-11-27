/**
 * フィルターメタデータAPIルート
 */

import { NextResponse } from 'next/server';
import { ragClient } from '@/lib/api/rag-client';

export async function GET() {
  try {
    const metadata = await ragClient.getFilterMetadata();
    return NextResponse.json(metadata);
  } catch (error) {
    console.error('[API /api/search/metadata] エラー:', error);
    return NextResponse.json(
      { error: 'メタデータの取得に失敗しました' },
      { status: 500 }
    );
  }
}