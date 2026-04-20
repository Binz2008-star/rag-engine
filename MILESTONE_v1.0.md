# Milestone v1.0 — Stable Grounded RAG with Enforceable Evaluation

**Tag:** `v1.0-strict-promote`
**Merge commit:** `6cd0015` (PR #6)
**Date:** 2026-04-21
**Status:** Production baseline — behavior frozen until a new failure appears.

---

## What changed

### Core architectural fix

Unified the grounding contract between runtime and evaluator. Previously two layers disagreed:

- Pipeline post-check (`_is_grounded`): token-overlap at `> 0.5` (lenient)
- Evaluator (`check_grounding`): sentence-level semantic cosine at `0.60` (strict)

When `check_grounding` rejected an answer inside the pipeline, the ungrounded text was flagged but **kept** — product shipped content the evaluator rejected. This caused a split-brain between local PROMOTE and CI REJECT driven by model wording drift on `qwen2:1.5b`.

**Fix:** `check_grounding()` is now the authoritative runtime gate. On rejection the answer is converted to `Insufficient data.` and classified as `retrieval_miss`. The redundant weaker `_is_grounded` layer is removed.

### Supporting changes landed in the same milestone

- System-role prompt isolation (prompt-injection defense)
- Sensitive-query short-circuit with preserved domain routing
- Multi-pass OCR fallback (300 DPI / 400 DPI, psm6 / psm11)
- Event sourcing, drift detection, alerting pipeline (`analysis/`, `events/`)
- Strict vs dev CI workflow separation with pinned Ollama digests
- Centralized refusal predicates (`evaluation/refusal.py`)
- Killer-query enforcement in the evaluation suite
- OCR presence gate as fail-closed signal

---

## Guarantees now in effect

| Guarantee | Enforced by |
|---|---|
| Runtime and evaluator agree on "grounded" | `check_grounding()` called in both paths |
| Ungrounded outputs never ship | pipeline converts to `Insufficient data.` on rejection |
| No hallucination under strict eval | evaluator cosine 0.60 gate + zero-hallucination policy |
| No prompt-injection content leakage | system-role isolation in `generation/llm.py` |
| Sensitive queries refused before routing leak | pre-routing filter in `app/pipeline.py` |
| OCR regressions blocked | `evaluation/ocr_check.py` fail-closed check |
| Model drift in CI detected | pinned Ollama digests + digest log on runner |
| Silent eval-suite weakening prevented | `scripts/check_strict_pass.py` killer-row warning |

---

## Frozen surfaces (do not modify without a new failure signal)

- Retrieval: `TOP_K`, reranker, score thresholds
- Grounding: cosine `0.60`, overlap `>= 1`
- Prompting: system prompt in `generation/llm.py`
- Chunking: chunk size, overlap
- Refusal predicates: `evaluation/refusal.py` keyword list
- Eval suite versioning: `strict_eval_v_current_corpus`

Any change to the above must be accompanied by:
1. A reproducible failure case demonstrating the need
2. A strict eval run before and after
3. A review note explaining why the frozen surface was touched

---

## Verification state at tag time

| Check | Result |
|---|---|
| Local strict (38 queries, no `--fast`) | PROMOTE, pass 38/38, hallucination 0% |
| CI strict (`qwen2:1.5b` CPU runner) | PROMOTE, 3 consecutive green runs |
| CI dev (`baseline_en`, 10 queries) | PASS, hallucination 0% |
| OCR presence check | PASS |
| Domain accuracy | 96% (above 95% threshold) |
| Refusal accuracy | 100% |

---

## Rollback

```powershell
git checkout v1.0-strict-promote
```

If a future change regresses the gate, reset main to this tag and re-plan.

---

## Next horizon (not in scope for v1.0)

- Bulk corpus expansion beyond the controlled ECO additions
- PPTX ingestion support
- Adversarial test expansion (Arabic/mixed edge cases beyond current 38)
- Regression test asserting `check_grounding` remains the sole authoritative grounding gate
