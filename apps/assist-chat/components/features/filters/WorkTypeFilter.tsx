/**
 * 故障分類フィルター
 * 
 * 記録の種類を選択（重大故障/修理票/作業票/連絡票）
 */

'use client';

import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { getWorkTypeColor, getWorkTypeIcon } from '@/lib/utils/category';

interface WorkTypeFilterProps {
  selectedWorkTypes: string[];
  availableWorkTypes: string[];
  onChange: (workTypes: string[]) => void;
}

export function WorkTypeFilter({
  selectedWorkTypes,
  availableWorkTypes,
  onChange,
}: WorkTypeFilterProps) {
  const handleToggle = (workType: string) => {
    if (selectedWorkTypes.includes(workType)) {
      onChange(selectedWorkTypes.filter((wt) => wt !== workType));
    } else {
      onChange([...selectedWorkTypes, workType]);
    }
  };

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">故障分類</Label>
      <div className="space-y-2">
        {availableWorkTypes.map((workType) => (
          <div key={workType} className="flex items-center space-x-2">
            <Checkbox
              id={`workType-${workType}`}
              checked={selectedWorkTypes.includes(workType)}
              onCheckedChange={() => handleToggle(workType)}
            />
            <Label
              htmlFor={`workType-${workType}`}
              className="text-sm cursor-pointer flex items-center gap-2"
            >
              <span className="text-base">{getWorkTypeIcon(workType)}</span>
              <span
                className={cn(
                  'px-2 py-0.5 rounded text-xs',
                  getWorkTypeColor(workType)
                )}
              >
                {workType}
              </span>
            </Label>
          </div>
        ))}
      </div>
    </div>
  );
}