#!/usr/bin/env python3
"""Train intent classification model."""

import argparse
import json
import joblib
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# Add parent to path to import app modules
import sys
sys.path.append(str(Path(__file__).parent.parent))


def load_dataset(dataset_path: Path) -> Tuple[List[str], List[str]]:
    """Load dataset from JSON or JSONL file."""
    queries = []
    intents = []

    with open(dataset_path, encoding="utf-8") as f:
        content = f.read()
        # Try JSONL first (line-by-line)
        try:
            for line in content.strip().split('\n'):
                if line:
                    item = json.loads(line)
                    queries.append(item.get("query", item.get("text")))
                    intents.append(item.get("intent", item.get("label")))
        except json.JSONDecodeError:
            # Fall back to JSON
            data = json.loads(content)
            for item in data:
                queries.append(item.get("query", item.get("text")))
                intents.append(item.get("intent", item.get("label")))

    return queries, intents


def train_model(queries: List[str], intents: List[str]) -> Tuple[LogisticRegression, TfidfVectorizer, LabelEncoder]:
    """Train intent classification model."""
    # Encode labels
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(intents)

    # Split for evaluation
    X_train, X_test, y_train, y_test = train_test_split(
        queries, y, test_size=0.2, random_state=42, stratify=y
    )

    # Create features
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 3),
        max_features=5000,
        min_df=1,
        sublinear_tf=True
    )

    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    # Train model
    model = LogisticRegression(
        max_iter=1000,
        random_state=42,
        class_weight='balanced',
        C=1.0
    )

    model.fit(X_train_vec, y_train)

    # Evaluate
    y_pred = model.predict(X_test_vec)
    print("Test set performance:")
    print(classification_report(
        y_test, y_pred,
        target_names=label_encoder.classes_,
        zero_division=0
    ))

    # Show confidence on training data
    train_probs = model.predict_proba(X_train_vec)
    train_confidence = np.max(train_probs, axis=1)
    print(f"\nTraining set confidence stats:")
    print(f"  Mean: {train_confidence.mean():.3f}")
    print(f"  Min: {train_confidence.min():.3f}")
    print(f"  Below 0.8: {(train_confidence < 0.8).sum()}/{len(train_confidence)}")

    return model, vectorizer, label_encoder


def save_model(model: LogisticRegression, vectorizer: TfidfVectorizer, label_encoder: LabelEncoder, output_dir: Path) -> None:
    """Save trained model components."""
    output_dir.mkdir(exist_ok=True)

    # Save model
    model_path = output_dir / "intent_model.joblib"
    joblib.dump({
        'model': model,
        'vectorizer': vectorizer,
        'label_encoder': label_encoder
    }, model_path)

    print(f"\nModel saved to {model_path}")

    # Save metadata
    metadata = {
        'intents': label_encoder.classes_.tolist(),
        'n_features': len(vectorizer.vocabulary_),
        'model_type': 'LogisticRegression'
    }

    metadata_path = output_dir / "intent_model_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata saved to {metadata_path}")


def main():
    """Train intent classification model."""
    parser = argparse.ArgumentParser(description='Train intent classification model')
    parser.add_argument('--train', type=str, default='data/intent_dataset_clean.json',
                        help='Path to training data (JSON or JSONL)')
    args = parser.parse_args()

    print("Training intent classifier...")

    # Load dataset
    dataset_path = Path(args.train)
    queries, intents = load_dataset(dataset_path)

    print(f"Dataset loaded: {len(queries)} examples")
    print(f"Intents: {set(intents)}")

    # Train model
    model, vectorizer, label_encoder = train_model(queries, intents)

    # Save model
    models_dir = Path(__file__).parent.parent / "models"
    save_model(model, vectorizer, label_encoder, models_dir)

    print("\nTraining complete!")


if __name__ == "__main__":
    main()
