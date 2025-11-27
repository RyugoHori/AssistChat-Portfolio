/**
 * 設備3フィルター（小分類）
 * 
 * 例: R側No1／2孔明制御盤, No1ﾌﾟﾘﾝﾄ機制御盤, 素板C／V など
 */

'use client';

import { useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';

interface Equipment3FilterProps {
  selectedEquipment3s: string[];
  availableEquipment3s: string[];
  onChange: (equipment3s: string[]) => void;
}

export function Equipment3Filter({
  selectedEquipment3s,
  availableEquipment3s,
  onChange,
}: Equipment3FilterProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredEquipment3s = availableEquipment3s.filter((equipment3) =>
    equipment3.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleToggle = (equipment3: string) => {
    if (selectedEquipment3s.includes(equipment3)) {
      onChange(selectedEquipment3s.filter((e3) => e3 !== equipment3));
    } else {
      onChange([...selectedEquipment3s, equipment3]);
    }
  };

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">設備3</Label>
      
      <div className="relative">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          type="text"
          placeholder="設備3を検索..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-8 h-9 text-sm"
        />
      </div>

      <div className="max-h-48 overflow-y-auto space-y-2 pr-2">
        {filteredEquipment3s.length === 0 ? (
          <p className="text-xs text-slate-500 py-2">該当する設備3が見つかりません</p>
        ) : (
          filteredEquipment3s.map((equipment3) => (
            <div key={equipment3} className="flex items-center space-x-2">
              <Checkbox
                id={`equipment3-${equipment3}`}
                checked={selectedEquipment3s.includes(equipment3)}
                onCheckedChange={() => handleToggle(equipment3)}
              />
              <Label
                htmlFor={`equipment3-${equipment3}`}
                className="text-sm cursor-pointer hover:text-slate-900"
              >
                {equipment3}
              </Label>
            </div>
          ))
        )}
      </div>
      
      {selectedEquipment3s.length > 0 && (
        <p className="text-xs text-slate-500">
          {selectedEquipment3s.length}件選択中
        </p>
      )}
    </div>
  );
}


