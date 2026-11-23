/**
 * 作業種別フィルター
 * 
 * 作業の種類を選択（機械/電気）
 */

'use client';

import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';

import { cn } from '@/lib/utils';
import { getCategoryColor } from '@/lib/utils/category';

interface CategoryFilterProps {
  selectedCategories: string[];
  availableCategories: string[];
  onChange: (categories: string[]) => void;
}

export function CategoryFilter({
  selectedCategories,
  availableCategories,
  onChange,
}: CategoryFilterProps) {
  const handleToggle = (category: string) => {
    if (selectedCategories.includes(category)) {
      onChange(selectedCategories.filter((c) => c !== category));
    } else {
      onChange([...selectedCategories, category]);
    }
  };

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">作業種別</Label>
      <div className="space-y-2">
        {availableCategories.map((category) => (
          <div key={category} className="flex items-center space-x-2">
            <Checkbox
              id={`category-${category}`}
              checked={selectedCategories.includes(category)}
              onCheckedChange={() => handleToggle(category)}
            />
            <Label
              htmlFor={`category-${category}`}
              className="text-sm cursor-pointer flex items-center gap-2"
            >
              <span className={cn('px-2 py-0.5 rounded text-xs', getCategoryColor(category))}>
                {category}
              </span>
            </Label>
          </div>
        ))}
      </div>
    </div>
  );
}