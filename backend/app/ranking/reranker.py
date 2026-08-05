"""Cross-encoder reranker (optional, OFF by default on the micro tier).

Scores the top-K RRF candidates with an ONNX Int8-quantized cross-encoder
(e.g. a MiniLM cross-encoder) against the original query, then re-orders
the candidate list so the highest-scoring passages come first.

Per CLAUDE.md rule 6 this module enforces a hard latency budget (<200ms
p95) and logs a warning whenever a single rerank call exceeds it. It is a
pure passthrough when ``rerank_enabled`` is False or when the model files
are absent, so enabling it never risks breaking the serving path.

Loading is lazy: the ONNX session and tokenizer are only constructed on
the first rerank call, never at import time (keeps the always-on API
process lean when reranking is off).
"""

from __future__ import annotations

import logging
import os
import time
from functools import lru_cache
from typing import Sequence

from app.config import settings
from app.ranking.rrf import RankedCandidate

logger = logging.getLogger(__name__)

_DEFAULT_BUDGET_MS = 200.0
_PAIRED_FORMAT = "{} [SEP] {}"

_warned_missing_model = False


def _is_enabled() -> bool:
    return bool(settings.rerank_enabled)


def _model_available(model_dir: str) -> bool:
    """True if required ONNX + tokenizer files exist under model_dir."""
    onnx = os.path.join(model_dir, "model.onnx")
    tokenizer_txt = os.path.join(model_dir, "tokenizer.json")
    bad_tok = os.path.join(model_dir, "tokenizer_config.json")
    return os.path.isfile(onnx) and os.path.isfile(tokenizer_txt) and os.path.isfile(bad_tok)


@lru_cache(maxsize=1)
def _get_reranker() -> "CrossEncoderReranker":
    """Lazily load and cache a single reranker instance."""
    logger.info("Loading reranker model from %s", settings.rerank_model_dir)
    return CrossEncoderReranker(
        model_dir=settings.rerank_model_dir,
        budget_ms=settings.rerank_budget_ms or _DEFAULT_BUDGET_MS,
    )


class CrossEncoderReranker:
    """Thin wrapper around an ONNX cross-encoder session + HF tokenizer.

    Encodes ``query + passage`` pairs and returns a sigmoid logit as the
    relevance score. Only instantiated when reranking is enabled and the
    model files are present.
    """

    def __init__(self, model_dir: str, budget_ms: float = _DEFAULT_BUDGET_MS):
        self.model_dir = model_dir
        self.budget_ms = budget_ms
        # Imports deferred so the module is import-safe even without
        # transformers.onnx / onnxruntime installed.
        import onnxruntime as ort

        from tokenizers import Tokenizer

        self._session = ort.InferenceSession(
            os.path.join(model_dir, "model.onnx"),
            providers=ort.get_available_providers(),
        )
        self._tokenizer = Tokenizer.from_file(os.path.join(model_dir, "tokenizer.json"))

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        """Return a relevance score per passage, order-preserving."""
        if not passages:
            return []
        inputs = self._tokenizer.encode_batch(
            [_PAIRED_FORMAT.format(query, p) for p in passages]
        )
        text_ids = [e.ids for e in inputs]
        attention = [e.attention_mask for e in inputs]
        token_type = getattr(inputs[0], "type_ids", None)

        feed = {self._session.get_inputs()[0].name: text_ids}
        for inp in self._session.get_inputs()[1:]:
            if inp.name.endswith("attention_mask") or "attention_mask" in inp.name:
                feed[inp.name] = attention
            elif token_type is not None and ("token" in inp.name or "type" in inp.name):
                feed[inp.name] = [getattr(e, "type_ids", [0] * len(e.ids)) for e in inputs]

        scores = self._session.run(None, feed)[0].tolist()
        # Squash logits to (0,1) when the model returns raw logits.
        if len(scores) and isinstance(scores[0], list) and len(scores[0]) == 1:
            scores = [s[0] for s in scores]
        return [1.0 / (1.0 + 2.718281828459045 ** (-s)) for s in scores]


def rerank_candidates(
    candidates: Sequence[RankedCandidate],
    query_text: str,
    top_k: int | None = None,
) -> list[RankedCandidate]:
    """Rerank the top-K RRF candidates by cross-encoder relevance.

    Returns the full candidate list re-ordered: the reranked top-K first
    (descending reranker score), then any remaining candidates appended in
    their original order. A pure passthrough when reranking is disabled or
    the model is unavailable.
    """
    global _warned_missing_model

    ordered = list(candidates)
    if not _is_enabled():
        return ordered

    if not _model_available(settings.rerank_model_dir):
        if not _warned_missing_model:
            logger.warning(
                "rerank_enabled is True but no cross-encoder model found in %s; "
                "falling back to RRF order.",
                settings.rerank_model_dir,
            )
            _warned_missing_model = True
        return ordered

    top_n = top_k or settings.rerank_top_k
    top_candidates = ordered[:top_n]
    rest = ordered[top_n:]

    if not top_candidates:
        return ordered

    start = time.perf_counter()
    try:
        r = _get_reranker()
        passages = [c.content for c in top_candidates]
        scores = r.score(query_text, passages)
    except Exception as exc:  # never let reranking take down search
        logger.exception("reranker failed (%s); keeping RRF order", exc)
        return ordered

    elapsed_ms = (time.perf_counter() - start) * 1000
    if elapsed_ms > (settings.rerank_budget_ms or _DEFAULT_BUDGET_MS):
        logger.warning(
            "reranker took %.1f ms (budget %.1f ms) — CLAUDE.md rule 6",
            elapsed_ms,
            settings.rerank_budget_ms or _DEFAULT_BUDGET_MS,
        )

    paired = sorted(zip(top_candidates, scores), key=lambda x: x[1], reverse=True)
    return [c for c, _ in paired] + rest