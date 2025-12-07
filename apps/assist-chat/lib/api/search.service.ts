// 検索サービス
// ragClientをラップしてる。将来的にキャッシュとか追加するかも

import { SearchRequest, SearchResponse, FilterMetadata } from '@/types';
import { ragClient } from './rag-client';

export class SearchService {
  async search(request: SearchRequest): Promise<SearchResponse> {
    return ragClient.search(request);
  }

  async getFilterMetadata(): Promise<FilterMetadata> {
    return ragClient.getFilterMetadata();
  }
}

export const searchService = new SearchService();
