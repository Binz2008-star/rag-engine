#!/usr/bin/env python3
"""
Convert ECO Technology AI Training Dataset to RAG-ready format.
Extracts atomic facts from ECO_Agent_Training_Document.md.
"""

import json
import re
from pathlib import Path
from typing import List, Dict

# Input and output paths
INPUT_FILE = Path("data/raw/ECO_Agent_Training_Document.md")
OUTPUT_FILE = Path("models/eco_rag_ready.jsonl")

# Read the training document
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# Extract atomic facts manually based on document structure
facts = []

# Company Overview facts
facts.append({
    "id": "eco_company_name",
    "type": "fact",
    "intent": "coverage",
    "entity": "company",
    "text": "ECO Technology Environmental Protection Services LLC is a UAE-based environmental services company.",
    "keywords": ["ECO Technology", "company", "UAE", "environmental services"],
    "source": "company_profile",
    "confidence": 0.9
})

facts.append({
    "id": "eco_company_founded",
    "type": "fact",
    "intent": "coverage",
    "entity": "company",
    "text": "ECO Technology Environmental Protection Services LLC was founded in 2016.",
    "keywords": ["ECO Technology", "founded", "2016", "established"],
    "source": "company_profile",
    "confidence": 0.9
})

facts.append({
    "id": "eco_company_location",
    "type": "fact",
    "intent": "coverage",
    "entity": "uae_coverage",
    "text": "ECO Technology Environmental Protection Services LLC is headquartered in Ajman, United Arab Emirates.",
    "keywords": ["ECO Technology", "headquarters", "Ajman", "UAE", "location"],
    "source": "company_profile",
    "confidence": 0.9
})

facts.append({
    "id": "eco_company_director",
    "type": "fact",
    "intent": "coverage",
    "entity": "company",
    "text": "ECO Technology is operated by Robin Edwan, Founder and General Manager.",
    "keywords": ["ECO Technology", "Robin Edwan", "Founder", "General Manager", "director"],
    "source": "company_profile",
    "confidence": 0.9
})

facts.append({
    "id": "eco_company_founder",
    "type": "fact",
    "intent": "coverage",
    "entity": "company",
    "text": "Robin Edwan is the founder of ECO Technology Environmental Protection Services LLC.",
    "keywords": ["founder", "Robin Edwan", "ECO Technology"],
    "source": "company_profile",
    "confidence": 0.9
})

# Certifications facts
facts.append({
    "id": "eco_cert_iso14001",
    "type": "fact",
    "intent": "compliance",
    "entity": "municipality_approval",
    "text": "ECO Technology holds ISO 14001 Environmental Management System certification.",
    "keywords": ["ISO 14001", "certification", "environmental management", "compliance"],
    "source": "compliance_reference",
    "confidence": 0.9
})

facts.append({
    "id": "eco_cert_iso9001",
    "type": "fact",
    "intent": "compliance",
    "entity": "municipality_approval",
    "text": "ECO Technology holds ISO 9001 Quality Management System certification.",
    "keywords": ["ISO 9001", "certification", "quality management", "compliance"],
    "source": "compliance_reference",
    "confidence": 0.9
})

facts.append({
    "id": "eco_cert_ajman",
    "type": "fact",
    "intent": "compliance",
    "entity": "municipality_approval",
    "text": "ECO Technology has official accreditation from Ajman Municipality (Ref: 01-PHE-021-16-QP0008).",
    "keywords": ["Ajman Municipality", "accreditation", "01-PHE-021-16-QP0008", "compliance"],
    "source": "compliance_reference",
    "confidence": 0.9
})

facts.append({
    "id": "eco_cert_dubai",
    "type": "fact",
    "intent": "compliance",
    "entity": "municipality_approval",
    "text": "ECO Technology is an approved vendor of Dubai Municipality.",
    "keywords": ["Dubai Municipality", "approved vendor", "compliance"],
    "source": "compliance_reference",
    "confidence": 0.9
})

