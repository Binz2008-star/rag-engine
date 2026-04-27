import json

# Read the latest eval report
with open('reports/eval_1777076263.json', 'r') as f:
    data = json.load(f)

# Get all grounding_reject examples
grounding_rejects = [r for r in data['results'] if r.get('failure_type') == 'grounding_reject']

# Categories
true_missing_corpus = []
over_conservative = []
adversarial_injection = []
multilingual = []

# Categorize each grounding_reject
for r in grounding_rejects:
    query = r['question'].lower()

    # Adversarial/injection attempts
    if any(kw in query for kw in ['ignore', 'reveal', 'system prompt', 'instructions', 'developer testing']):
        adversarial_injection.append(r)
    # Multilingual queries (Arabic)
    elif any(ord(c) > 127 for c in r['question']):
        multilingual.append(r)
    # True missing corpus (general knowledge questions not in corpus)
    elif any(kw in query for kw in ['gdp of japan', 'gdp of mars', 'economic output of mars', 'quantum entanglement', 'naffco']):
        true_missing_corpus.append(r)
    # Over-conservative (should have answer in corpus)
    else:
        over_conservative.append(r)

print(f'Total grounding_reject failures: {len(grounding_rejects)}')
print()
print(f'True missing corpus: {len(true_missing_corpus)}')
print(f'Over-conservative (LLM refusal): {len(over_conservative)}')
print(f'Adversarial/injection: {len(adversarial_injection)}')
print(f'Multilingual: {len(multilingual)}')
print()

print('=== TRUE MISSING CORPUS ===')
for r in true_missing_corpus:
    print(f"- {r['question']}")

print()
print('=== OVER-CONSERVATIVE (LLM REFUSAL) ===')
for r in over_conservative[:20]:  # Show first 20
    print(f"- {r['question']}")
    print(f"  Sources: {r['sources'][:3]}")

print()
print('=== ADVERSARIAL/INJECTION ===')
for r in adversarial_injection:
    print(f"- {r['question']}")

print()
print('=== MULTILINGUAL ===')
for r in multilingual[:10]:  # Show first 10
    print(f"- {r['question']}")
