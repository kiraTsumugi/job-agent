"""RAG 模块单元测试."""

import pytest

from app.rag.chunker import FixedChunker, SemanticChunker, RecursiveChunker


class TestChunkers:
    SAMPLE_TEXT = (
        "## 项目经历\n\n"
        "### AI Agent 求职助手\n"
        "基于 LangGraph 和 FastAPI 搭建的多轮对话 Agent，"
        "集成了 RAG 混合检索和简历改写功能。"
        "使用 bge-m3 做嵌入，Qdrant 做向量存储。\n\n"
        "### 电商推荐系统\n"
        "基于协同过滤和深度学习的推荐系统，"
        "DAU 10 万+，点击率提升 15%。\n\n"
        "## 技能\n"
        "Python, FastAPI, LangGraph, Qdrant, Docker"
    )

    def test_fixed_chunker(self):
        chunker = FixedChunker(chunk_size=100, overlap=20)
        chunks = chunker.chunk(self.SAMPLE_TEXT)
        assert len(chunks) > 1
        assert all("text" in c for c in chunks)
        assert all("id" in c for c in chunks)

    def test_semantic_chunker(self):
        chunker = SemanticChunker(min_chunk_size=50, max_chunk_size=500)
        chunks = chunker.chunk(self.SAMPLE_TEXT)
        assert len(chunks) >= 1
        assert all(c["text"] for c in chunks)

    def test_recursive_chunker(self):
        chunker = RecursiveChunker(chunk_size=200, overlap=30)
        chunks = chunker.chunk(self.SAMPLE_TEXT)
        assert len(chunks) >= 1
        assert all("text" in c for c in chunks)

    def test_chunk_id_uniqueness(self):
        for chunker_cls in [FixedChunker, RecursiveChunker]:
            chunker = chunker_cls(chunk_size=200, overlap=30)
            chunks = chunker.chunk(self.SAMPLE_TEXT)
            ids = [c["id"] for c in chunks]
            assert len(ids) == len(set(ids)), f"{chunker_cls.__name__}: duplicate IDs"


class TestRRF:
    from app.rag.retriever import _reciprocal_rank_fusion_many, reciprocal_rank_fusion
    _reciprocal_rank_fusion_many = staticmethod(_reciprocal_rank_fusion_many)
    reciprocal_rank_fusion = staticmethod(reciprocal_rank_fusion)

    def test_rrf_basic(self):
        a = [("doc1", 0.9), ("doc2", 0.7), ("doc3", 0.5)]
        b = [("doc2", 0.8), ("doc3", 0.6), ("doc1", 0.1)]
        fused = self.reciprocal_rank_fusion(a, b)
        assert len(fused) == 3
        # doc2 should rank high since it appears top in both
        assert fused[0][0] == "doc2"

    def test_rrf_many(self):
        fused = self._reciprocal_rank_fusion_many([
            [("doc1", 0.9), ("doc2", 0.7)],
            [("doc2", 0.8), ("doc3", 0.6)],
            [("doc2", 0.5), ("doc1", 0.4)],
        ])
        assert fused[0][0] == "doc2"


class TestTokenizer:
    from app.rag.retriever import _tokenize
    _tokenize = staticmethod(_tokenize)

    def test_tokenize_keeps_english_terms_and_chinese_bigrams(self):
        tokens = self._tokenize("FastAPI + LangGraph，向量数据库 RAG")
        assert "fastapi" in tokens
        assert "langgraph" in tokens
        assert "rag" in tokens
        assert "向量" in tokens
        assert "数据" in tokens


class TestLexicalRanking:
    from app.rag.retriever import _Document, _bm25_rank, _tokenize
    _bm25_rank = staticmethod(_bm25_rank)
    _tokenize = staticmethod(_tokenize)

    def test_bm25_ranks_matching_jd_first(self):
        docs = [
            self._Document(
                id="agent",
                text="AI Agent 实习生，需要 FastAPI、LangGraph、RAG 和向量数据库经验",
                metadata={},
                tokens=self._tokenize("AI Agent 实习生，需要 FastAPI、LangGraph、RAG 和向量数据库经验"),
            ),
            self._Document(
                id="frontend",
                text="前端实习生，需要 React、CSS 和页面还原经验",
                metadata={},
                tokens=self._tokenize("前端实习生，需要 React、CSS 和页面还原经验"),
            ),
        ]

        ranked = self._bm25_rank(self._tokenize("LangGraph FastAPI RAG"), docs)
        assert ranked[0][0] == "agent"


class TestHashEmbedding:
    from app.rag.embedder import _hash_embedding
    _hash_embedding = staticmethod(_hash_embedding)

    def test_hash_embedding_is_deterministic_and_normalized(self):
        first = self._hash_embedding("LangGraph FastAPI RAG", 32)
        second = self._hash_embedding("LangGraph FastAPI RAG", 32)
        assert first == second
        assert len(first) == 32
        norm = sum(value * value for value in first) ** 0.5
        assert norm == pytest.approx(1.0)
