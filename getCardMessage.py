def parseCardNameAndAuthor(acceptanceMessage: str) -> tuple[str, str]:
    dbname = ""
    card_author = ""
    if (len(acceptanceMessage)) == 0 or ("by " not in acceptanceMessage):
        ...  # This is really the case of setting both to "", but due to scoping i got lazy
    elif acceptanceMessage[0:3] == "by ":
        card_author = str((acceptanceMessage.split("by "))[1])
    else:
        firstPart, secondPart = acceptanceMessage.rsplit(" by ", 1)
        dbname = str(firstPart)
        card_author = str(secondPart)

    return dbname, card_author


def getCardMessage(acceptanceMessage: str):
    dbname, card_author = parseCardNameAndAuthor(acceptanceMessage)

    resolvedName = dbname if dbname != "" else "Crazy card with no name"
    resolvedAuthor = card_author if card_author != "" else "no author"

    return f"**{resolvedName}** by **{resolvedAuthor}**"
