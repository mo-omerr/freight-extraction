# prompts.py
"""
Prompt versions with evolution tracking
"""
from enum import Enum


class PromptVersion(Enum):
    V1 = "v1_basic_extraction"
    V2 = "v2_business_rules"
    V3 = "v3_structured_reasoning"
    V4 = "v4_final"


def get_prompt(version: PromptVersion, email_data: dict) -> str:
    """Get prompt by version"""
    
    if version == PromptVersion.V1:
        return get_v1_prompt(email_data)
    elif version == PromptVersion.V2:
        return get_v2_prompt(email_data)
    elif version == PromptVersion.V3:
        return get_v3_prompt(email_data)
    elif version == PromptVersion.V4:
        return get_v4_prompt(email_data)


def get_v1_prompt(email: dict) -> str:
    """V1: Basic extraction"""
    return f"""You are a freight forwarding expert. Extract shipment details from this email.

Email Subject: {email['subject']}
Email Body: {email['body']}

Extract these fields and return ONLY valid JSON:

{{
  "origin_port": "origin city/port name or code",
  "destination_port": "destination city/port name or code",
  "incoterm": "shipping terms (FOB, CIF, etc.) or null",
  "cargo_weight_text": "weight as written or null",
  "cargo_cbm_text": "volume as written or null",
  "dangerous_goods_mentioned": "YES, NO, or NOT_MENTIONED",
  "is_import_to_india": true/false,
  "is_export_from_india": true/false
}}

Return ONLY the JSON, no other text."""


def get_v2_prompt(email: dict) -> str:
    """V2: Add business rules"""
    return f"""You are a freight forwarding expert. Extract shipment details from this email.

Email Subject: {email['subject']}
Email Body: {email['body']}

IMPORTANT RULES:
1. If subject and body conflict, use information from BODY
2. If multiple shipments mentioned, extract only the FIRST shipment
3. For incoterm: Extract exactly as written, or null if not mentioned
4. For dangerous goods:
   - If "non-DG" or "non-hazardous" or "not dangerous" → "NO"
   - If "DG" or "dangerous" or "Class X" or "IMO" or "UN XXXX" → "YES"
   - Otherwise → "NOT_MENTIONED"
5. Extract ports as written (don't convert yet)
6. Indian ports: Chennai, Mumbai, Bangalore, Nhava Sheva, Hyderabad, Delhi, etc.

Extract these fields and return ONLY valid JSON:

{{
  "origin_port": "origin city/port name or code",
  "destination_port": "destination city/port name or code",
  "incoterm": "shipping terms or null",
  "cargo_weight_text": "weight as written or null",
  "cargo_cbm_text": "volume as written or null",
  "dangerous_goods_mentioned": "YES, NO, or NOT_MENTIONED",
  "is_import_to_india": true/false,
  "is_export_from_india": true/false
}}

Return ONLY the JSON, no other text."""


def get_v3_prompt(email: dict) -> str:
    """V3: Add structured reasoning"""
    return f"""You are a freight forwarding expert. Extract shipment details from this email.

Email Subject: {email['subject']}
Email Body: {email['body']}

CRITICAL RULES:
1. If subject and body conflict, ALWAYS use BODY information
2. If multiple shipments mentioned, extract only the FIRST shipment
3. Indian ports include: Chennai (MAA), Mumbai (BOM), Bangalore (BLR), Nhava Sheva, Hyderabad (HYD), Delhi (DEL)
4. Check if this is IMPORT to India or EXPORT from India based on port locations

DANGEROUS GOODS (check in this order):
1. FIRST check for negations: "non-DG", "non-hazardous", "not dangerous" → "NO"
2. THEN check for positive: "DG", "dangerous", "Class X", "IMO", "IMDG", "UN XXXX" → "YES"
3. If no mention → "NOT_MENTIONED"

PORT ABBREVIATIONS:
- SHA = Shanghai
- MAA = Chennai
- HK = Hong Kong
- SIN = Singapore
- BLR = Bangalore
- BOM = Mumbai
- BKK = Bangkok
- SUB = Surabaya
- JED/DAM/RUH = Saudi Arabia

Extract these fields and return ONLY valid JSON:

{{
  "origin_port": "origin city/port/code",
  "destination_port": "destination city/port/code",
  "incoterm": "terms or null",
  "cargo_weight_text": "weight with unit or null",
  "cargo_cbm_text": "volume or null",
  "dangerous_goods_mentioned": "YES, NO, or NOT_MENTIONED",
  "is_import_to_india": true/false,
  "is_export_from_india": true/false
}}

Return ONLY the JSON, no other text."""


def get_v4_prompt(email: dict) -> str:
    """V4: Final optimized prompt"""
    return f"""Extract shipment details from this freight forwarding email.

Subject: {email['subject']}
Body: {email['body']}

EXTRACTION RULES:
1. BODY takes precedence over subject if they conflict
2. Extract FIRST shipment only if multiple mentioned
3. Indian ports: Chennai/MAA, Mumbai/BOM, Bangalore/BLR, Nhava Sheva, Hyderabad/HYD, Whitefield/WFD
4. Port abbreviations: SHA=Shanghai, HK=Hong Kong, SIN=Singapore, BKK=Bangkok, SUB=Surabaya, JED/DAM/RUH=Saudi

DANGEROUS GOODS (check in order):
1. Negations ("non-DG", "non-hazardous", "not dangerous") → "NO"
2. Positive ("DG", "dangerous", "Class X", "IMO", "UN XXXX", "flammable") → "YES"  
3. No mention → "NOT_MENTIONED"

INCOTERM: Extract exactly as written (FOB, CIF, FCA, etc.) or null if not mentioned

WEIGHT & VOLUME:
- Extract as written including units (e.g., "1,980 KGS", "500 lbs", "3.8 CBM", "3 RT")
- If dimensions only (L×W×H), extract as null for CBM
- "TBD" or "N/A" → null

Return ONLY this JSON:
{{
  "origin_port": "port name/code",
  "destination_port": "port name/code",
  "incoterm": "terms or null",
  "cargo_weight_text": "weight or null",
  "cargo_cbm_text": "cbm or null",
  "dangerous_goods_mentioned": "YES/NO/NOT_MENTIONED",
  "is_import_to_india": true/false,
  "is_export_from_india": true/false
}}"""