"""
LLM prompt construction for offshore transaction classification.
Builds System Prompt A (offshore list) and System Prompt B (web_search permission).
"""
import os
import re
from typing import Tuple, List, Dict


def load_offshore_jurisdictions() -> List[Dict[str, str]]:
    """
    Load offshore jurisdictions from the markdown file.
    Parses the table and extracts CODE_STR, CODE_STR2, and ENGNAME.
    
    Returns:
        List of dicts with 'code3', 'code2', and 'name' keys
    """
    # Determine the path to offshore_countries.md
    current_dir = os.path.dirname(os.path.abspath(__file__))
    md_path = os.path.join(os.path.dirname(current_dir), 'docs', 'offshore_countries.md')
    
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"Offshore countries file not found at: {md_path}")
    
    jurisdictions = []
    
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Skip header lines and parse table rows
    in_table = False
    for line in lines:
        line = line.strip()
        
        # Detect table start
        if line.startswith('|') and 'LONGNAME' in line:
            in_table = True
            continue
        
        # Skip separator line
        if in_table and line.startswith('|:'):
            continue
        
        # Parse data rows
        if in_table and line.startswith('|'):
            # Split by | and clean up
            parts = [p.strip() for p in line.split('|')]
            # parts[0] is empty, parts[1] is LONGNAME, parts[2] is CODE_STR, etc.
            if len(parts) >= 5:
                try:
                    code3 = parts[2].strip()  # CODE_STR (3-letter)
                    code2 = parts[3].strip()  # CODE_STR2 (2-letter)
                    name = parts[4].strip()   # ENGNAME
                    
                    if code2 and name:  # Ensure we have at least code2 and name
                        jurisdictions.append({
                            'code3': code3,
                            'code2': code2,
                            'name': name
                        })
                except (IndexError, ValueError):
                    continue
    
    return jurisdictions


def build_system_prompt_a() -> str:
    """
    Build System Prompt A: Offshore jurisdictions list with instructions.
    Embeds the full offshore list from offshore_countries.md.
    
    Returns:
        Complete system prompt with embedded offshore jurisdictions
    """
    jurisdictions = load_offshore_jurisdictions()
    
    # Build the jurisdiction list as a formatted table
    jurisdiction_lines = []
    for j in jurisdictions:
        # Format: CODE2 – ENGNAME (we use code2 as it matches SWIFT country codes)
        jurisdiction_lines.append(f"  - {j['code2']} – {j['name']}")
    
    jurisdiction_text = "\n".join(jurisdiction_lines)
    
    prompt = f"""You are assessing whether a banking transaction involves an offshore jurisdiction for a Kazakhstani bank.

OFFSHORE JURISDICTIONS LIST:
The following jurisdictions are considered offshore for compliance purposes. Any match should be flagged:

{jurisdiction_text}

ANALYSIS RULES:
1. SWIFT/BIC country code (2-letter code at positions 5-6 of SWIFT code) is the strongest signal.
2. Use simple fuzzy matching only for short text: country code, country name, and city.
3. Do not overgeneralize. When evidence is weak or circumstantial, use OFFSHORE_SUSPECT.
4. When evidence is strong and direct (e.g., SWIFT code matches offshore jurisdiction), use OFFSHORE_YES.
5. When there is no credible offshore signal, use OFFSHORE_NO.

OUTPUT FORMAT:
You MUST respond with valid JSON matching this exact schema:
{{
  "transaction_id": "string or int or null",
  "direction": "incoming or outgoing",
  "amount_kzt": number,
  "signals": {{
    "swift_country_code": "string or null",
    "swift_country_name": "string or null",
    "is_offshore_by_swift": "boolean or null",
    "country_name_match": {{"value": "string or null", "score": "number or null"}},
    "country_code_match": {{"value": "string or null", "score": "number or null"}},
    "city_match": {{"value": "string or null", "score": "number or null"}}
  }},
  "classification": {{
    "label": "OFFSHORE_YES or OFFSHORE_SUSPECT or OFFSHORE_NO",
    "confidence": number between 0 and 1
  }},
  "reasoning_short_ru": "string (1-2 sentences in Russian explaining the decision)",
  "sources": ["array of URLs if web_search was used, empty array otherwise"],
  "llm_error": "string or null"
}}

Be precise, conservative, and always output valid JSON."""
    
    return prompt


def build_system_prompt_b() -> str:
    """
    Build System Prompt B: Web search permission and citation requirements.
    
    Returns:
        System prompt instructing LLM on web_search tool usage
    """
    prompt = """WEB SEARCH TOOL USAGE:

You have access to the web_search tool to verify information when needed:
- Use web_search to verify bank domicile, SWIFT code ownership, or regulatory lists
- Use web_search when a claim needs external validation
- Cite ALL sources used by including URLs in the 'sources' array
- Keep searches minimal and targeted (e.g., "bank name SWIFT code country")
- Never include screenshots or non-canonical sources
- If you don't use web_search, leave sources as an empty array []

CITATION REQUIREMENTS:
- Every URL in 'sources' must be a website you actually retrieved via web_search
- Sources should be authoritative (bank websites, regulators, SWIFT databases)
- Do not fabricate sources or include URLs you didn't access"""
    
    return prompt


def build_user_prompt(transaction_data: dict, local_signals: dict) -> str:
    """
    Build the user prompt with transaction data and local matching signals.
    
    Args:
        transaction_data: Dict with transaction fields
        local_signals: Dict with pre-computed local matching signals (SWIFT, fuzzy matches)
    
    Returns:
        Formatted user prompt as JSON string
    """
    import json
    
    payload = {
        "transaction": transaction_data,
        "local_signals": local_signals,
        "instruction": (
            "Analyze this transaction for offshore jurisdiction involvement. "
            "Use web_search if you need to verify any information. "
            "Return valid JSON only, matching the schema exactly."
        )
    }
    
    return json.dumps(payload, ensure_ascii=False, indent=2)


# Cache prompts at module level to avoid repeated file I/O
_SYSTEM_PROMPT_A = None
_SYSTEM_PROMPT_B = None


def get_system_prompts() -> Tuple[str, str]:
    """
    Get both system prompts, using cached versions if available.
    
    Returns:
        Tuple of (System Prompt A, System Prompt B)
    """
    global _SYSTEM_PROMPT_A, _SYSTEM_PROMPT_B
    
    if _SYSTEM_PROMPT_A is None:
        _SYSTEM_PROMPT_A = build_system_prompt_a()
    
    if _SYSTEM_PROMPT_B is None:
        _SYSTEM_PROMPT_B = build_system_prompt_b()
    
    return _SYSTEM_PROMPT_A, _SYSTEM_PROMPT_B
