from typing import Type


class Card:
    def __init__(self, name, img, creator):
        self._name = name
        self._img = img
        self._creator = creator

    def getName(self):
        return self._name

    def getImg(self):
        return self._img

    def getCreator(self):
        return self._creator


class Side:
    def __init__(
        self,
        cost: str,
        supertypes: list[str],
        types: list[str],
        subtypes: list[str],
        power: int,
        toughness: int,
        loyalty: int,
        text: str,
        flavor: str,
    ):
        self._cost = cost
        self._supertypes = supertypes
        self._types = types
        self._subtypes = subtypes
        self._power = power
        self._toughness = toughness
        self._loyalty = loyalty
        self._text = text
        self._flavor = flavor

    def cost(self):
        return self._cost

    def types(self):
        return self._supertypes + self._types + self._subtypes

    def power(self):
        return self._power

    def toughness(self):
        return self._toughness

    def loyalty(self):
        return self._loyalty

    def text(self):
        return self._text

    def flavor(self):
        return self._flavor


class CardSearch:
    def __init__(
        self,
        name: str,
        img: str,
        creator: str,
        cmc: int,
        colors: list[str],
        sides: list[Side],
        cardset: str,
        legality: str,
        rulings: str,
        tags: list[str],
    ):
        self._name = name
        self._img = img
        self._creator = creator
        self._cmc = cmc
        self._colors = colors
        self._sides = sides
        self._cardset = cardset
        self._legality = legality
        self._rulings = rulings
        self._tags = tags

    def name(self):
        return self._name

    def img(self):
        return self._img

    def creator(self):
        return self._creator

    def legality(self):
        return self._legality

    def rulings(self):
        return self._rulings

    def cmc(self):
        return [self._cmc]

    def colors(self):
        return self._colors

    def cardset(self):
        return self._cardset

    def sides(self):
        return self._sides

    def tags(self):
        return self._tags

    def addTag(self, tag):
        self._tags.append(tag)

    def types(self):
        returnList: list[str] = []
        for i in self._sides:
            returnList += i.types()
        return list(set(returnList))

    def setRuling(self, ruling):
        self._rulings = ruling

    def power(self):
        returnList = []
        for i in self._sides:
            returnList.append(i.power())
        return list(set(returnList))

    def toughness(self):
        returnList = []
        for i in self._sides:
            returnList.append(i.toughness())
        return list(set(returnList))

    def loyalty(self):
        returnList = []
        for i in self._sides:
            returnList.append(i.loyalty())
        return list(set(returnList))

    def text(self):
        returnString = ""
        for i in self._sides:
            returnString += i.text()
        return returnString

    def flavor(self):
        returnString = ""
        for i in self._sides:
            returnString += i.flavor()
        return returnString
