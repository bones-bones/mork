from difflib import SequenceMatcher

import shared_vars

EXACT_MATCH_SCORE = 10_000_000


def cardNameRequest(requestName: str):
    print(f"cnr [{requestName}]")
    maxWeight = -1.0
    maxWeightName = ""
    for cardName in shared_vars.allCards.keys():
        currentWeight = similarity(cardName, requestName)
        if currentWeight > maxWeight or (
            currentWeight == maxWeight and len(cardName) < len(maxWeightName)
        ):
            maxWeight = currentWeight
            maxWeightName = cardName
    return maxWeightName


def _word_prefix_score(req_words: list[str], name_words: list[str]) -> float:
    """Score how well request words match name words in order (prefix ok)."""
    if not req_words:
        return 0.0
    score = 0.0
    name_index = 0
    for req_word in req_words:
        found = False
        while name_index < len(name_words):
            name_word = name_words[name_index]
            name_index += 1
            if name_word == req_word:
                score += 3
                found = True
                break
            if name_word.startswith(req_word) or req_word.startswith(name_word):
                overlap = min(len(req_word), len(name_word)) / max(
                    len(req_word), len(name_word)
                )
                score += 2 * overlap
                found = True
                break
            if req_word in name_word or name_word in req_word:
                overlap = min(len(req_word), len(name_word)) / max(
                    len(req_word), len(name_word)
                )
                score += overlap
                found = True
                break
        if not found:
            score -= 1
    return score / len(req_words)


def similarity(name: str, requestName: str) -> float:
    name_lower = name.lower()
    request_lower = requestName.lower()

    if name_lower == request_lower or name_lower + " " == request_lower:
        return EXACT_MATCH_SCORE

    ratio = SequenceMatcher(None, request_lower, name_lower).ratio()
    score = ratio * 1000

    if name_lower.startswith(request_lower):
        score += 500 * (len(request_lower) / len(name_lower))
    elif request_lower.startswith(name_lower):
        score += 300 * (len(name_lower) / len(request_lower))

    if request_lower in name_lower:
        score += 400 * (len(request_lower) / len(name_lower))
    elif name_lower in request_lower:
        score += 300 * (len(name_lower) / len(request_lower))

    score += _word_prefix_score(request_lower.split(), name_lower.split()) * 200

    length_ratio = min(len(request_lower), len(name_lower)) / max(
        len(request_lower), len(name_lower)
    )
    score *= length_ratio**0.3

    return score
