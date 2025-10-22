"""
Web research functionality using external APIs.
"""
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
import urllib.parse
import logging
from bs4 import BeautifulSoup
from functools import lru_cache
import hashlib
import time
import threading

# Simple cache for search results (since they return lists which are not hashable)
_search_cache = {}

# Rate limiting: Track last request time
_last_request_time = {'geocode': 0.0, 'search': 0.0}
_rate_limit_lock = threading.Lock()

def rate_limit(service, min_interval=1.0):
    """
    Simple rate limiter to avoid overwhelming external APIs.
    """
    with _rate_limit_lock:
        elapsed = time.time() - _last_request_time.get(service, 0.0)
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time[service] = time.time()

@lru_cache(maxsize=500)  # Cache up to 500 unique bank lookups
@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
def geocode_bank(bank_name):
    """
    Geocode bank name using OpenStreetMap Nominatim.
    Performance: Cached to avoid redundant API calls. Rate-limited to respect API usage policies.
    """
    if not bank_name:
        return None
    
    rate_limit('geocode', min_interval=1.0)  # Nominatim requires 1 req/sec max
    
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': bank_name[:100],
        'format': 'json',
        'limit': 1
    }
    headers = {
        'User-Agent': 'OffshoreDetector/1.0 (mshatayev@gmail.com)',
        'Accept': 'application/json'
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=8)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Geocoding request failed: {e}")
        return None

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
def google_search(counterparty_name, bank_name):
    """
    Perform a Google search for offshore indicators.
    This function scrapes Google search results and is not 100% reliable.
    For production use, consider a dedicated search API.
    Performance: Cached to avoid redundant searches.
    """
    # Create cache key
    cache_key = f"{counterparty_name}:{bank_name}"
    if cache_key in _search_cache:
        return _search_cache[cache_key]
    
    rate_limit('search', min_interval=2.0)  # Rate limit Google searches
    
    query = f"{counterparty_name} {bank_name} offshore tax haven"[:100]
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num=3"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if href.startswith('/url?q='):
                # Extract the actual URL from the Google redirect link
                clean_link = href.split('/url?q=')[1].split('&sa=U')[0]
                links.append(urllib.parse.unquote(clean_link))
        
        result = links[:3] if links else None  # Return top 3 results
        
        # Cache result (limit cache size)
        if len(_search_cache) > 500:
            _search_cache.clear()
        _search_cache[cache_key] = result
        
        return result
    except requests.RequestException as e:
        logging.error(f"Google search request failed: {e}")
        return None
    except Exception as e:
        logging.error(f"Error parsing Google search results: {e}")
        return None

async def run_web_research(counterparty_name, bank_name):
    """
    Run geocoding and Google search concurrently.
    """
    loop = asyncio.get_event_loop()
    
    geocode_task = loop.run_in_executor(None, geocode_bank, bank_name)
    search_task = loop.run_in_executor(None, google_search, counterparty_name, bank_name)
    
    geocode_result = await geocode_task
    search_result = await search_task
    
    return {
        "geocoding": geocode_result,
        "search_results": search_result
    }

def parallel_web_research(counterparty_name, bank_name):
    """
    Entry point for parallel web research.
    Fixed: Proper event loop handling for all contexts.
    """
    try:
        # Try to get the running loop
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create a new one
        try:
            return asyncio.run(run_web_research(counterparty_name, bank_name))
        except Exception as e:
            logging.error(f"Error in web research: {e}")
            return {"geocoding": None, "search_results": None}
    else:
        # Loop is already running (e.g., in Jupyter), use run_in_executor
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, run_web_research(counterparty_name, bank_name))
            try:
                return future.result(timeout=30)
            except Exception as e:
                logging.error(f"Error in web research: {e}")
                return {"geocoding": None, "search_results": None}
