"""
Simple fuzzy matching for country codes, country names, and cities.
Uses Levenshtein distance with a strict threshold (0.80).
ONLY matches against the offshore jurisdictions list.
"""
import logging
from typing import Optional, List
from Levenshtein import distance
from prompts import load_offshore_jurisdictions


# Cache offshore jurisdictions
_OFFSHORE_JURISDICTIONS: Optional[List[dict]] = None


def _get_offshore_jurisdictions() -> List[dict]:
    """Get cached offshore jurisdictions list."""
    global _OFFSHORE_JURISDICTIONS
    
    if _OFFSHORE_JURISDICTIONS is None:
        _OFFSHORE_JURISDICTIONS = load_offshore_jurisdictions()
        logging.info(f"Loaded {len(_OFFSHORE_JURISDICTIONS)} offshore jurisdictions for matching")
    
    return _OFFSHORE_JURISDICTIONS


def normalize_string(s: str) -> str:
    """
    Normalize string for comparison: lowercase, strip, remove extra spaces.
    
    Args:
        s: Input string
    
    Returns:
        Normalized string
    """
    if not s or not isinstance(s, str):
        return ""
    
    # Lowercase and strip
    normalized = s.lower().strip()
    
    # Remove multiple spaces
    normalized = " ".join(normalized.split())
    
    return normalized


def simple_fuzzy_match(
    text: str, 
    targets: List[str], 
    threshold: float = 0.80
) -> Optional[dict]:
    """
    Simple fuzzy matching using Levenshtein distance.
    Returns the best match if similarity >= threshold.
    
    For short strings (< 20 chars), uses full string comparison.
    
    Args:
        text: Text to match
        targets: List of target strings to match against
        threshold: Minimum similarity score (default 0.80)
    
    Returns:
        Dict with 'value' and 'score' if match found, None otherwise
    """
    if not text or not targets:
        return None
    
    text_norm = normalize_string(text)
    if not text_norm:
        return None
    
    best_match = None
    best_score = 0.0
    
    for target in targets:
        target_norm = normalize_string(target)
        if not target_norm:
            continue
        
        # Exact substring match (case-insensitive)
        if target_norm in text_norm or text_norm in target_norm:
            return {'value': target, 'score': 1.0}
        
        # Fuzzy match for short strings (< 20 chars)
        if len(text_norm) < 20 or len(target_norm) < 20:
            max_len = max(len(text_norm), len(target_norm))
            if max_len == 0:
                continue
            
            lev_dist = distance(text_norm, target_norm)
            similarity = 1.0 - (lev_dist / max_len)
            
            if similarity >= threshold and similarity > best_score:
                best_score = similarity
                best_match = target
    
    if best_match:
        return {'value': best_match, 'score': best_score}
    
    return None


def match_country_code(country_code: str) -> Optional[dict]:
    """
    Match country code (2-letter or 3-letter) against offshore jurisdictions.
    
    Args:
        country_code: Country code to match
    
    Returns:
        Dict with 'value' and 'score' if matched, None otherwise
    """
    if not country_code:
        return None
    
    jurisdictions = _get_offshore_jurisdictions()
    
    # Build list of all codes (both 2-letter and 3-letter)
    target_codes = []
    for j in jurisdictions:
        if j.get('code2'):
            target_codes.append(j['code2'])
        if j.get('code3'):
            target_codes.append(j['code3'])
    
    return simple_fuzzy_match(country_code, target_codes, threshold=0.80)


def match_country_name(country_name: str) -> Optional[dict]:
    """
    Match country name against offshore jurisdictions.
    
    Args:
        country_name: Country name to match
    
    Returns:
        Dict with 'value' and 'score' if matched, None otherwise
    """
    if not country_name:
        return None
    
    jurisdictions = _get_offshore_jurisdictions()
    target_names = [j['name'] for j in jurisdictions if j.get('name')]
    
    return simple_fuzzy_match(country_name, target_names, threshold=0.80)


def match_city(city: str) -> Optional[dict]:
    """
    Match city name against offshore jurisdiction names.
    
    Note: Cities aren't explicitly in the offshore list, but some jurisdiction
    names could match city-states (e.g., Monaco, Singapore, Hong Kong).
    
    Args:
        city: City name to match
    
    Returns:
        Dict with 'value' and 'score' if matched, None otherwise
    """
    if not city:
        return None
    
    jurisdictions = _get_offshore_jurisdictions()
    # Use jurisdiction names as potential city matches
    target_names = [j['name'] for j in jurisdictions if j.get('name')]
    
    return simple_fuzzy_match(city, target_names, threshold=0.80)


def get_all_matches(
    country_code: Optional[str] = None,
    country_name: Optional[str] = None,
    city: Optional[str] = None
) -> dict:
    """
    Get all matching signals for a transaction's fields.
    
    Args:
        country_code: Country code field from transaction
        country_name: Country name field from transaction
        city: City field from transaction
    
    Returns:
        Dict with 'country_code_match', 'country_name_match', 'city_match'
    """
    return {
        'country_code_match': match_country_code(country_code) if country_code else None,
        'country_name_match': match_country_name(country_name) if country_name else None,
        'city_match': match_city(city) if city else None
    }
