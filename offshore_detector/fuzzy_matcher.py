"""
Fuzzy string matching using Levenshtein distance.
"""
from Levenshtein import distance
import re
from typing import List, Dict

def normalize_text(text: str) -> str:
    """
    Lowercase, remove punctuation, and trim spaces.
    """
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

def fuzzy_match(text: str, targets: List[str], threshold: float = 0.8) -> List[Dict]:
    """
    Returns matches with similarity score using multiple strategies.
    """
    normalized_text = normalize_text(text)
    if not normalized_text:
        return []

    matches = []

    for target in targets:
        normalized_target = normalize_text(target)
        if not normalized_target:
            continue

        # 1. Exact substring match
        if normalized_target in normalized_text:
            matches.append({'match': target, 'similarity': 1.0})
            continue

        # 2. Token-level exact match
        if any(token in normalized_text.split() for token in normalized_target.split()):
            matches.append({'match': target, 'similarity': 0.95})
            continue

        # 3. Character-level fuzzy match (Levenshtein)
        # 4. Full string fuzzy for short strings
        if len(normalized_text) < 20 or len(normalized_target) < 20:
            max_len = max(len(normalized_text), len(normalized_target))
            if max_len == 0:
                continue
            lev_dist = distance(normalized_text, normalized_target)
            similarity = 1 - (lev_dist / max_len)
            if similarity >= threshold:
                matches.append({'match': target, 'similarity': similarity})
        else: # For longer strings, check token-wise similarity
            text_tokens = set(normalized_text.split())
            target_tokens = set(normalized_target.split())
            
            if not text_tokens or not target_tokens:
                continue

            max_sim = 0
            for txt_tok in text_tokens:
                for tar_tok in target_tokens:
                    max_len = max(len(txt_tok), len(tar_tok))
                    if max_len == 0:
                        continue
                    lev_dist = distance(txt_tok, tar_tok)
                    sim = 1 - (lev_dist / max_len)
                    if sim > max_sim:
                        max_sim = sim
            
            if max_sim >= threshold:
                matches.append({'match': target, 'similarity': max_sim})

    # Return top 5 unique matches sorted by similarity
    unique_matches = {m['match']: m for m in matches}
    sorted_matches = sorted(unique_matches.values(), key=lambda x: x['similarity'], reverse=True)
    
    return sorted_matches[:5]
