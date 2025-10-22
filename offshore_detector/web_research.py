"""
Geo search (OpenStreetMap Nominatim)
Logs geocoding responses for observability and normalizes bank query.

Security improvements:
- Removed hardcoded sensitive information
- Added input validation and sanitization
- Limited response size to prevent DoS
- Validated URL parameters

Performance improvements:
- Uses async HTTP client (aiohttp)
- Non-blocking rate limiting
- Optimized caching strategy
- Simplified event loop handling

Logic improvements:
- Fixed caching with multiple parameters
- Removed unused variables
- Better error handling
- Improved code organization
"""
import asyncio
import logging
import re
import time
import json
from typing import Optional, Dict, Any, Tuple
from functools import wraps

try:
    import aiohttp
except ImportError:
    # Fallback to requests if aiohttp is not available
    import requests
    aiohttp = None

from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

from .config import (
    GEOCODING_USER_AGENT,
    GEOCODING_TIMEOUT,
    GEOCODING_RATE_LIMIT,
    GEOCODING_CACHE_SIZE,
    GEOCODING_MAX_RETRIES,
    GEOCODING_MAX_RESPONSE_SIZE
)

# Cache for geocoding results - key is tuple of (normalized_bank_name, country_code)
_geocoding_cache: Dict[Tuple[str, Optional[str]], Any] = {}
_cache_lock = asyncio.Lock()

# Rate limiting: Track last request time per service
_last_request_time: Dict[str, float] = {}
_rate_limit_lock = asyncio.Lock()


def validate_input(value: Any, max_length: int = 1000) -> Optional[str]:
    """
    Validate and sanitize input strings.
    
    Security: Prevents injection attacks and malformed inputs.
    """
    if not value:
        return None
    
    if not isinstance(value, str):
        value = str(value)
    
    # Remove null bytes and control characters
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    
    # Limit length
    value = value.strip()[:max_length]
    
    return value if value else None


def validate_country_code(code: Optional[str]) -> Optional[str]:
    """
    Validate ISO 3166-1 alpha-2 country code.
    
    Security: Ensures only valid country codes are used in API calls.
    """
    if not code:
        return None
    
    if not isinstance(code, str):
        return None
    
    code = code.strip().upper()
    
    # Must be exactly 2 alphabetic characters
    if len(code) == 2 and code.isalpha():
        return code
    
    return None


async def async_rate_limit(service: str, min_interval: float = GEOCODING_RATE_LIMIT):
    """
    Non-blocking rate limiter for external API calls.
    
    Performance: Uses async sleep instead of blocking sleep.
    """
    async with _rate_limit_lock:
        last_time = _last_request_time.get(service, 0.0)
        elapsed = time.time() - last_time
        
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        
        _last_request_time[service] = time.time()


def normalize_bank_query(name: str) -> str:
    """
    Normalize bank name for geocoding query.
    
    Logic improvements:
    - More robust line selection
    - Better handling of edge cases
    - Clearer logic flow
    """
    if not isinstance(name, str) or not name.strip():
        return ""
    
    # Replace path separators with spaces
    raw = name.replace("/", " ").replace("\\", " ")
    
    # Split into lines and filter empty ones
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    
    if not lines:
        return ""
    
    # Keyword pattern for bank-related terms
    keyword_re = re.compile(r"\b(bank|банк|банка|credit|union)\b", re.IGNORECASE)
    
    # Prefer a line containing bank keywords
    candidate = None
    for ln in lines:
        if keyword_re.search(ln):
            candidate = ln
            break
    
    # Fallback: pick line with highest alphabetic ratio
    if candidate is None:
        def alpha_ratio(s: str) -> float:
            letters = sum(ch.isalpha() for ch in s)
            total = len(s)
            return letters / max(1, total)
        
        candidate = max(lines, key=alpha_ratio)
    
    # Extract core name
    s = candidate
    
    # Take part before first comma (often separates name from address)
    s = s.split(',')[0].strip()
    
    # Remove common address patterns
    address_pattern = r"\b(floor|fl|avenue|ave|road|rd|street|st|bldg|building|no\.?|№|suite|ste|unit)\b.*$"
    s = re.sub(address_pattern, "", s, flags=re.IGNORECASE).strip()
    
    # Handle parentheses - remove if not containing bank keywords
    paren_match = re.search(r"\(([^)]*)\)$", s)
    if paren_match and not keyword_re.search(paren_match.group(1)):
        s = re.sub(r"\([^)]*\)$", "", s).strip()
    
    # Remove trailing standalone numbers
    s = re.sub(r"\s+\d+$", "", s).strip()
    
    # Collapse multiple spaces
    s = re.sub(r"\s+", " ", s)
    
    # Remove leading non-word characters
    s = re.sub(r"^[\W_]+", "", s)
    
    # Ensure we have something
    if not s and lines:
        s = lines[0][:80]
    
    # Limit final length
    return s[:100].strip()


