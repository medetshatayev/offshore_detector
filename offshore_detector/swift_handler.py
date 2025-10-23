"""
SWIFT/BIC code handling and country extraction.
Extracts 2-letter country codes from SWIFT codes and checks against offshore list.
"""
import logging
from typing import Optional, Dict
from prompts import load_offshore_jurisdictions


# Cache offshore jurisdictions at module level
_OFFSHORE_MAP: Optional[Dict[str, str]] = None


def _get_offshore_map() -> Dict[str, str]:
    """
    Get cached mapping of country code (2-letter) to country name for offshore jurisdictions.
    
    Returns:
        Dict mapping code2 -> name for all offshore jurisdictions
    """
    global _OFFSHORE_MAP
    
    if _OFFSHORE_MAP is None:
        jurisdictions = load_offshore_jurisdictions()
        _OFFSHORE_MAP = {j['code2']: j['name'] for j in jurisdictions}
        logging.info(f"Loaded {len(_OFFSHORE_MAP)} offshore jurisdictions")
    
    return _OFFSHORE_MAP


def extract_swift_country(swift_code: str) -> Optional[Dict[str, any]]:
    """
    Extract country information from SWIFT/BIC code.
    
    SWIFT/BIC format: AAAA BB CC DDD
    - AAAA: Bank code (4 chars)
    - BB: Country code (2 chars, positions 4-5 in 0-indexed string)
    - CC: Location code (2 chars)
    - DDD: Branch code (3 chars, optional)
    
    Args:
        swift_code: SWIFT/BIC code string
    
    Returns:
        Dict with 'code', 'name', and 'is_offshore' if valid, None otherwise
    """
    if not swift_code or not isinstance(swift_code, str):
        return None
    
    # Clean and validate
    swift_clean = swift_code.strip().upper()
    
    # SWIFT codes must be 8 or 11 characters
    if len(swift_clean) not in (8, 11):
        logging.debug(f"Invalid SWIFT code length: {len(swift_clean)} (expected 8 or 11)")
        return None
    
    # Extract country code at positions 4:6 (0-indexed)
    country_code = swift_clean[4:6]
    
    # Validate it's alphabetic
    if not country_code.isalpha():
        logging.debug(f"Invalid country code in SWIFT '{swift_code}': {country_code}")
        return None
    
    # Check if it's in the offshore list
    offshore_map = _get_offshore_map()
    country_name = offshore_map.get(country_code)
    
    if country_name:
        # It's an offshore jurisdiction
        return {
            'code': country_code,
            'name': country_name,
            'is_offshore': True
        }
    else:
        # Not offshore, but we can still return the code for logging
        # (In production, you might want to have a full ISO 3166-1 alpha-2 mapping)
        return {
            'code': country_code,
            'name': None,  # Unknown country name (not in offshore list)
            'is_offshore': False
        }


def is_offshore_swift(swift_code: str) -> bool:
    """
    Quick check if a SWIFT code belongs to an offshore jurisdiction.
    
    Args:
        swift_code: SWIFT/BIC code string
    
    Returns:
        True if the SWIFT code's country is in the offshore list
    """
    result = extract_swift_country(swift_code)
    return result is not None and result.get('is_offshore', False)
