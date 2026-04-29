from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

import requests

from app.config import MAX_RETRIES, TIMEOUT, CHAT_MODEL, OLLAMA_BASE_URL

log = logging.getLogger(__name__)

# Hard ceiling for the entire gap analysis (LLM call + retries).
# Prevents 20-30s hangs when Ollama is slow.  Configurable via env.
_GAP_TIMEOUT_S = int(os.environ.get("KGAP_TIMEOUT_S", "5"))
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kgap")
from app.models import KnowledgeGap


_VALID_GAP_TYPES = frozenset({
    "missing_information",
    "terminology_mismatch",
    "scope_out_of_bounds",
    "ambiguous_query",
    "temporal_mismatch",
})

_FALLBACK = KnowledgeGap(
    gap_type="missing_information",
    confidence_if_adversarial=0.0,
    suggested_action="add_relevant_documents",
)


class KnowledgeGapAnalyzer:
    """Analyzes knowledge gaps when retrieval fails.

    Set ``bypass_llm=True`` (or export ``KGAP_BYPASS_LLM=1``) to skip the
    remote LLM call and return the deterministic fallback immediately. This
    is used during fast evaluation runs where the downstream
    ``CorpusTopicMap`` signal is sufficient and the extra LLM round-trip
    would dominate latency.
    """

    def __init__(self, llm, *, bypass_llm: bool | None = None) -> None:
        self.llm = llm
        self._cache: dict[str, KnowledgeGap] = {}
        if bypass_llm is None:
            bypass_llm = os.environ.get("KGAP_BYPASS_LLM", "").strip() in {"1", "true", "True"}
        self.bypass_llm = bool(bypass_llm)

    def analyze(self, query: str, intent: str, normalized_query: str) -> KnowledgeGap:
        if self.bypass_llm:
            return KnowledgeGap(
                gap_type=_FALLBACK.gap_type,
                confidence_if_adversarial=_FALLBACK.confidence_if_adversarial,
                suggested_action=_FALLBACK.suggested_action,
            )
        key = hashlib.md5(f"{intent}:{normalized_query}".encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]

        t0 = time.perf_counter()
        try:
            future = _EXECUTOR.submit(self._run, query, intent, normalized_query)
            result = future.result(timeout=_GAP_TIMEOUT_S)
        except FuturesTimeout:
            elapsed = time.perf_counter() - t0
            log.warning(
                "knowledge_gap: LLM call timed out after %.1fs (limit=%ds), "
                "returning fallback",
                elapsed, _GAP_TIMEOUT_S,
            )
            result = KnowledgeGap(
                gap_type="missing_information",
                confidence_if_adversarial=0.0,
                suggested_action="add_relevant_documents",
            )
        except Exception:
            log.exception("knowledge_gap: unexpected error")
            result = KnowledgeGap(
                gap_type="missing_information",
                confidence_if_adversarial=0.0,
                suggested_action="add_relevant_documents",
            )

        elapsed = time.perf_counter() - t0
        log.info("knowledge_gap: completed in %.1fs", elapsed)
        self._cache[key] = result
        return result

    def _run(self, query: str, intent: str, normalized_query: str) -> KnowledgeGap:
        prompt = (
            "You are analyzing why a retrieval system failed to find relevant documents.\n"
            "Categorize the knowledge gap and suggest an action.\n\n"
            f"Query: {query}\n"
            f"Normalized Query: {normalized_query}\n"
            f"Detected Intent: {intent}\n\n"
            "Respond with a JSON object only:\n"
            '{"gap_type": "<type>", "confidence_if_adversarial": <float>, "suggested_action": "<action>"}\n'
            f"gap_type must be one of: {', '.join(sorted(_VALID_GAP_TYPES))}"
        )
        raw = self._call_with_retry(prompt)
        return self._parse(raw)

    def _call_with_retry(self, prompt: str) -> str:
        base_url = OLLAMA_BASE_URL.rstrip("/")
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": CHAT_MODEL,
                        "stream": False,
                        "messages": [{"role": "user", "content": prompt}],
                        "options": {"temperature": 0.0, "num_predict": 128},
                    },
                    timeout=TIMEOUT,
                )
                resp.raise_for_status()
                return resp.json()["message"]["content"].strip()
            except Exception as exc:
                last_exc = exc
                time.sleep(2 ** attempt)
        return json.dumps({
            "gap_type": "missing_information",
            "confidence_if_adversarial": 0.0,
            "suggested_action": "add_relevant_documents",
        })

    def _parse(self, raw: str) -> KnowledgeGap:
        try:
            m = re.search(r"\{[^{}]*\}", raw)
            data = json.loads(m.group() if m else raw)
            gap_type = data.get("gap_type", "missing_information")
            if gap_type not in _VALID_GAP_TYPES:
                gap_type = "missing_information"
            return KnowledgeGap(
                gap_type=gap_type,
                confidence_if_adversarial=max(0.0, min(1.0, float(data.get("confidence_if_adversarial", 0.0)))),
                suggested_action=data.get("suggested_action", "add_relevant_documents"),
            )
        except (json.JSONDecodeError, KeyError, ValueError, AttributeError):
            return _FALLBACK
