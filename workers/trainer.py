from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from app.config import BASE_DIR, TRAINING_TRIGGER_FAILURE_COUNT
from app.utils import stable_hash
from evaluation.eval_gate import gate
from evaluation.eval_main import run_eval
from events.replay import load_events
from training.dataset_builder import build_dataset_from_events
from training.registry import register_model
from training.train_intent import train_intent_model


def run_training_cycle(build_pipeline: Callable[[Path], object]) -> str:
    events = load_events()
    failures = [event for event in events if event.get("event_type") == "failure"]
    if len(failures) < TRAINING_TRIGGER_FAILURE_COUNT:
        return f"Skipped training: only {len(failures)} failures"

    dataset = build_dataset_from_events(events)
    out_train = BASE_DIR / "data" / "train.generated.jsonl"
    out_train.parent.mkdir(parents=True, exist_ok=True)
    with open(out_train, "w", encoding="utf-8") as handle:
        for row in dataset:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    dataset_hash = stable_hash(
        [json.dumps(row, sort_keys=True, ensure_ascii=False) for row in dataset]
    )
    version = f"intent_{dataset_hash[:8]}"
    model_path = train_intent_model(out_train, f"{version}.joblib")

    pipeline = build_pipeline(model_path)
    eval_result = run_eval(pipeline, BASE_DIR / "data" / "eval_queries.json")
    metrics = eval_result["metrics"]

    gate_result = gate(metrics)
    decision = gate_result["decision"]
    status = "staging" if decision == "PROMOTE" else "rejected"
    register_model(
        version=version,
        path=str(model_path),
        metrics=metrics,
        dataset_hash=dataset_hash,
        status=status,
    )
    return (
        f"Training completed: version={version}, decision={decision}, "
        f"failed_checks={gate_result['failed_checks']}"
    )
