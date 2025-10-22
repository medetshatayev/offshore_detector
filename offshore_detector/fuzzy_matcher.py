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
    """
    normalized_text = normalize_text(text)
    if not normalized_text:
        return []

    matches = []

    for target in targets:
        normalized_target = normalize_text(target)
        if not normalized_target:
            continue

        target_tokens = [t for t in normalized_target.split() if t not in STOPWORDS and len(t) >= 3]
        text_tokens = [t for t in normalized_text.split() if t not in STOPWORDS and len(t) >= 3]

        # 1. Exact substring match of the whole normalized target
        if normalized_target in normalized_text and len(target_tokens) >= 1:
            matches.append({'match': target, 'similarity': 1.0})
            continue

        # 2. Token-level exact matches (require >=2 distinct token hits for multi-word targets)
        if target_tokens:
            hits = len(set(target_tokens) & set(text_tokens))
            if (len(target_tokens) == 1 and hits >= 1) or (len(target_tokens) > 1 and hits >= 2):
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
        else: # For longer strings, check token-wise similarity requiring multiple supporting tokens
            if not text_tokens or not target_tokens:
                continue

            sims = []
            for tar_tok in set(target_tokens):
                best = 0
                for txt_tok in set(text_tokens):
                    max_len = max(len(txt_tok), len(tar_tok))
                    if max_len == 0:
                        continue
                    lev_dist = distance(txt_tok, tar_tok)
                    sim = 1 - (lev_dist / max_len)
                    if sim > best:
                        best = sim
                sims.append(best)

            # Require at least two target tokens to meet threshold for multi-word targets
            strong_hits = sum(1 for s in sims if s >= threshold)
            if (len(target_tokens) == 1 and strong_hits >= 1) or (len(target_tokens) > 1 and strong_hits >= 2):
                matches.append({'match': target, 'similarity': sum(sims)/len(sims) if sims else threshold})

    # Return top 5 unique matches sorted by similarity
    unique_matches = {m['match']: m for m in matches}
    sorted_matches = sorted(unique_matches.values(), key=lambda x: x['similarity'], reverse=True)
    
    return sorted_matches[:5]