def extract_swift_country_code(swift_code: Optional[str]) -> Optional[str]:
    """
    Extract ISO country code from SWIFT/BIC code.
    
    SWIFT format: AAAABBCCXXX
    - AAAA: Bank code (4 characters)
    - BB: Country code (2 characters) - positions 4-5
    - CC: Location code (2 characters)
    - XXX: Branch code (3 characters, optional)
    
    Returns validated country code or None.
    """
    swift_code = validate_input(swift_code, max_length=11)
    if not swift_code:
        return None
    
    swift_code = swift_code.upper()
    
    # SWIFT codes are 8 or 11 characters
    if len(swift_code) not in (8, 11):
        return None
    
    # Extract country code (positions 4-5, 0-indexed)
    country_code = swift_code[4:6]
    
    return validate_country_code(country_code)


async def geocode_bank_async(
    bank_name: str,
    swift_country_code: Optional[str] = None
) -> Optional[list]:
    """
    Geocode bank name using OpenStreetMap Nominatim API.
    
    Performance: Async implementation with proper caching and rate limiting.
    Security: Input validation, response size limits, proper error handling.
    
    Args:
        bank_name: Name of the bank to geocode
        swift_country_code: Optional ISO 3166-1 alpha-2 country code
        
    Returns:
        List of geocoding results or None on error
    """
    # Validate and normalize inputs
    bank_name = validate_input(bank_name, max_length=500)
    if not bank_name:
        return None
    
    country_code = validate_country_code(swift_country_code)
    
    # Normalize query
    query = normalize_bank_query(bank_name)
    if not query:
        # Fallback to truncated original
        query = bank_name[:80]
    
    # Check cache
    cache_key = (query, country_code)
    async with _cache_lock:
        if cache_key in _geocoding_cache:
            logging.debug("Cache hit for bank='%s', country='%s'", query, country_code)
            return _geocoding_cache[cache_key]
    
    # Rate limit
    await async_rate_limit('geocode', GEOCODING_RATE_LIMIT)
    
    # Prepare request
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': query,
        'format': 'json',
        'limit': 2
    }
    
    if country_code:
        params['countrycodes'] = country_code.lower()
    
    headers = {
        'User-Agent': GEOCODING_USER_AGENT,
        'Accept': 'application/json'
    }
    
    try:
        logging.info(
            "Geocoding request: q='%s'%s",
            query,
            f", countrycodes={country_code}" if country_code else ""
        )
        
        result = None
        
        if aiohttp:
            # Use async HTTP client
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=GEOCODING_TIMEOUT)
                ) as response:
                    response.raise_for_status()
                    
                    # Check response size
                    content_length = response.content_length
                    if content_length and content_length > GEOCODING_MAX_RESPONSE_SIZE:
                        logging.error("Response too large: %d bytes", content_length)
                        return None
                    
                    result = await response.json()
        else:
            # Fallback to synchronous requests
            import requests
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=GEOCODING_TIMEOUT
            )
            response.raise_for_status()
            
            # Check response size
            if len(response.content) > GEOCODING_MAX_RESPONSE_SIZE:
                logging.error("Response too large: %d bytes", len(response.content))
                return None
            
            result = response.json()
        
        # Log summary
        try:
            first = (result or [None])[0] or {}
            summary = {
                "bank": bank_name,
                "display_name": first.get("display_name"),
                "lat": first.get("lat"),
                "lon": first.get("lon"),
                "query": query,
                "countrycodes": country_code
            }
            logging.info("Geocoding summary: %s", json.dumps(summary, ensure_ascii=False))
        except Exception as e:
            logging.warning("Error logging geocoding summary: %s", e)
        
        # Cache result (limit cache size)
        async with _cache_lock:
            if len(_geocoding_cache) >= GEOCODING_CACHE_SIZE:
                # Remove oldest entry (first key)
                oldest_key = next(iter(_geocoding_cache))
                del _geocoding_cache[oldest_key]
            
            _geocoding_cache[cache_key] = result
        
        return result
        
    except asyncio.TimeoutError:
        logging.error("Geocoding request timeout for bank='%s'", bank_name)
        return None
    except Exception as e:
        logging.error("Geocoding request failed for bank='%s': %s", bank_name, str(e))
        return None


