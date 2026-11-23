/**
 * SearchInput のキーボード操作
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { SearchInput } from '@/components/features/search/SearchInput';

describe('SearchInput', () => {
  it('変換中の Enter では検索しない', () => {
    const onSearch = vi.fn();
    render(
      <SearchInput value="あ" onChange={() => {}} onSearch={onSearch} />,
    );

    fireEvent.keyDown(screen.getByPlaceholderText('故障内容や設備名で検索...'), {
      key: 'Enter',
      isComposing: true,
    });

    expect(onSearch).not.toHaveBeenCalled();
  });
});
