'use client';

import { useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getCategoryColor } from '@/lib/utils/category'; // 今はgetCategoryColorを再利用してる

interface Equipment1FilterProps {
  selectedEquipment1s: string[];
  availableEquipment1s: string[];
  onChange: (equipment1s: string[]) => void;
}

export function Equipment1Filter({
  selectedEquipment1s,
  availableEquipment1s,
  onChange,
}: Equipment1FilterProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredEquipment1s = availableEquipment1s.filter((equipment1) =>
    equipment1.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleToggle = (equipment1: string) => {
    if (selectedEquipment1s.includes(equipment1)) {
      onChange(selectedEquipment1s.filter((e1) => e1 !== equipment1));
    } else {
      onChange([...selectedEquipment1s, equipment1]);
    }
  };

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">設備1</Label>
      
      <div className="relative">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          type="text"
          placeholder="設備1を検索..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-8 h-9 text-sm"
        />
      </div>

      <div className="max-h-48 overflow-y-auto space-y-2 pr-2">
        {filteredEquipment1s.length === 0 ? (
          <p className="text-xs text-slate-500 py-2">該当する設備1が見つかりません</p>
        ) : (
          filteredEquipment1s.map((equipment1) => (
            <div key={equipment1} className="flex items-center space-x-2">
              <Checkbox
                id={`equipment1-${equipment1}`}
                checked={selectedEquipment1s.includes(equipment1)}
                onCheckedChange={() => handleToggle(equipment1)}
              />
              <Label
                htmlFor={`equipment1-${equipment1}`}
                className="text-sm cursor-pointer flex items-center gap-2"
              >
                <span
                  className={cn(
                    'px-2 py-0.5 rounded text-xs',
                    getCategoryColor(equipment1) // 今はgetCategoryColorを使用
                  )}
                >
                  {equipment1}
                </span>
              </Label>
            </div>
          ))
        )}
      </div>
      
      {selectedEquipment1s.length > 0 && (
        <p className="text-xs text-slate-500">
          {selectedEquipment1s.length}件選択中
        </p>
      )}
    </div>
  );
}