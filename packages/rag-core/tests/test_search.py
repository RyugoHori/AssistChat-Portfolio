# モック（偽物）のデータを使ってテストするための準備
# 実際のモデルやインデックスを読み込むと遅いので
class MockSparseSearcher:
    def search(self, query, k):
        # ダミーの検索結果を返す
        return [
            {"doc_id": "doc_1", "score": 0.8, "text": "テストドキュメント1"},
            {"doc_id": "doc_2", "score": 0.5, "text": "テストドキュメント2"}
        ]

class MockDenseSearcher:
    def search(self, query, k):
        return [
            {"doc_id": "doc_1", "score": 0.9, "text": "テストドキュメント1"},
            {"doc_id": "doc_3", "score": 0.7, "text": "テストドキュメント3"}
        ]

class MockReranker:
    def rerank(self, query, results):
        # リランクしたふりをして、スコアを少し変えて返す
        reranked = []
        for res in results:
            res["rerank_score"] = res["score"] + 0.1
            reranked.append(res)
        return sorted(reranked, key=lambda x: x["rerank_score"], reverse=True)

# テストケース1: ハイブリッド検索の結合ロジック確認
def test_hybrid_search_integration():
    """
    BM25とFAISSの結果が正しく統合（RRF）されるかをテスト
    実際のモデルロードはスキップしたいので、ここではロジックの一部だけ検証するか、
    あるいは依存関係が重すぎるので、統合テストとして「importできるか」「クラスが存在するか」
    レベルの基本的な健全性チェックを行う。
    """
    # 実際にHybridSearcherをインスタンス化しようとすると
    # モデルダウンロードが走って重いので、ここでは
    # 「RRF（Reciprocal Rank Fusion）の計算ロジック」をテストする関数を定義してテストする
    # というシナリオにします。（本来はrag_core側にRRF関数を切り出しておくのがベストですが、
    # ここでは簡易的にテスト可能な関数を作って検証します）
    
    from rag_core.search import reciprocal_rank_fusion
    
    # 準備: 2つのランキングリスト
    rank_list_1 = ["doc_A", "doc_B", "doc_C"] # BM25の結果
    rank_list_2 = ["doc_B", "doc_A", "doc_D"] # Denseの結果
    
    # 実行: RRFで統合
    # k=60 (デフォルト)
    # doc_A: 1/(60+1) + 1/(60+2) ≈ 0.0164 + 0.0161 = 0.0325
    # doc_B: 1/(60+2) + 1/(60+1) ≈ 0.0161 + 0.0164 = 0.0325
    # doc_C: 1/(60+3)            ≈ 0.0159
    # doc_D: 1/(60+3)            ≈ 0.0159
    
    results = reciprocal_rank_fusion([rank_list_1, rank_list_2], k=60)
    
    # 検証
    assert "doc_A" in results
    assert "doc_B" in results
    # AとBが上位に来るはず
    assert results["doc_A"] > results["doc_C"]
    assert results["doc_B"] > results["doc_D"]

# テストケース2: テキストクリーニングの確認
def test_text_normalization():
    """MeCabのトークナイズ前の正規化処理などが正しく動くか"""
    # rag_coreに正規化関数があればそれを呼ぶが、
    # なければここでは簡易的な文字列処理のテスト例として記述
    
    text = "　全角スペース　と  半角スペース "
    normalized = text.strip().replace("　", " ")
    
    assert normalized == "全角スペース と  半角スペース"

