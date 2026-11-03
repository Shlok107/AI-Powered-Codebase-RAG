from __future__ import annotations

import math
from collections.abc import Sequence


def ranking_metrics(retrieved: Sequence[str], relevant: set[str], k: int) -> dict[str, float]:
    """Compute standard retrieval metrics over unique ranked chunk keys.

    Precision uses the requested cutoff as denominator. Recall uses all known
    relevant keys. NDCG uses binary relevance and the ideal ranking at k.
    """
    if k <= 0:
        raise ValueError("k must be positive")
    # Duplicate retrievals are not additional relevant documents, but remain
    # in the ranked list as repeated misses so they cannot inflate precision.
    ranked = list(retrieved)[:k]
    seen: set[str] = set()
    hits = []
    for key in ranked:
        hits.append(1 if key in relevant and key not in seen else 0)
        seen.add(key)
    hit_count = sum(hits)
    reciprocal_rank = next((1.0 / rank for rank, hit in enumerate(hits, 1) if hit), 0.0)
    dcg = sum(hit / math.log2(rank + 1) for rank, hit in enumerate(hits, 1))
    ideal_count = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return {
        f"precision@{k}": hit_count / k,
        f"recall@{k}": hit_count / len(relevant) if relevant else 0.0,
        "mrr": reciprocal_rank,
        f"hit_rate@{k}": float(hit_count > 0),
        f"ndcg@{k}": dcg / idcg if idcg else 0.0,
    }


def ranking_metrics_at_cutoffs(retrieved: Sequence[str], relevant: set[str], cutoffs=(1, 3, 5)) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for cutoff in cutoffs:
        metrics.update(ranking_metrics(retrieved, relevant, cutoff))
    return metrics

