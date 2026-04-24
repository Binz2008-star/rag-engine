## Summary
- 120 rows total (cv=44, eco=37, general=39)
- Meets hard minimums: 100 total, 30/class
- existing_labeled_seed: 71, manual_expansion: 49
- Strict duplicate contract: any normalized duplicate is a hard error

## Validation
- `python scripts/validate_train_v2.py` → exit 0, 0 warnings
- `python -m pytest test_validate_train_v2.py -q` → 12 passed

## Data Reconciliation
- Added 6 missing rows from train.jsonl to ensure full seed coverage
- All 9 train.jsonl queries now included in train_v2_human.jsonl
- Merge path is now a straight replacement

## Constraints
- No router/evaluator/threshold/API changes
- Dataset isolated from train.jsonl pending eval gate
- train_v2_human.jsonl must not merge into train.jsonl until held-out eval confirms no regression

## Files
- data/train_v2_human.jsonl
- scripts/validate_train_v2.py
- test_validate_train_v2.py
