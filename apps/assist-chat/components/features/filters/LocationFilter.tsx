/**
 * Location (Factory) filter with search
 */

'use client';

import { useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';

interface LocationFilterProps {
  selectedLocations: string[];
  availableLocations: string[];
  onChange: (locations: string[]) => void;
}

export function LocationFilter({
  selectedLocations,
  availableLocations,
  onChange,
}: LocationFilterProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredLocations = availableLocations.filter((loc) =>
    loc.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleToggle = (loc: string) => {
    if (selectedLocations.includes(loc)) {
      onChange(selectedLocations.filter((l) => l !== loc));
    } else {
      onChange([...selectedLocations, loc]);
    }
  };

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">工場</Label>
      
      <div className="relative">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          type="text"
          placeholder="工場検索..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-8 h-9 text-sm"
        />
      </div>

      <div className="max-h-32 overflow-y-auto space-y-2 pr-2">
        {filteredLocations.length === 0 ? (
          <p className="text-xs text-slate-500 py-2">該当する工場が見つかりません</p>
        ) : (
          filteredLocations.map((loc) => (
            <div key={loc} className="flex items-center space-x-2">
              <Checkbox
                id={`loc-${loc}`}
                checked={selectedLocations.includes(loc)}
                onCheckedChange={() => handleToggle(loc)}
              />
              <Label
                htmlFor={`loc-${loc}`}
                className="text-sm cursor-pointer"
              >
                {loc}
              </Label>
            </div>
          ))
        )}
      </div>
      
      {selectedLocations.length > 0 && (
        <p className="text-xs text-slate-500">
          {selectedLocations.length}件選択中
        </p>
      )}
    </div>
  );
}

