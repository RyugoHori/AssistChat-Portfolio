'use client';

import { Search, X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { SEARCH_CONFIG } from '@/lib/constants';

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
}

export function SearchInput({
  value,
  onChange,
  onSearch,
  isLoading = false,
  placeholder = '故障内容や設備名で検索...',
  className,
}: SearchInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && (e.nativeEvent.isComposing || e.keyCode === 229)) return;
    if (e.key === 'Enter' && !isLoading) {
      e.preventDefault(); // フォーム送信を防ぐ
      onSearch();
    }
  };

  const handleClear = () => {
    onChange('');
  };

  return (
    <div className={cn('relative w-full', className)}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isLoading}
          className="pl-10 pr-24 sm:pr-28 h-12 text-base"
          maxLength={SEARCH_CONFIG.MAX_QUERY_LENGTH}
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {value && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={handleClear}
              className="h-8 w-8"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
          <Button
            type="button"
            onClick={onSearch}
            disabled={isLoading || !value.trim()}
          >
            検索
          </Button>
        </div>
      </div>
    </div>
  );
}
