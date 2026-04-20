# RAG Intent System

## Bootstrap

1. Put your documents in `data/docs/`
2. Put your intent datasets in:
   - `data/intent_dataset_base.jsonl`
   - `data/intent_dataset_human.jsonl`
3. Train the initial router:

```bash
python scripts/run_training.py
```

4. Build retrieval indexes:

```bash
python scripts/build_indexes.py
```

5. Run the API:

```bash
uvicorn app.main:app --reload
```

6. Check system health:

```bash
curl http://127.0.0.1:8000/health
```

## Notes

* This is single-node by design.
* Events are stored in SQLite at `logs/events.db`.
* Retraining is batch-triggered, not inline with inference.
* `uncertain` routing blends all indexes instead of silently collapsing to `general`.
* Training promotion should use real eval metrics, not placeholders.
