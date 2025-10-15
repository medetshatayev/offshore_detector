"""
Web research functionality using external APIs.
"""
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
import urllib.parse
import logging
from bs4 import BeautifulSoup

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
    """
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
        
        return links[:3] # Return top 3 results
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
    """
    try:
        return asyncio.run(run_web_research(counterparty_name, bank_name))
    except RuntimeError: # For environments where an event loop is already running (like Jupyter)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(run_web_research(counterparty_name, bank_name))