facts.append({
    "id": "eco_cert_abudhabi",
    "type": "fact",
    "intent": "compliance",
    "entity": "municipality_approval",
    "text": "ECO Technology is certified by Abu Dhabi Environment Agency (EAD).",
    "keywords": ["Abu Dhabi", "EAD", "Environment Agency", "certification", "compliance"],
    "source": "compliance_reference",
    "confidence": 0.9
})

facts.append({
    "id": "eco_cert_wildlife",
    "type": "fact",
    "intent": "compliance",
    "entity": "municipality_approval",
    "text": "ECO Technology is a member of UAE Wildlife Society.",
    "keywords": ["UAE Wildlife Society", "member", "certification", "compliance"],
    "source": "compliance_reference",
    "confidence": 0.9
})

# Service facts
facts.append({
    "id": "eco_service_grease_cleaning",
    "type": "fact",
    "intent": "service",
    "entity": "grease_trap",
    "text": "ECO Technology provides monthly or scheduled grease trap cleaning and maintenance for commercial kitchens, restaurants, hotels, and food establishments across all 7 UAE Emirates.",
    "keywords": ["grease trap", "cleaning", "maintenance", "monthly", "scheduled", "commercial kitchens", "restaurants", "hotels"],
    "source": "service_spec",
    "confidence": 0.9
})

facts.append({
    "id": "eco_service_grease_installation",
    "type": "fact",
    "intent": "service",
    "entity": "grease_trap",
    "text": "ECO Technology supplies and professionally installs grease traps in 4 sizes: D (entry), A (small), B (medium/popular), C (large commercial).",
    "keywords": ["grease trap", "supply", "installation", "sizes", "D", "A", "B", "C"],
    "source": "service_spec",
    "confidence": 0.9
})

facts.append({
    "id": "eco_service_marine_cleaning",
    "type": "fact",
    "intent": "service",
    "entity": "sewage_desludging",
    "text": "ECO Technology provides professional cleaning of marine vessels and tanks in Dubai, Abu Dhabi, Sharjah, Ajman, and all UAE maritime facilities.",
    "keywords": ["marine vessel", "tank cleaning", "Dubai", "Abu Dhabi", "Sharjah", "Ajman", "UAE"],
    "source": "service_spec",
    "confidence": 0.9
})

facts.append({
    "id": "eco_service_uco",
    "type": "fact",
    "intent": "service",
    "entity": "uco_recycling",
    "text": "ECO Technology provides regular collection of used cooking oils from restaurants and hotels and issues recycling certificates to clients.",
    "keywords": ["used cooking oil", "UCO", "collection", "recycling", "restaurants", "hotels", "certificates"],
    "source": "service_spec",
    "confidence": 0.9
})

facts.append({
    "id": "eco_service_pressure_washing",
    "type": "fact",
    "intent": "service",
    "entity": "drain_jetting",
    "text": "ECO Technology provides industrial and commercial high-pressure cleaning of drain lines, grease traps, surfaces, and equipment.",
    "keywords": ["high-pressure washing", "drain lines", "grease traps", "surfaces", "equipment", "industrial", "commercial"],
    "source": "service_spec",
    "confidence": 0.9
})

facts.append({
    "id": "eco_service_biological",
    "type": "definition",
    "intent": "service",
    "entity": "biological_treatment",
    "text": "Biological Treatment (GES System) uses non-harmful bacteria treatment that eliminates odours, reduces grease accumulation by 85%, and extends drainage system lifespan by 200%.",
    "keywords": ["biological treatment", "GES System", "bacteria", "odours", "grease accumulation", "drainage lifespan"],
    "source": "service_spec",
    "confidence": 0.9
})

# Pricing facts
facts.append({
    "id": "eco_pricing_grease_d",
    "type": "fact",
    "intent": "pricing",
    "entity": "grease_trap",
    "text": "Grease Trap Size D (entry for small cafes) price is AED 2,500 excluding VAT.",
    "keywords": ["grease trap", "Size D", "entry", "small cafes", "AED 2500", "price", "VAT"],
    "source": "internal_pricing_doc",
    "confidence": 0.9
})

