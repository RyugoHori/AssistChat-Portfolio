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
  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
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
          value={value} // propsから直接値を使用
          onChange={(e) => onChange(e.target.value)} // propsから直接onChangeを呼び出し
          onKeyPress={handleKeyPress}
          placeholder={placeholder}
          disabled={isLoading}
          className="pl-10 pr-24 sm:pr-28 h-12 text-base sm:text-base" // モバイルではボタンが少し小さめになるように調整
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
