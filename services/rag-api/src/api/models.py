"""
API リクエスト / レスポンス検証用の Pydantic モデル

フロントエンド（TypeScript `apps/assist-chat/types`）と対になる型定義。
変更時は両者の整合性を必ず保つこと。
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ==================== 共通 ====================

class YearRange(BaseModel):
    """年度範囲フィルター"""
    startYear: int
    endYear: int


class SearchFilters(BaseModel):
    """
    検索フィルター条件

    フィルター階層:
    - categories: 作業種別（機械 / 電気）
    - workTypes: 故障分類（重大故障 / 修理票 / 作業票 / 連絡票）
    - productionLines: 生産ライン
    - equipment1s / equipment2s / equipment3s: 設備階層（大 > 中 > 小）
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


# ==================== 検索（/api/search） ====================

class SearchRequest(BaseModel):
    """検索リクエスト"""
    query: str = Field(..., min_length=1, max_length=200)
    filters: Optional[SearchFilters] = None
    k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    """個別検索結果"""
    doc_id: str
    title: str
    summary: str
    score: float
    confidence: int = 0  # UI 表示用 (0-100%)
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
    """検索レスポンス"""
    results: List[SearchResult]
    total: int
    processingTime: int


# ==================== ドキュメント詳細（/api/docs/{doc_id}） ====================

class DocumentChunk(BaseModel):
    """ドキュメントチャンク（Embedding の最小単位）"""
    chunk_id: str
    text: str
    chunk_index: int
    source_doc_id: str


class DocumentDetail(BaseModel):
    """ドキュメント詳細"""
    doc_id: str
    title: str
    content: str
    metadata: Dict[str, Any]
    full_text: str
    chunks: List[DocumentChunk]
    attachments: List[str] = []
    action_taken: Optional[str] = None
    parts_replaced: Optional[str] = None


# ==================== フィードバック（/api/feedback） ====================

FeedbackMode = Literal["search", "chat"]


class FeedbackRequest(BaseModel):
    """
    フィードバックリクエスト

    現場の保全員が「この事例は役に立った/立たなかった」を評価することで、
    将来の Re-ranker ファインチューニング用の正解ペアを蓄積する。
    """

    doc_id: str = Field(..., min_length=1, max_length=64)
    rating: int = Field(..., ge=1, le=5)
    helpful: bool
    comment: Optional[str] = Field(default=None, max_length=2000)
    query: Optional[str] = Field(
        default=None,
        max_length=500,
        description="ユーザーが入力した検索/質問クエリ（将来のファインチューニング用）",
    )
    mode: FeedbackMode = Field(
        default="search",
        description="どのモードから送信されたか（search / chat）",
    )


class FeedbackResponse(BaseModel):
    """フィードバックレスポンス"""
    success: bool
    message: str
    saved_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== フィルターメタデータ（/api/search/metadata） ====================

class HierarchyNode(BaseModel):
    """階層ツリーのノード"""
    id: str
    label: str
    children: List["HierarchyNode"] = []


class FilterMetadata(BaseModel):
    """
    フィルターメタデータ

    フロントエンドのフィルターパネルで使用する利用可能値一覧。
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


# ==================== AI チャット（/api/chat） ====================

ChatRole = Literal["user", "assistant"]


class ChatMessage(BaseModel):
    """会話履歴の 1 メッセージ"""
    role: ChatRole
    content: str = Field(..., min_length=1, max_length=4000)


class ChatSource(BaseModel):
    """LLM 回答の引用元"""
    doc_id: str
    title: str
    score: float


class ChatRequest(BaseModel):
    """
    AI モードのチャットリクエスト

    `messages` は直近のユーザー発言を除いた会話履歴（user/assistant 交互）。
    直近のユーザー質問は `query` に入れて送信する。
    フロントエンドは履歴管理の責務を持ち、サーバーはステートレス。
    """
    query: str = Field(..., min_length=1, max_length=500)
    messages: List[ChatMessage] = Field(default_factory=list, max_length=20)
    filters: Optional[SearchFilters] = None
    k: int = Field(default=5, ge=1, le=20)
