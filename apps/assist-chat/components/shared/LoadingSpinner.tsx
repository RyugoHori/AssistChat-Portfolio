/**
 * Loading spinner with optional message
 */

'use client';

import { cn } from '@/lib/utils';

interface LoadingSpinnerProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function LoadingSpinner({ 
  message, 
  size = 'md',
  className 
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'h-4 w-4 border-2',
    md: 'h-8 w-8 border-3',
    lg: 'h-12 w-12 border-4',
  };

  return (
    <div className={cn('flex flex-col items-center justify-center gap-3', className)}>
      <div
        className={cn(
          'animate-spin rounded-full border-blue-600 border-t-transparent',
          sizeClasses[size]
        )}
        role="status"
        aria-label="読み込み中"
      />
      {message && (
        <p className="text-sm text-slate-600">{message}</p>
      )}
    </div>
  );
}