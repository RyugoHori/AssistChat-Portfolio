/**
 * 設備2フィルター（中分類）
 * 
 * 例: 孔明設備, ﾌﾟﾘﾝﾄ設備, 切折設備, 洗浄設備 など
 */

'use client';

import { useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';

interface Equipment2FilterProps {
  selectedEquipment2s: string[];
  availableEquipment2s: string[];
  onChange: (equipment2s: string[]) => void;
}

export function Equipment2Filter({
  selectedEquipment2s,
  availableEquipment2s,
  onChange,
}: Equipment2FilterProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredEquipment2s = availableEquipment2s.filter((equipment2) =>
    equipment2.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleToggle = (equipment2: string) => {
    if (selectedEquipment2s.includes(equipment2)) {
      onChange(selectedEquipment2s.filter((e2) => e2 !== equipment2));
    } else {
      onChange([...selectedEquipment2s, equipment2]);
    }
  };

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">設備2</Label>
      
      <div className="relative">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          type="text"
          placeholder="設備2を検索..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-8 h-9 text-sm"
        />
      </div>

      <div className="max-h-48 overflow-y-auto space-y-2 pr-2">
        {filteredEquipment2s.length === 0 ? (
          <p className="text-xs text-slate-500 py-2">該当する設備2が見つかりません</p>
        ) : (
          filteredEquipment2s.map((equipment2) => (
            <div key={equipment2} className="flex items-center space-x-2">
              <Checkbox
                id={`equipment2-${equipment2}`}
                checked={selectedEquipment2s.includes(equipment2)}
                onCheckedChange={() => handleToggle(equipment2)}
              />
              <Label
                htmlFor={`equipment2-${equipment2}`}
                className="text-sm cursor-pointer hover:text-slate-900"
              >
                {equipment2}
              </Label>
            </div>
          ))
        )}
      </div>
      
      {selectedEquipment2s.length > 0 && (
        <p className="text-xs text-slate-500">
          {selectedEquipment2s.length}件選択中
        </p>
      )}
    </div>
  );
}


