/**
 * フィルターパネル - 検索条件の詳細絞り込み
 * 
 * フィルター階層:
 * 1. 年度範囲
 * 2. 作業種別（機械/電気）
 * 3. 故障分類（重大故障/修理票/作業票/連絡票）
 * 4. 工場
 * 5. 生産ライン (工場に依存)
 * 6. 設備階層（設備1 → 設備2 → 設備3） (ラインに依存)
 */

'use client';

import { useMemo } from 'react';
import { SearchFilters, FilterMetadata, HierarchyNode } from '@/types';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { CategoryFilter } from './CategoryFilter';
import { WorkTypeFilter } from './WorkTypeFilter';
import { YearRangeFilter } from './YearRangeFilter';
import { LocationFilter } from './LocationFilter';
import { ProductionLineFilter } from './ProductionLineFilter';
import { Equipment1Filter } from './Equipment1Filter';
import { Equipment2Filter } from './Equipment2Filter';
import { Equipment3Filter } from './Equipment3Filter';
import { RotateCcw } from 'lucide-react';

interface FilterPanelProps {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
  metadata: FilterMetadata;
  onReset: () => void;
}

export function FilterPanel({ filters, onChange, metadata, onReset }: FilterPanelProps) {
  const hasActiveFilters =
    filters.yearRange !== undefined ||
    (filters.categories && filters.categories.length > 0) ||
    (filters.workTypes && filters.workTypes.length > 0) ||
    (filters.locations && filters.locations.length > 0) ||
    (filters.productionLines && filters.productionLines.length > 0) ||
    (filters.equipment1s && filters.equipment1s.length > 0) ||
    (filters.equipment2s && filters.equipment2s.length > 0) ||
    (filters.equipment3s && filters.equipment3s.length > 0);

  const handleFilterChange = <K extends keyof SearchFilters>(
    key: K,
    value: SearchFilters[K]
  ) => {
    // 親フィルターが変更された場合、子フィルターをリセットするロジックを入れると親切だが、
    // ユーザーが意図せず選択解除されるのを嫌う場合もあるため、今回はそのままにする。
    // ただし、無効になった選択肢が残ると変なので、理想はリセット。
    
    let newFilters = { ...filters, [key]: value };

    // カスケードリセットロジック (簡易版)
    if (key === 'locations') {
      newFilters.productionLines = [];
      newFilters.equipment1s = [];
      newFilters.equipment2s = [];
      newFilters.equipment3s = [];
    } else if (key === 'productionLines') {
      newFilters.equipment1s = [];
      newFilters.equipment2s = [];
      newFilters.equipment3s = [];
    } else if (key === 'equipment1s') {
      newFilters.equipment2s = [];
      newFilters.equipment3s = [];
    } else if (key === 'equipment2s') {
      newFilters.equipment3s = [];
    }

    onChange(newFilters);
  };

  // ==================== カスケードロジック ====================

  // 1. 利用可能な工場（ルート）
  const availableLocations = useMemo(() => {
    if (!metadata.hierarchy) return [];
    return metadata.hierarchy.map(node => node.id).sort();
  }, [metadata.hierarchy]);

  // 2. 利用可能なライン（工場に依存）
  const availableLines = useMemo(() => {
    if (!metadata.hierarchy) return metadata.productionLines;
    
    const selectedLocs = filters.locations || [];
    let lines: Set<string> = new Set();

    metadata.hierarchy.forEach(locNode => {
      // ロケーションが選択されていない(全表示) または 選択されている場合
      if (selectedLocs.length === 0 || selectedLocs.includes(locNode.id)) {
        locNode.children.forEach(lineNode => lines.add(lineNode.id));
      }
    });

    return Array.from(lines).sort();
  }, [metadata.hierarchy, metadata.productionLines, filters.locations]);

  // 3. 利用可能な設備1（ラインに依存）
  const availableEquipment1s = useMemo(() => {
    if (!metadata.hierarchy) return metadata.equipment1s;

    const selectedLocs = filters.locations || [];
    const selectedLines = filters.productionLines || [];
    let eq1s: Set<string> = new Set();

    // ラインが選択されてない場合、全部の設備1を表示するとごちゃごちゃするかも
    // でも、カスケードルールに従って、選択された工場（または全部）の設備1を表示する
    // 多すぎるかもしれないけど、今のロジックのまま：現在の制約下で利用可能なものを全部表示

    metadata.hierarchy.forEach(locNode => {
      if (selectedLocs.length === 0 || selectedLocs.includes(locNode.id)) {
        locNode.children.forEach(lineNode => {
          if (selectedLines.length === 0 || selectedLines.includes(lineNode.id)) {
             lineNode.children.forEach(eq1Node => eq1s.add(eq1Node.id));
          }
        });
      }
    });

    return Array.from(eq1s).sort();
  }, [metadata.hierarchy, metadata.equipment1s, filters.locations, filters.productionLines]);

  // 4. 利用可能な設備2（設備1に依存）
  const availableEquipment2s = useMemo(() => {
    if (!metadata.hierarchy) return metadata.equipment2s;

    const selectedLocs = filters.locations || [];
    const selectedLines = filters.productionLines || [];
    const selectedEq1s = filters.equipment1s || [];
    let eq2s: Set<string> = new Set();

    // カスケードルール：設備1が選択されてる場合だけ設備2を表示？
    // それとも利用可能な設備1に属する設備2を表示？
    // 現在のロジック：利用可能な制約下の設備2を全部表示
    
    metadata.hierarchy.forEach(locNode => {
      if (selectedLocs.length === 0 || selectedLocs.includes(locNode.id)) {
        locNode.children.forEach(lineNode => {
          if (selectedLines.length === 0 || selectedLines.includes(lineNode.id)) {
             lineNode.children.forEach(eq1Node => {
               if (selectedEq1s.length === 0 || selectedEq1s.includes(eq1Node.id)) {
                 eq1Node.children.forEach(eq2Node => eq2s.add(eq2Node.id));
               }
             });
          }
        });
      }
    });

    return Array.from(eq2s).sort();
  }, [metadata.hierarchy, metadata.equipment2s, filters.locations, filters.productionLines, filters.equipment1s]);

  // 5. 利用可能な設備3
  const availableEquipment3s = useMemo(() => {
    if (!metadata.hierarchy) return metadata.equipment3s;

    const selectedLocs = filters.locations || [];
    const selectedLines = filters.productionLines || [];
    const selectedEq1s = filters.equipment1s || [];
    const selectedEq2s = filters.equipment2s || [];
    let eq3s: Set<string> = new Set();

    metadata.hierarchy.forEach(locNode => {
      if (selectedLocs.length === 0 || selectedLocs.includes(locNode.id)) {
        locNode.children.forEach(lineNode => {
          if (selectedLines.length === 0 || selectedLines.includes(lineNode.id)) {
             lineNode.children.forEach(eq1Node => {
               if (selectedEq1s.length === 0 || selectedEq1s.includes(eq1Node.id)) {
                 eq1Node.children.forEach(eq2Node => {
                   if (selectedEq2s.length === 0 || selectedEq2s.includes(eq2Node.id)) {
                      eq2Node.children.forEach(eq3Node => eq3s.add(eq3Node.id));
                   }
                 });
               }
             });
          }
        });
      }
    });

    return Array.from(eq3s).sort();
  }, [metadata.hierarchy, metadata.equipment3s, filters.locations, filters.productionLines, filters.equipment1s, filters.equipment2s]);


  return (
    <Card className="p-4">
      <div className="space-y-4">
        {/* ヘッダー */}
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-slate-900">フィルター</h3>
          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onReset}
              className="h-8 text-xs"
            >
              <RotateCcw className="h-3 w-3 mr-1" />
              リセット
            </Button>
          )}
        </div>

        <div className="space-y-4">
          {/* 年度範囲 */}
          <YearRangeFilter
            yearRange={filters.yearRange}
            availableYearRange={metadata.yearRange}
            onChange={(value) => handleFilterChange('yearRange', value)}
          />

          <Separator />

          {/* 作業種別（機械/電気） */}
          <CategoryFilter
            selectedCategories={filters.categories || []}
            availableCategories={metadata.categories}
            onChange={(value) => handleFilterChange('categories', value)}
          />

          {/* 故障分類 */}
          <WorkTypeFilter
            selectedWorkTypes={filters.workTypes || []}
            availableWorkTypes={metadata.workTypes}
            onChange={(value) => handleFilterChange('workTypes', value)}
          />

          <Separator />

          {/* 工場 */}
          {/* metadata.hierarchyがある場合のみ表示、空でも表示するかは要検討 */}
          {availableLocations.length > 0 && (
            <LocationFilter
              selectedLocations={filters.locations || []}
              availableLocations={availableLocations}
              onChange={(value) => handleFilterChange('locations', value)}
            />
          )}

          {/* 生産ライン */}
          <ProductionLineFilter
            selectedLines={filters.productionLines || []}
            availableLines={availableLines}
            onChange={(value) => handleFilterChange('productionLines', value)}
          />

          {/* 設備階層 */}
          <Equipment1Filter
            selectedEquipment1s={filters.equipment1s || []}
            availableEquipment1s={availableEquipment1s}
            onChange={(value) => handleFilterChange('equipment1s', value)}
          />

          <Equipment2Filter
            selectedEquipment2s={filters.equipment2s || []}
            availableEquipment2s={availableEquipment2s}
            onChange={(value) => handleFilterChange('equipment2s', value)}
          />

          <Equipment3Filter
            selectedEquipment3s={filters.equipment3s || []}
            availableEquipment3s={availableEquipment3s}
            onChange={(value) => handleFilterChange('equipment3s', value)}
          />
        </div>
      </div>
    </Card>
  );
}
