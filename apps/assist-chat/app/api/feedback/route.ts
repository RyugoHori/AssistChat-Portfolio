/**
 * フィードバックAPIルート
 */

import { NextRequest, NextResponse } from 'next/server';
import { FeedbackRequest } from '@/types';

export async function POST(request: NextRequest) {
  try {
    const feedback: FeedbackRequest = await request.json();
    
    console.log('フィードバックを受信:', feedback);
    
    return NextResponse.json({
      success: true,
      message: 'フィードバックを受け付けました',
    });
  } catch (error) {
    console.error('[API /api/feedback] エラー:', error);
    return NextResponse.json(
      { error: 'フィードバックの保存に失敗しました' },
      { status: 500 }
    );
  }
}