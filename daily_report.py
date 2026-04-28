"""
Daily Report Generator for ECO Technology Leads
Phase 2: Includes lead scoring, RAG intent, and recommended actions
"""
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.environ["DATABASE_URL"]


def get_db():
    """Get database connection."""
    return psycopg2.connect(DB_URL)


def fetch_hot_warm_leads(days: int = 1) -> List[Dict[str, Any]]:
    """Fetch HOT and WARM leads from last N days."""
    conn = get_db()
    cur = conn.cursor()
    try:
        since = datetime.now() - timedelta(days=days)
        cur.execute(
            """
            SELECT 
                id, full_name, company_name, email, phone,
                services_required, lead_score, score_band,
                rag_intent, rag_confidence, rag_method,
                recommended_action, scored_at, created_at
            FROM leads
            WHERE score_band IN ('HOT', 'WARM')
            AND created_at >= %s
            ORDER BY lead_score DESC, scored_at DESC NULLS LAST
            """,
            (since,)
        )

        columns = [desc[0] for desc in cur.description]
        leads = []
        for row in cur.fetchall():
            lead = dict(zip(columns, row))
            leads.append(lead)
        return leads
    finally:
        cur.close()
        conn.close()


def fetch_lead_stats(days: int = 1) -> Dict[str, Any]:
    """Fetch lead statistics for the period."""
    conn = get_db()
    cur = conn.cursor()
    try:
        since = datetime.now() - timedelta(days=days)

        # Total leads
        cur.execute(
            "SELECT COUNT(*) FROM leads WHERE created_at >= %s",
            (since,)
        )
        total = cur.fetchone()[0]

        # By band
        cur.execute(
            """
            SELECT score_band, COUNT(*) 
            FROM leads 
            WHERE created_at >= %s AND score_band IS NOT NULL
            GROUP BY score_band
            """,
            (since,)
        )
        bands = {row[0]: row[1] for row in cur.fetchall()}

        # RAG stats
        cur.execute(
            """
            SELECT 
                COUNT(*) as total_with_rag,
                AVG(rag_confidence) as avg_confidence
            FROM leads 
            WHERE created_at >= %s AND rag_intent IS NOT NULL
            """,
            (since,)
        )
        rag_stats = cur.fetchone()

        return {
            "total_leads": total,
            "by_band": bands,
            "with_rag": rag_stats[0] if rag_stats else 0,
            "avg_rag_confidence": round(rag_stats[1], 2) if rag_stats and rag_stats[1] else 0,
        }
    finally:
        cur.close()
        conn.close()


def generate_report(days: int = 1) -> str:
    """Generate HTML daily report."""
    leads = fetch_hot_warm_leads(days)
    stats = fetch_lead_stats(days)

    period = f"Last {days} day{'s' if days > 1 else ''}"

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ECO Technology Daily Report - {period}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #2c5530; }}
        h2 {{ color: #4a7c59; margin-top: 30px; }}
        .stats {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .stat-box {{ display: inline-block; margin: 10px 20px; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #2c5530; }}
        .stat-label {{ font-size: 12px; color: #666; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th {{ background: #4a7c59; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f9f9f9; }}
        .hot {{ color: #d32f2f; font-weight: bold; }}
        .warm {{ color: #f57c00; font-weight: bold; }}
        .band-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .band-hot {{ background: #ffebee; color: #c62828; }}
        .band-warm {{ background: #fff3e0; color: #ef6c00; }}
        .rag-info {{ font-size: 12px; color: #666; }}
        .action {{ font-size: 12px; color: #1565c0; font-style: italic; }}
    </style>
</head>
<body>
    <h1>ECO Technology Lead Report</h1>
    <p><strong>Period:</strong> {period}</p>
    <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

    <div class="stats">
        <h2>Summary</h2>
        <div class="stat-box">
            <div class="stat-value">{stats['total_leads']}</div>
            <div class="stat-label">Total Leads</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{stats['by_band'].get('HOT', 0)}</div>
            <div class="stat-label">HOT Leads</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{stats['by_band'].get('WARM', 0)}</div>
            <div class="stat-label">WARM Leads</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{stats['with_rag']}</div>
            <div class="stat-label">With RAG Intent</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{stats['avg_rag_confidence']}%</div>
            <div class="stat-label">Avg RAG Confidence</div>
        </div>
    </div>

    <h2>Hot & Warm Leads (Action Required)</h2>
    <table>
        <thead>
            <tr>
                <th>Band</th>
                <th>Score</th>
                <th>Contact</th>
                <th>Company</th>
                <th>Services</th>
                <th>RAG Intent</th>
                <th>Confidence</th>
                <th>Recommended Action</th>
            </tr>
        </thead>
        <tbody>
"""

    for lead in leads:
        band = lead.get('score_band', 'N/A')
        band_class = 'band-hot' if band == 'HOT' else 'band-warm'

        services = lead.get('services_required', [])
        if isinstance(services, str):
            services = [services]
        services_str = ', '.join(services) if services else 'N/A'

        rag_intent = lead.get('rag_intent') or 'N/A'
        rag_conf = f"{lead.get('rag_confidence', 0):.0%}" if lead.get('rag_confidence') else 'N/A'

        html += f"""            <tr>
                <td><span class="band-badge {band_class}">{band}</span></td>
                <td>{lead.get('lead_score', 'N/A')}</td>
                <td>
                    <strong>{lead.get('full_name', 'N/A')}</strong><br>
                    <small>{lead.get('email', 'N/A')}</small><br>
                    <small>{lead.get('phone', 'N/A')}</small>
                </td>
                <td>{lead.get('company_name', 'N/A')}</td>
                <td><small>{services_str}</small></td>
                <td class="rag-info">{rag_intent}</td>
                <td class="rag-info">{rag_conf}</td>
                <td class="action">{lead.get('recommended_action', 'Follow up')}</td>
            </tr>
"""

    html += """        </tbody>
    </table>

    <h2>Next Steps</h2>
    <ul>
        <li><strong>HOT leads (≥80):</strong> Call within 1 hour</li>
        <li><strong>WARM leads (≥60):</strong> Call within 2 hours</li>
        <li><strong>MEDIUM leads (≥40):</strong> Email proposal within 4 hours</li>
        <li>Update lead status after each contact attempt</li>
    </ul>

    <p style="margin-top: 40px; font-size: 12px; color: #666;">
        This report is auto-generated by ECO Technology Lead Pipeline Phase 2.<br>
        Lead scoring powered by 6-dimension heuristic + RAG intent classification.
    </p>
</body>
</html>
"""

    return html


def main():
    """Generate and save daily report."""
    report = generate_report(days=1)

    # Save to file
    filename = f"daily_report_{datetime.now().strftime('%Y%m%d')}.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"Report generated: {filename}")
    print(f"Hot leads: {report.count('band-hot')}")
    print(f"Warm leads: {report.count('band-warm')}")


if __name__ == "__main__":
    main()