def geocode_bank_sync(
    bank_name: str,
    swift_country_code: Optional[str] = None
) -> Optional[list]:
    """
    Synchronous wrapper for geocode_bank_async.
    
    Used when called from synchronous context.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Cannot use asyncio.run in running loop
            # Create task and wait for it
            future = asyncio.ensure_future(
                geocode_bank_async(bank_name, swift_country_code)
            )
            # This is not ideal but needed for compatibility
            while not future.done():
                time.sleep(0.01)
            return future.result()
        else:
            return loop.run_until_complete(
                geocode_bank_async(bank_name, swift_country_code)
            )
    except RuntimeError:
        # No event loop
        return asyncio.run(geocode_bank_async(bank_name, swift_country_code))


async def run_web_research(
    counterparty_name: str,
    bank_name: str,
    swift_code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run geocoding research for a bank.
    
    Args:
        counterparty_name: Name of the counterparty
        bank_name: Name of the bank
        swift_code: Optional SWIFT/BIC code
        
    Returns:
        Dictionary with geocoding results
    """
    # Validate inputs
    counterparty_name = validate_input(counterparty_name, max_length=500)
    bank_name = validate_input(bank_name, max_length=500)
    swift_code = validate_input(swift_code, max_length=11)
    
    if not bank_name:
        logging.warning("No bank name provided for web research")
        return {"geocoding": None, "search_results": None}
    
    # Extract country code from SWIFT
    country_code = extract_swift_country_code(swift_code)
    
    # Run geocoding
    geocode_result = await geocode_bank_async(bank_name, country_code)
    
    # Log result
    try:
        first = (geocode_result or [None])[0] or {}
        display_name = first.get("display_name", "N/A")
        logging.info(
            "Web research completed: counterparty='%s', bank='%s' -> display_name='%s'",
            counterparty_name,
            bank_name,
            display_name
        )
    except Exception as e:
        logging.warning("Error logging web research result: %s", e)
    
    return {
        "geocoding": geocode_result,
        "search_results": None
    }


def parallel_web_research(
    counterparty_name: str,
    bank_name: str,
    swift_code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Entry point for web research from synchronous context.
    
    Handles event loop management automatically.
    
    Args:
        counterparty_name: Name of the counterparty
        bank_name: Name of the bank
        swift_code: Optional SWIFT/BIC code
        
    Returns:
        Dictionary with geocoding results
    """
    try:
        # Check if there's a running event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context with a running loop
            # Create a task and return a future
            logging.warning("parallel_web_research called from async context - this may cause issues")
            # Use run_in_executor to avoid blocking
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    run_web_research(counterparty_name, bank_name, swift_code)
                )
                return future.result(timeout=30)
        except RuntimeError:
            # No running loop - safe to use asyncio.run
            return asyncio.run(
                run_web_research(counterparty_name, bank_name, swift_code)
            )
    except Exception as e:
        logging.error("Error in web research: %s", str(e), exc_info=True)
        return {"geocoding": None, "search_results": None}


# Backward compatibility - keep old function name
geocode_bank = geocode_bank_sync
