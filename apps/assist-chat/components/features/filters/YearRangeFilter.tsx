/**
 * Year range filter with dropdowns
 */

'use client';

import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface YearRangeFilterProps {
  yearRange?: { startYear: number; endYear: number };
  availableYearRange: { startYear: number; endYear: number };
  onChange: (yearRange: { startYear: number; endYear: number } | undefined) => void;
}

export function YearRangeFilter({
  yearRange,
  availableYearRange,
  onChange,
}: YearRangeFilterProps) {
  const years = Array.from(
    { length: availableYearRange.endYear - availableYearRange.startYear + 1 },
    (_, i) => availableYearRange.startYear + i
  );

  const handleStartYearChange = (value: string) => {
    const startYear = parseInt(value);
    const endYear = yearRange?.endYear || availableYearRange.endYear;
    onChange({ startYear, endYear: Math.max(startYear, endYear) });
  };

  const handleEndYearChange = (value: string) => {
    const endYear = parseInt(value);
    const startYear = yearRange?.startYear || availableYearRange.startYear;
    onChange({ startYear: Math.min(startYear, endYear), endYear });
  };

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">年度範囲</Label>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <Select
            value={yearRange?.startYear?.toString() || availableYearRange.startYear.toString()}
            onValueChange={handleStartYearChange}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {years.map((year) => (
                <SelectItem key={year} value={year.toString()}>
                  {year}年
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Select
            value={yearRange?.endYear?.toString() || availableYearRange.endYear.toString()}
            onValueChange={handleEndYearChange}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {years.map((year) => (
                <SelectItem key={year} value={year.toString()}>
                  {year}年
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}