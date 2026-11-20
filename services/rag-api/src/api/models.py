"""API の Pydantic モデル。フロント `apps/assist-chat/types` と対で保守する。"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class YearRange(BaseModel):
    """年度範囲フィルター"""

    startYear: int
    endYear: int


class SearchFilters(BaseModel):
    """検索フィルター条件。equipment1s/2s/3s で設備階層（大 > 中 > 小）を絞る。"""

    yearRange: Optional[YearRange] = None
    categories: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    productionLines: Optional[List[str]] = None
    workTypes: Optional[List[str]] = None
    equipment1s: Optional[List[str]] = None
    equipment2s: Optional[List[str]] = None
    equipment3s: Optional[List[str]] = None


class SearchRequest(BaseModel):
    """検索リクエスト"""

    query: str = Field(..., min_length=1, max_length=200)
    filters: Optional[SearchFilters] = None
    k: int = Field(default=5, ge=1, le=10)


class SearchResult(BaseModel):
    """個別検索結果"""

    doc_id: str
    title: str
    score: float
    confidence: int = 0  # UI 表示用 (0-100%)
    snippet: str
    date: str
    machine: Optional[str] = None
    line: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    symptom: Optional[str] = None
    action_taken: Optional[str] = None


class SearchResponse(BaseModel):
    """検索レスポンス"""

    results: List[SearchResult]
    total: int
    processingTime: int
    # 利用ログで、閲覧とフィードバックをこの検索に結び付けるためのID
    searchId: Optional[str] = None


class DocumentDetail(BaseModel):
    """ドキュメント詳細"""

    doc_id: str
    title: str
    metadata: Dict[str, Any]
    full_text: str
    action_taken: Optional[str] = None


FeedbackMode = Literal["search", "chat"]


class FeedbackRequest(BaseModel):
    """役に立ったかどうかの評価。利用ログと合わせて集計する。"""

    doc_id: str = Field(..., min_length=1, max_length=64)
    rating: int = Field(..., ge=1, le=5)
    helpful: bool
    comment: Optional[str] = Field(default=None, max_length=2000)
    query: Optional[str] = Field(
        default=None,
        max_length=500,
        description="ユーザーが入力した検索/質問クエリ",
    )
    mode: FeedbackMode = Field(
        default="search",
        description="どのモードから送信されたか（search / chat）",
    )
    search_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="どの検索の結果に対する評価か（検索ログの search_id）",
    )
    rank: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="その検索での表示順位（1始まり）",
    )


class FeedbackResponse(BaseModel):
    """フィードバックレスポンス"""

    success: bool
    message: str
    saved_at: datetime = Field(default_factory=datetime.utcnow)


class HierarchyNode(BaseModel):
    """階層ツリーのノード"""

    id: str
    label: str
    children: List["HierarchyNode"] = []


class FilterMetadata(BaseModel):
    """フィルターパネル用メタデータ（利用可能値一覧）。"""

    categories: List[str]
    productionLines: List[str]
    workTypes: List[str]
    equipment1s: List[str]
    equipment2s: List[str]
    equipment3s: List[str]
    yearRange: Dict[str, int]
    totalDocuments: int
    hierarchy: Optional[List[HierarchyNode]] = None


ChatRole = Literal["user", "assistant"]


class ChatMessage(BaseModel):
    """会話履歴の 1 メッセージ"""

    role: ChatRole
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    """AI モードのチャットリクエスト。

    `messages` は直近の user 発言を除いた会話履歴、`query` に直近質問を入れる。
    サーバーはステートレスで、履歴管理はフロント側の責務。
    """

    query: str = Field(..., min_length=1, max_length=500)
    messages: List[ChatMessage] = Field(default_factory=list, max_length=20)
    filters: Optional[SearchFilters] = None
    k: int = Field(default=5, ge=1, le=10)
