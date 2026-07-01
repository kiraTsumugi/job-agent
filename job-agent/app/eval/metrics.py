"""评测指标计算：命中率、Recall@K、MRR."""

from __future__ import annotations


def recall_at_k(relevant: set[str], retrieved: list[str], k: int = 5) -> float:
    """Retrieval Recall@K."""
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def mrr(relevant: set[str], retrieved: list[str]) -> float:
    """Mean Reciprocal Rank."""
    for i, doc_id in enumerate(retrieved):
        if doc_id in relevant:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(relevant_scores: dict[str, float], retrieved: list[str], k: int = 5) -> float:
    """Normalized Discounted Cumulative Gain @K (简化版)."""
    import math

    dcg = 0.0
    for i, doc_id in enumerate(retrieved[:k]):
        gain = relevant_scores.get(doc_id, 0)
        dcg += gain / math.log2(i + 2)  # i+2 因为 log(1)=0

    ideal = sorted(relevant_scores.values(), reverse=True)
    idcg = 0.0
    for i, gain in enumerate(ideal[:k]):
        idcg += gain / math.log2(i + 2)

    return dcg / idcg if idcg > 0 else 0.0
