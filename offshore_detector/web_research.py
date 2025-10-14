"""
Web research functionality using external APIs.
"""
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
import urllib.parse
import logging

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
def geocode_bank(bank_name):
    """
    Geocode bank name using OpenStreetMap Nominatim.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': bank_name[:100],
        'format': 'json',
        'limit': 1
    }
    headers = {
        'User-Agent': 'offshore-detection/1.0 (your-email@example.com)',
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
    """
    query = f"{counterparty_name} {bank_name} offshore tax haven"[:100]
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num=3"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        # Basic parsing to find links. A more robust solution would use a library like BeautifulSoup.
        links = [line.split('href="')[1].split('"')[0] for line in response.text.splitlines() if 'href="/url?q=' in line]
        return links
    except requests.RequestException as e:
        logging.error(f"Google search request failed: {e}")
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
    """
    try:
        return asyncio.run(run_web_research(counterparty_name, bank_name))
    except RuntimeError: # For environments where an event loop is already running (like Jupyter)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(run_web_research(counterparty_name, bank_name))
