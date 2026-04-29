"""
Backfill lead scores for existing leads in Neon DB.
Run once after Phase 2 deployment.
"""
import os
import sys
from typing import Dict, Any, Optional
import psycopg2
from dotenv import load_dotenv

# Add pipeline to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pipeline'))

load_dotenv()

DB_URL = os.environ["DATABASE_URL"]


def get_db():
    """Get database connection."""
    return psycopg2.connect(DB_URL)


def fetch_unscored_leads() -> list:
    """Fetch leads without scores."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, full_name, company_name, email, phone,
                   services_required, source
            FROM leads
            WHERE lead_score IS NULL
            ORDER BY id
            """
        )
        columns = [desc[0] for desc in cur.description]
        leads = []
        for row in cur.fetchall():
            leads.append(dict(zip(columns, row)))
        return leads
    finally:
        cur.close()
        conn.close()


def update_lead_score(lead_id: int, score_data: Dict[str, Any]) -> bool:
    """Update lead with score data."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE leads
            SET lead_score = %s,
                score_band = %s,
                rag_intent = %s,
                rag_confidence = %s,
                rag_method = %s,
                recommended_action = %s,
                scored_at = NOW()
            WHERE id = %s
            """,
            (
                score_data.get('lead_score'),
                score_data.get('score_band'),
                score_data.get('rag_intent'),
                score_data.get('rag_confidence'),
                score_data.get('rag_method'),
                score_data.get('recommended_action'),
                lead_id
            )
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating lead {lead_id}: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def main():
    """Backfill scores for all unscored leads."""
    print("Fetching unscored leads...")
    leads = fetch_unscored_leads()
    print(f"Found {len(leads)} leads to score")

    if not leads:
        print("No leads need scoring. Exiting.")
        return

    # Import lead_scorer
    try:
        from lead_scorer import get_scorer
        scorer = get_scorer()
        print("Lead scorer loaded successfully")
    except ImportError as e:
        print(f"Error importing lead_scorer: {e}")
        print("Make sure lead_scorer.py is in the pipeline/ directory")
        return

    # Optional: Import RAG client for intent classification
    rag_available = False
    try:
        from rag_client import classify_lead
        rag_available = True
        print("RAG client available for intent classification")
    except ImportError:
        print("RAG client not available - scoring without RAG intent")

    # Score each lead
    hot_count = 0
    warm_count = 0

    for lead in leads:
        lead_id = lead['id']
        print(f"\nScoring lead #{lead_id}: {lead.get('full_name', 'N/A')} ({lead.get('company_name', 'N/A')})")

        # Build question for RAG classification
        services = lead.get('services_required', [])
        if isinstance(services, str):
            services = [services]
        question = f"{lead.get('company_name', '')} {' '.join(services) if services else 'inquiry'}"

        # Get RAG intent if available
        rag_result = None
        if rag_available:
            try:
                rag_result = classify_lead(question)
                print(f"  RAG intent: {rag_result.get('intent')} (conf: {rag_result.get('confidence', 0):.2f})")
            except Exception as e:
                print(f"  RAG classification failed: {e}")

        # Score the lead
        try:
            score_result = scorer.score(lead, rag_result)

            # Add RAG data to score result
            if rag_result:
                score_result['rag_intent'] = rag_result.get('intent')
                score_result['rag_confidence'] = rag_result.get('confidence')
                score_result['rag_method'] = rag_result.get('method')

            print(f"  Score: {score_result['lead_score']} ({score_result['score_band']})")
            print(f"  Action: {score_result['recommended_action']}")

            # Update DB
            if update_lead_score(lead_id, score_result):
                print(f"  ✓ Updated successfully")
                if score_result['score_band'] == 'HOT':
                    hot_count += 1
                elif score_result['score_band'] == 'WARM':
                    warm_count += 1
            else:
                print(f"  ✗ Update failed")

        except Exception as e:
            print(f"  ✗ Scoring failed: {e}")

    print(f"\n{'='*50}")
    print(f"Backfill complete!")
    print(f"Total leads processed: {len(leads)}")
    print(f"HOT leads: {hot_count}")
    print(f"WARM leads: {warm_count}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
