"""
APIリクエスト/レスポンス検証用のPydanticモデル
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class YearRange(BaseModel):
    """年度範囲フィルター"""
    startYear: int
    endYear: int

class SearchFilters(BaseModel):
    """
    検索フィルター条件
    
    フィルター階層:
    - categories: 作業種別（機械/電気）
    - workTypes: 故障分類（重大故障/修理票/作業票/連絡票）
    - productionLines: 生産ライン
    - equipment1s: 設備1（大分類）
    - equipment2s: 設備2（中分類）
    - equipment3s: 設備3（小分類）
    """
    yearRange: Optional[YearRange] = None
    categories: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    productionLines: Optional[List[str]] = None
    workTypes: Optional[List[str]] = None
    equipment1s: Optional[List[str]] = None
    equipment2s: Optional[List[str]] = None
    equipment3s: Optional[List[str]] = None
    severity: Optional[List[str]] = None
    keywords: Optional[List[str]] = None

class SearchRequest(BaseModel):
    """検索リクエストモデル"""
    query: str = Field(..., min_length=1, max_length=200)
    filters: Optional[SearchFilters] = None
    k: int = Field(default=5, ge=1, le=20)

class SearchResult(BaseModel):
    """個別検索結果モデル"""
    doc_id: str
    title: str
    summary: str
    score: float
    confidence: int = 0  # UI表示用 (0-100%)
    snippet: str
    date: str
    machine: Optional[str] = None
    line: Optional[str] = None
    category: Optional[str] = None
    match_fields: Dict[str, float] = {}
    location: Optional[str] = None
    symptom: Optional[str] = None
    action_taken: Optional[str] = None
    parts_replaced: Optional[str] = None
    operator: Optional[str] = None

class SearchResponse(BaseModel):
    """検索レスポンスモデル"""
    results: List[SearchResult]
    total: int
    processingTime: int

class DocumentChunk(BaseModel):
    """ドキュメントチャンクモデル"""
    chunk_id: str
    text: str
    chunk_index: int
    source_doc_id: str

class DocumentDetail(BaseModel):
    """ドキュメント詳細モデル"""
    doc_id: str
    title: str
    content: str
    metadata: Dict[str, Any]
    full_text: str
    chunks: List[DocumentChunk]
    attachments: List[str] = []
    action_taken: Optional[str] = None
    parts_replaced: Optional[str] = None

class FeedbackRequest(BaseModel):
    """フィードバックリクエスト"""
    doc_id: str
    rating: int
    comment: Optional[str] = None
    helpful: bool

class HierarchyNode(BaseModel):
    """階層構造のノード"""
    id: str
    label: str
    children: List['HierarchyNode'] = []

class FilterMetadata(BaseModel):
    """
    フィルターメタデータモデル
    
    利用可能なフィルター値のリストを提供:
    - categories: 作業種別（機械/電気）
    - workTypes: 故障分類（重大故障/修理票/作業票/連絡票）
    - productionLines: 生産ライン一覧
    - equipment1s: 設備1一覧（大分類）
    - equipment2s: 設備2一覧（中分類）
    - equipment3s: 設備3一覧（小分類）
    """
    categories: List[str]
    productionLines: List[str]
    workTypes: List[str]
    equipment1s: List[str]
    equipment2s: List[str]
    equipment3s: List[str]
    yearRange: Dict[str, int]
    totalDocuments: int
    hierarchy: Optional[List[HierarchyNode]] = None

class HealthResponse(BaseModel):
    """ヘルスチェックレスポンス"""
    status: str
    timestamp: str
    index_loaded: bool
    model_loaded: bool
    vectors: int
