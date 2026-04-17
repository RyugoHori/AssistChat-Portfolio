/**
 * 検索APIルート - FastAPIバックエンドへのプロキシ
 */

import { NextRequest, NextResponse } from 'next/server';
import { ragClient } from '@/lib/api/rag-client';
import { SearchRequest } from '@/types';

export async function POST(request: NextRequest) {
  try {
    const searchRequest: SearchRequest = await request.json();
    const response = await ragClient.search(searchRequest);
    return NextResponse.json(response);
  } catch (error) {
    console.error('[API /api/search] エラー:', error);
    return NextResponse.json(
      { error: '検索リクエストに失敗しました' },
      { status: 500 }
    );
  }
}