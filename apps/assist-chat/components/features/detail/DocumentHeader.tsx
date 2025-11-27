// ドキュメント詳細のヘッダー

'use client';

import { DocumentDetail } from '@/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';

interface DocumentHeaderProps {
  document: DocumentDetail;
  onClose: () => void;
}

export function DocumentHeader({ document, onClose }: DocumentHeaderProps) {
  return (
    <div className="space-y-2 p-4 sm:p-6 border-b border-slate-200">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1 flex-1 min-w-0">
          <h1 className="text-lg sm:text-xl font-bold text-slate-900 leading-tight break-words">
            {document.title}
          </h1>
          <Badge variant="outline" className="text-xs font-mono">
            {document.doc_id}
          </Badge>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} className="text-slate-500 flex-shrink-0">
          <X className="h-5 w-5" />
        </Button>
      </div>
      
      {document.content && (
        <p className="text-xs sm:text-sm text-slate-600 pt-2 break-words">
          {document.content}
        </p>
      )}
    </div>
  );
}
