from collections.abc import Iterable
from difflib import SequenceMatcher


def _word_prefix_score(req_words: list[str], name_words: list[str]) -> float:
    """Score how well request words match name words in order (prefix ok)."""
    if not req_words:
        return 0.0
    score = 0.0
    for req_word in req_words:
        found = False
        for i in range(len(name_words)):
            name_word = name_words[i]
            if req_word in name_word or name_word in req_word:
                overlap = (
                    1
                    if name_word == req_word
                    else min(len(req_word), len(name_word)) / max(len(req_word), len(name_word))
                )
                mult = (
                    3
                    if overlap == 1
                    else 2
                    if (name_word.startswith(req_word) or req_word.startswith(name_word))
                    else 1
                )
                score += mult * overlap
                found = True
                break
        if not found:
            score -= 1
    return score / len(req_words)


def similarity(name: str, request: str) -> float:

    ratio = SequenceMatcher(None, request, name).ratio()
    score = ratio * 1000

    if name.startswith(request):
        score += 500 * (len(request) / len(name))
    elif request.startswith(name):
        score += 300 * (len(name) / len(request))

    if request in name:
        score += 400 * (len(request) / len(name))
    elif name in request:
        score += 300 * (len(name) / len(request))

    score += _word_prefix_score(request.split(), name.split()) * 200

    score *= min(len(request), len(name)) / max(len(request), len(name)) ** 0.3

    return score


def get_closest_name(requestName: str, allNames: Iterable[str]):
    print(f"cnr [{requestName}]")
    maxWeight = -1.0
    maxWeightName = ""
    for cardName in allNames:
        currentWeight = similarity(cardName, requestName)
        if currentWeight > maxWeight or (
            currentWeight == maxWeight and len(cardName) < len(maxWeightName)
        ):
            maxWeight = currentWeight
            maxWeightName = cardName
    return maxWeightName
