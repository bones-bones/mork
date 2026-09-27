def submission_card_name(content: str) -> str:
    return (content or "").strip().split("\n", 1)[0].strip()


def parseCardNameAndAuthor(acceptanceMessage: str) -> tuple[str, str]:
    message = acceptanceMessage or ""
    if not message:
        return "", ""
    if message.startswith("by "):
        return "", str(message.split("by ", 1)[1])
    if " by " in message:
        firstPart, secondPart = message.rsplit(" by ", 1)
        return str(firstPart), str(secondPart)
    return message, ""


def get_card_message(acceptanceMessage: str):
    dbname, card_author = parseCardNameAndAuthor(acceptanceMessage)

    resolvedName = dbname if dbname != "" else "Crazy card with no name"
    resolvedAuthor = card_author if card_author != "" else "no author"

    return f"**{resolvedName}** by **{resolvedAuthor}**"
