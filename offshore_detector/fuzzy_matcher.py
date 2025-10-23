"""
Fuzzy string matching using Levenshtein distance.
Hardened to reduce false positives on generic tokens and noisy long strings.
"""
from Levenshtein import distance
import re
from typing import List, Dict

STOPWORDS = {
    'and','the','of','company','co','ltd','limited','bank','trust','inc','corp','saint','st','islands','island',
    'llc','plc','spa','pt','a','an','hk','uae','u.a.e','ua','us','usa'
}

def normalize_text(text: str) -> str:
    """
    Lowercase, remove punctuation, and trim spaces.
    """
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    # collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def fuzzy_match(text: str, targets: List[str], threshold: float = 0.8) -> List[Dict]:
    """
    Returns matches with similarity score using multiple strategies.
    Optimized with early returns and efficient token comparison.
    """
    normalized_text = normalize_text(text)
    if not normalized_text:
        return []

    # Pre-tokenize text once for efficiency
    text_tokens = [t for t in normalized_text.split() if t not in STOPWORDS and len(t) >= 3]
    text_token_set = set(text_tokens)
    
    matches = []

    for target in targets:
        normalized_target = normalize_text(target)
        if not normalized_target:
            continue

        # Try different matching strategies in order of efficiency
        match_result = (
            _try_exact_match(normalized_text, normalized_target, target) or
            _try_token_match(text_token_set, normalized_target, target) or
            _try_fuzzy_match(normalized_text, normalized_target, text_tokens, target, threshold)
        )
        
        if match_result:
            matches.append(match_result)

    # Return top 5 unique matches sorted by similarity
    unique_matches = {m['match']: m for m in matches}
    sorted_matches = sorted(unique_matches.values(), key=lambda x: x['similarity'], reverse=True)
    
    return sorted_matches[:5]


def _try_exact_match(text, target, original_target):
    """Try exact substring match."""
    if target in text and len(target) >= 3:
        return {'match': original_target, 'similarity': 1.0}
    return None


def _try_token_match(text_token_set, target, original_target):
    """Try token-level exact matches."""
    target_tokens = [t for t in target.split() if t not in STOPWORDS and len(t) >= 3]
    if not target_tokens:
        return None
    
    target_token_set = set(target_tokens)
    hits = len(target_token_set & text_token_set)
    
    # Require at least 1 hit for single-word targets, 2 hits for multi-word
    if (len(target_tokens) == 1 and hits >= 1) or (len(target_tokens) > 1 and hits >= 2):
        return {'match': original_target, 'similarity': 0.95}
    return None


def _try_fuzzy_match(text, target, text_tokens, original_target, threshold):
    """Try character-level fuzzy matching with Levenshtein distance."""
    # For short strings, compare full strings
    if len(text) < 20 or len(target) < 20:
        max_len = max(len(text), len(target))
        if max_len == 0:
            return None
        
        lev_dist = distance(text, target)
        similarity = 1 - (lev_dist / max_len)
        if similarity >= threshold:
            return {'match': original_target, 'similarity': similarity}
    else:
        # For longer strings, use token-wise similarity
        target_tokens = [t for t in target.split() if t not in STOPWORDS and len(t) >= 3]
        if not text_tokens or not target_tokens:
            return None

        # Calculate best similarity for each target token
        sims = []
        for tar_tok in set(target_tokens):
            best = _best_token_similarity(tar_tok, set(text_tokens))
            sims.append(best)

        # Require at least two tokens to meet threshold for multi-word targets
        strong_hits = sum(1 for s in sims if s >= threshold)
        if (len(target_tokens) == 1 and strong_hits >= 1) or (len(target_tokens) > 1 and strong_hits >= 2):
            avg_similarity = sum(sims) / len(sims) if sims else threshold
            return {'match': original_target, 'similarity': avg_similarity}
    
    return None


def _best_token_similarity(target_token, text_token_set):
    """Find best similarity between a target token and text tokens."""
    best = 0.0
    for txt_tok in text_token_set:
        max_len = max(len(txt_tok), len(target_token))
        if max_len == 0:
            continue
        
        lev_dist = distance(txt_tok, target_token)
        sim = 1 - (lev_dist / max_len)
        if sim > best:
            best = sim
    return best
