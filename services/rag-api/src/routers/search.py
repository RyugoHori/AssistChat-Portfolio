"""検索・詳細・フィルターメタデータのエンドポイント。"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from rag_core import calculate_display_score

from ..api.models import (
    DocumentDetail,
    FilterMetadata,
    HierarchyNode,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from ..deps import run_async_search

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_hierarchy(metadata: List[Dict[str, Any]]) -> List[HierarchyNode]:
    """メタデータから設備階層（工場 → ライン → 設備 1-3）を組み立てる。"""
    tree: Dict[str, Any] = {}

    for doc in metadata:
        meta = doc.get("metadata", {})
        loc = meta.get("location")
        line = meta.get("line")
        eq1 = meta.get("equipment1")
        eq2 = meta.get("equipment2")
        eq3 = meta.get("equipment3")

        if not all([loc, line]):
            continue

        tree.setdefault(loc, {}).setdefault(line, {})

        if eq1:
            tree[loc][line].setdefault(eq1, {})
            if eq2:
                tree[loc][line][eq1].setdefault(eq2, {})
                if eq3:
                    tree[loc][line][eq1][eq2][eq3] = True

    result = []
    for loc_name, lines in sorted(tree.items()):
        loc_node = HierarchyNode(id=loc_name, label=loc_name, children=[])
        for line_name, eq1s in sorted(lines.items()):
            line_node = HierarchyNode(id=line_name, label=line_name, children=[])
            for eq1_name, eq2s in sorted(eq1s.items()):
                eq1_node = HierarchyNode(id=eq1_name, label=eq1_name, children=[])
                for eq2_name, eq3s in sorted(eq2s.items()):
                    eq2_node = HierarchyNode(id=eq2_name, label=eq2_name, children=[])
                    for eq3_name in sorted(eq3s.keys()):
                        eq2_node.children.append(
                            HierarchyNode(id=eq3_name, label=eq3_name, children=[])
                        )
                    eq1_node.children.append(eq2_node)
                line_node.children.append(eq1_node)
            loc_node.children.append(line_node)
        result.append(loc_node)

    return result


def _get_filter_metadata(metadata: List[Dict[str, Any]]) -> Dict[str, Any]:
    """フィルターパネル用の利用可能値一覧を返す。"""
    if not metadata:
        return {
            "categories": [],
            "productionLines": [],
            "workTypes": [],
            "equipment1s": [],
            "equipment2s": [],
            "equipment3s": [],
            "yearRange": {"startYear": 2020, "endYear": 2024},
            "totalDocuments": 0,
            "hierarchy": [],
        }

    hierarchy = _build_hierarchy(metadata)

    categories, work_types, lines = set(), set(), set()
    equipment1s, equipment2s, equipment3s = set(), set(), set()
    years: List[int] = []

    for doc in metadata:
        meta = doc.get("metadata", {})
        if c := meta.get("category"):
            categories.add(c)
        if wt := meta.get("work_type"):
            work_types.add(wt)
        if ln := meta.get("line"):
            lines.add(ln)
        if eq1 := meta.get("equipment1"):
            equipment1s.add(eq1)
        if eq2 := meta.get("equipment2"):
            equipment2s.add(eq2)
        if eq3 := meta.get("equipment3"):
            equipment3s.add(eq3)
        date_str = meta.get("date", "")
        if date_str and len(date_str) >= 4:
            try:
                year = int(date_str[:4])
                if 2000 <= year <= 2100:
                    years.append(year)
            except (ValueError, TypeError):
                continue

    return {
        "categories": sorted(categories),
        "productionLines": sorted(lines),
        "workTypes": sorted(work_types),
        "equipment1s": sorted(equipment1s),
        "equipment2s": sorted(equipment2s),
        "equipment3s": sorted(equipment3s),
        "yearRange": {
            "startYear": min(years) if years else 2020,
            "endYear": max(years) if years else 2024,
        },
        "totalDocuments": len(metadata),
        "hierarchy": hierarchy,
    }


@router.post("/api/search", response_model=SearchResponse)
async def search_endpoint(req: SearchRequest, request: Request):
    """メインの検索エンドポイント。"""
    start_time = time.time()
    if not getattr(request.app.state, "searcher", None):
        raise HTTPException(status_code=503, detail="Search service not fully initialized.")

    try:
        filters_dict = req.filters.model_dump(exclude_none=True) if req.filters else None
        if filters_dict:
            logger.info("search filters: %s", filters_dict)

        search_results = await run_async_search(request, req.query, filters=filters_dict)

        results = []
        for res in search_results:
            meta = res.get("metadata", res)
            score = calculate_display_score(res)
            text = res.get("text", "")

            results.append(
                SearchResult(
                    doc_id=meta.get("doc_id", ""),
                    title=meta.get("title", "故障対応記録"),
                    summary=text[:150] + "..." if text else "",
                    score=score,
                    confidence=int(score * 100),
                    snippet=text[:200] + "..." if text else "",
                    date=meta.get("date", ""),
                    machine=meta.get("machine"),
                    line=meta.get("line"),
                    category=meta.get("category", "その他"),
                    match_fields={"text": score},
                    location=meta.get("location"),
                    symptom=meta.get("symptom"),
                    action_taken=meta.get("action_taken"),
                    parts_replaced=meta.get("parts_replaced"),
                    operator=meta.get("operator"),
                )
            )

        processing_time = int((time.time() - start_time) * 1000)
        logger.info(
            "search done: query=%r results=%d time=%dms",
            req.query[:30], len(results), processing_time,
        )
        return SearchResponse(results=results, total=len(results), processingTime=processing_time)

    except Exception as e:
        logger.error("search failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/search/metadata", response_model=FilterMetadata)
async def get_filter_metadata(request: Request):
    """フィルターパネル用メタデータを返す。"""
    metadata = getattr(request.app.state, "metadata", None)
    if not metadata:
        raise HTTPException(status_code=503, detail="Metadata not loaded")
    try:
        return FilterMetadata(**_get_filter_metadata(metadata))
    except Exception as e:
        logger.error("failed to build filter metadata: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/docs/{doc_id}", response_model=DocumentDetail)
async def get_document(doc_id: str, request: Request):
    """ドキュメント詳細を返す。"""
    metadata = getattr(request.app.state, "metadata", None)
    if not metadata:
        raise HTTPException(status_code=503, detail="Metadata service not initialized.")

    # 2 万件規模なら線形探索で十分。インデックス化のコストを避ける。
    doc = next(
        (
            m for m in metadata
            if m.get("metadata", {}).get("doc_id") == doc_id or m.get("doc_id") == doc_id
        ),
        None,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    meta = doc.get("metadata", doc)
    text = doc.get("text", "")
    return DocumentDetail(
        doc_id=doc_id,
        title=meta.get("title", "N/A"),
        content=text,
        metadata=doc,
        full_text=text,
        chunks=[{
            "chunk_id": f"{doc_id}_chunk_0",
            "text": text,
            "chunk_index": 0,
            "source_doc_id": doc_id,
        }],
        attachments=[],
        action_taken=meta.get("action_taken"),
        parts_replaced=meta.get("parts_replaced"),
    )
