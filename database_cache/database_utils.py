import re
import unicodedata


def normalizeText(text: str):
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[\u0300-\u036f]", "", text)
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"[“”]", '"', text)
    text = re.sub(r" {2,}", " ", text)
    return text


delimiterList = [
    "**",  # bold
    "__",  # underline
    "~~",  # strikethrough
    "*",  # italics
    "_",  # italics
]

escapeRegex = re.compile(r"[*_~()\\]")


def textPrep(text: str) -> str:
    if not text:
        return text
    result: list[str] = []
    i = 0

    def foundDelimiter(delimiter: str):
        nonlocal i
        if not text.startswith(delimiter, i) or i + len(delimiter) >= len(text):
            return False
        try:
            end = text.index(delimiter, i + len(delimiter))
            result.append(textPrep(text[i + len(delimiter) : end]))
            i = end + 2
            return True
        except ValueError:
            return False

    while i < len(text):
        if i == 0 and not escapeRegex.match(text[i]):
            break
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] in "*_()\\":
            result.append(text[i + 1])
            i += 2
            continue
        if any(foundDelimiter(delimiter) for delimiter in delimiterList):
            continue
        result.append(text[i])
        i += 1
    return normalizeText("".join(result) if result else text).lower()


def fixName(text: str):
    return textPrep(text.strip())
