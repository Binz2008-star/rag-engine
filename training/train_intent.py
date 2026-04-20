from __future__ import annotations

import json
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.config import MODEL_DIR


def load_jsonl(path: Path) -> tuple[list[str], list[str]]:
    queries: list[str] = []
    labels: list[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            queries.append(row["query"])
            labels.append(row["label"])
    return queries, labels


def train_intent_model(train_path: Path, output_name: str) -> Path:
    queries, labels = load_jsonl(train_path)
    model = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2))),
            ("clf", LogisticRegression(max_iter=500)),
        ]
    )
    model.fit(queries, labels)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MODEL_DIR / output_name
    joblib.dump(model, out_path)
    return out_path