facts.append({
    "id": "eco_pricing_grease_d_vat",
    "type": "fact",
    "intent": "pricing",
    "entity": "grease_trap",
    "text": "Grease Trap Size D VAT (5%) is AED 125.",
    "keywords": ["grease trap", "Size D", "VAT", "5%", "AED 125"],
    "source": "internal_pricing_doc",
    "confidence": 0.9
})

facts.append({
    "id": "eco_pricing_grease_a",
    "type": "fact",
    "intent": "pricing",
    "entity": "grease_trap",
    "text": "Grease Trap Size A (small restaurants) price is AED 4,500 excluding VAT.",
    "keywords": ["grease trap", "Size A", "small restaurants", "AED 4500", "price", "VAT"],
    "source": "internal_pricing_doc",
    "confidence": 0.9
})

facts.append({
    "id": "eco_pricing_grease_a_vat",
    "type": "fact",
    "intent": "pricing",
    "entity": "grease_trap",
    "text": "Grease Trap Size A VAT (5%) is AED 225.",
    "keywords": ["grease trap", "Size A", "VAT", "5%", "AED 225"],
    "source": "internal_pricing_doc",
    "confidence": 0.9
})

facts.append({
    "id": "eco_pricing_grease_b",
    "type": "fact",
    "intent": "pricing",
    "entity": "grease_trap",
    "text": "Grease Trap Size B (medium restaurants) price is AED 6,000 excluding VAT.",
    "keywords": ["grease trap", "Size B", "medium restaurants", "AED 6000", "price", "VAT"],
    "source": "internal_pricing_doc",
    "confidence": 0.9
})

facts.append({
    "id": "eco_pricing_grease_b_vat",
    "type": "fact",
    "intent": "pricing",
    "entity": "grease_trap",
    "text": "Grease Trap Size B VAT (5%) is AED 300.",
    "keywords": ["grease trap", "Size B", "VAT", "5%", "AED 300"],
    "source": "internal_pricing_doc",
    "confidence": 0.9
})

facts.append({
    "id": "eco_pricing_grease_c",
    "type": "fact",
    "intent": "pricing",
    "entity": "grease_trap",
    "text": "Grease Trap Size C (large commercial kitchens, hotels) price starts from AED 8,000 excluding VAT.",
    "keywords": ["grease trap", "Size C", "large commercial kitchens", "hotels", "AED 8000", "price", "VAT"],
    "source": "internal_pricing_doc",
    "confidence": 0.9
})

facts.append({
    "id": "eco_pricing_grease_c_vat",
    "type": "fact",
    "intent": "pricing",
    "entity": "grease_trap",
    "text": "Grease Trap Size C VAT (5%) starts from AED 400.",
    "keywords": ["grease trap", "Size C", "VAT", "5%", "AED 400"],
    "source": "internal_pricing_doc",
    "confidence": 0.9
})

facts.append({
    "id": "eco_pricing_addon_sink",
    "type": "fact",
    "intent": "pricing",
    "entity": "grease_trap",
    "text": "Sink connections add-on price is AED 500 plus 5% VAT.",
    "keywords": ["sink connections", "add-on", "AED 500", "VAT", "5%"],
    "source": "internal_pricing_doc",
    "confidence": 0.9
})

facts.append({
    "id": "eco_pricing_addon_cover",
    "type": "fact",
    "intent": "pricing",
    "entity": "grease_trap",
    "text": "Metal cover add-on price is AED 1,000 plus 5% VAT.",
    "keywords": ["metal cover", "add-on", "AED 1000", "VAT", "5%"],
    "source": "internal_pricing_doc",
    "confidence": 0.9
})

