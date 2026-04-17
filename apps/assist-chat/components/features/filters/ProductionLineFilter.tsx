/**
 * Production line filter with search
 */

'use client';

import { useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';

interface ProductionLineFilterProps {
  selectedLines: string[];
  availableLines: string[];
  onChange: (lines: string[]) => void;
}

export function ProductionLineFilter({
  selectedLines,
  availableLines,
  onChange,
}: ProductionLineFilterProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredLines = availableLines.filter((line) =>
    line.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleToggle = (line: string) => {
    if (selectedLines.includes(line)) {
      onChange(selectedLines.filter((l) => l !== line));
    } else {
      onChange([...selectedLines, line]);
    }
  };

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">生産ライン</Label>
      
      <div className="relative">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          type="text"
          placeholder="ライン検索..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-8 h-9 text-sm"
        />
      </div>

      <div className="max-h-48 overflow-y-auto space-y-2 pr-2">
        {filteredLines.length === 0 ? (
          <p className="text-xs text-slate-500 py-2">該当するラインが見つかりません</p>
        ) : (
          filteredLines.map((line) => (
            <div key={line} className="flex items-center space-x-2">
              <Checkbox
                id={`line-${line}`}
                checked={selectedLines.includes(line)}
                onCheckedChange={() => handleToggle(line)}
              />
              <Label
                htmlFor={`line-${line}`}
                className="text-sm cursor-pointer"
              >
                {line}
              </Label>
            </div>
          ))
        )}
      </div>
      
      {selectedLines.length > 0 && (
        <p className="text-xs text-slate-500">
          {selectedLines.length}件選択中
        </p>
      )}
    </div>
  );
}