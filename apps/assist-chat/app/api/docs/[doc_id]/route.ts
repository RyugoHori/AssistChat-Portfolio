/**
 * ドキュメント詳細APIルート
 */

import { NextRequest, NextResponse } from 'next/server';
import { ragClient } from '@/lib/api/rag-client';

export async function GET(
  request: NextRequest,
  { params }: { params: { doc_id: string } }
) {
  try {
    const { doc_id } = params;
    const document = await ragClient.getDocument(doc_id);

    if (!document) {
      return NextResponse.json(
        { error: 'ドキュメントが見つかりませんでした' },
        { status: 404 }
      );
    }

    return NextResponse.json(document);
  } catch (error) {
    console.error(`[API /api/docs/${params.doc_id}] エラー:`, error);
    return NextResponse.json(
      { error: 'ドキュメントの取得に失敗しました' },
      { status: 500 }
    );
  }
}