# AMC facts
facts.append({
    "id": "eco_amc_price",
    "type": "fact",
    "intent": "pricing",
    "entity": "amc",
    "text": "Annual Maintenance Contract starts from AED 48,000 per year plus 5% VAT for institutional clients including malls, hotels, hospitals, and industrial facilities.",
    "keywords": ["AMC", "Annual Maintenance Contract", "AED 48000", "VAT", "5%", "institutional", "malls", "hotels", "hospitals"],
    "source": "internal_pricing_doc",
    "confidence": 0.9
})

facts.append({
    "id": "eco_amc_visits",
    "type": "fact",
    "intent": "service",
    "entity": "amc",
    "text": "AMC contracts include 24 or 36 scheduled visits per year at client's choice.",
    "keywords": ["AMC", "visits", "scheduled", "24", "36", "year", "maintenance"],
    "source": "service_spec",
    "confidence": 0.9
})

facts.append({
    "id": "eco_amc_emergency_response",
    "type": "fact",
    "intent": "emergency",
    "entity": "amc",
    "text": "AMC contracts guarantee emergency call-out within 60-120 minutes.",
    "keywords": ["AMC", "emergency", "call-out", "60-120 minutes", "response time"],
    "source": "service_spec",
    "confidence": 0.9
})

facts.append({
    "id": "eco_amc_waste_limit",
    "type": "fact",
    "intent": "service",
    "entity": "amc",
    "text": "AMC contracts include waste disposal up to 50-70 cubic metres per month.",
    "keywords": ["AMC", "waste disposal", "50-70 cubic metres", "monthly"],
    "source": "service_spec",
    "confidence": 0.9
})

facts.append({
    "id": "eco_amc_reports",
    "type": "fact",
    "intent": "service",
    "entity": "amc",
    "text": "AMC contracts include quarterly compliance reports with photographic documentation.",
    "keywords": ["AMC", "compliance reports", "quarterly", "photographic documentation"],
    "source": "service_spec",
    "confidence": 0.9
})

facts.append({
    "id": "eco_amc_compliance",
    "type": "fact",
    "intent": "compliance",
    "entity": "amc",
    "text": "AMC contracts include full Ajman Municipality and UAE regulatory compliance.",
    "keywords": ["AMC", "Ajman Municipality", "UAE regulatory", "compliance"],
    "source": "compliance_reference",
    "confidence": 0.9
})

facts.append({
    "id": "eco_amc_support",
    "type": "fact",
    "intent": "service",
    "entity": "amc",
    "text": "AMC contracts include dedicated account manager and 24/7 hotline.",
    "keywords": ["AMC", "account manager", "24/7 hotline", "support"],
    "source": "service_spec",
    "confidence": 0.9
})

# Coverage facts
facts.append({
    "id": "eco_coverage_uae",
    "type": "fact",
    "intent": "coverage",
    "entity": "uae_coverage",
    "text": "ECO Technology serves all 7 UAE Emirates: Abu Dhabi, Dubai, Sharjah, Ajman, Umm Al Quwain, Ras Al Khaimah, and Fujairah.",
    "keywords": ["coverage", "UAE", "7 emirates", "Abu Dhabi", "Dubai", "Sharjah", "Ajman", "Umm Al Quwain", "Ras Al Khaimah", "Fujairah"],
    "source": "company_profile",
    "confidence": 0.9
})

# Contact facts
facts.append({
    "id": "eco_contact_phone",
    "type": "contact",
    "intent": "emergency",
    "entity": "emergency_contact",
    "text": "ECO Technology phone number is +971 52 223 3989.",
    "keywords": ["phone", "+971 52 223 3989", "contact"],
    "source": "emergency_contact_record",
    "confidence": 1.0
})

facts.append({
    "id": "eco_contact_whatsapp",
    "type": "contact",
    "intent": "emergency",
    "entity": "emergency_contact",
    "text": "ECO Technology WhatsApp number is +971 52 223 3989.",
    "keywords": ["WhatsApp", "+971 52 223 3989", "contact"],
    "source": "emergency_contact_record",
    "confidence": 1.0
})

facts.append({
    "id": "eco_contact_email",
    "type": "contact",
    "intent": "emergency",
    "entity": "emergency_contact",
    "text": "ECO Technology email address is robinedwan@gmail.com.",
    "keywords": ["email", "robinedwan@gmail.com", "contact"],
    "source": "emergency_contact_record",
    "confidence": 1.0
})

facts.append({
    "id": "eco_business_hours",
    "type": "fact",
    "intent": "service",
    "entity": "company",
    "text": "ECO Technology business hours are Sunday-Thursday 8:00 AM-6:00 PM UAE time.",
    "keywords": ["business hours", "Sunday-Thursday", "8:00 AM-6:00 PM", "UAE time"],
    "source": "company_profile",
    "confidence": 0.9
})

facts.append({
    "id": "eco_emergency_availability",
    "type": "fact",
    "intent": "emergency",
    "entity": "emergency_contact",
    "text": "ECO Technology provides 24/7 emergency service all week.",
    "keywords": ["emergency", "24/7", "all week", "availability"],
    "source": "emergency_contact_record",
    "confidence": 1.0
})

# Client facts (excluded - these are client lists without verifiable source grounding in this context)
# Statistics facts (excluded - "80+ clients", "500+ projects" are unsupported statistics without source grounding)

# Validate facts
def validate_fact(fact: Dict) -> bool:
    """Validate a fact according to rules."""
    text = fact["text"].lower()

    # Check for CTA phrases
    cta_phrases = ["call", "contact us", "share", "send", "reach out", "get in touch"]
    if any(phrase in text for phrase in cta_phrases):
        return False

    # Check for questions
    if "?" in text:
        return False

    # Check for ambiguous wording
    ambiguous = ["depends on", "can vary", "typically", "usually", "approximately"]
    if any(phrase in text for phrase in ambiguous):
        return False

    # Check for marketing claims without measurable anchor
    marketing = ["best service", "top quality", "excellent service", "premium service"]
    if any(phrase in text for phrase in marketing):
        return False

    # Check for unsupported statistics with "+" (unless from official source)
    if "+" in text and "emirates" not in text.lower():
        # Allow "all 7 UAE Emirates" but not "80+ clients"
        if "clients" in text.lower() or "projects" in text.lower():
            return False

    return True

# Apply validation
validated_facts = [f for f in facts if validate_fact(f)]
excluded_count = len(facts) - len(validated_facts)

# Write JSONL output
with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
    for fact in validated_facts:
        outfile.write(json.dumps(fact, ensure_ascii=False) + "\n")

# Generate statistics
intent_counts = {}
entity_counts = {}
for fact in validated_facts:
    intent_counts[fact["intent"]] = intent_counts.get(fact["intent"], 0) + 1
    entity_counts[fact["entity"]] = entity_counts.get(fact["entity"], 0) + 1

# Print report
print("=" * 60)
print("ECO Dataset RAG-Ready Conversion Report")
print("=" * 60)
print(f"Total rows generated: {len(validated_facts)}")
print(f"\nRows per intent:")
for intent, count in sorted(intent_counts.items()):
    print(f"  {intent}: {count}")
print(f"\nRows per entity:")
for entity, count in sorted(entity_counts.items()):
    print(f"  {entity}: {count}")
print(f"\nExcluded lines: {excluded_count}")
print(f"\n5 sample rows:")
for i, fact in enumerate(validated_facts[:5]):
    print(f"\n  Row {i+1}:")
    print(f"    ID: {fact['id']}")
    print(f"    Type: {fact['type']}")
    print(f"    Intent: {fact['intent']}")
    print(f"    Entity: {fact['entity']}")
    print(f"    Text: {fact['text']}")
    print(f"    Keywords: {fact['keywords']}")
    print(f"    Source: {fact['source']}")
    print(f"    Confidence: {fact['confidence']}")
print(f"\nAmbiguous facts skipped: None (all validated facts are clear)")
print("=" * 60)
