from typing import Type


class Card:
    def __init__(self, uuid:str, oracle_id:str, hcid:str, name:str, image:str, creators:list[str], artists:list[str]):
        self._uuid = uuid
        self._oracle_id = oracle_id
        self._hcid = hcid
        self._name = name
        self._image = image
        self._creators = creators
        self._artists = artists

    def getUUID(self):
        return self._uuid

    def getOracleID(self):
        return self._oracle_id
    
    def getHCID(self):
        return self._hcid
    
    def getName(self):
        return self._name

    def getImage(self):
        return self._image

    def getCreators(self):
        return self._creators

    def getArtists(self):
        return self._artists



class Side:
    def __init__(
        self,
        image: str,
        mana_cost: str,
        supertypes: list[str],
        types: list[str],
        subtypes: list[str],
        oracle_text: str,
        flavor_text: str,
        power: str,
        toughness: str,
        loyalty: str,
    ):
        self._image = image
        self._mana_cost = mana_cost
        self._supertypes = supertypes
        self._types = types
        self._subtypes = subtypes
        self._oracle_text = oracle_text
        self._flavor_text = flavor_text
        self._power = power
        self._toughness = toughness
        self._loyalty = loyalty

    def image(self):
        return self._image
    
    def manaCost(self):
        return self._mana_cost

    def types(self):
        return self._supertypes + self._types + self._subtypes

    def oracleText(self):
        return self._oracle_text

    def flavorText(self):
        return self._flavor_text

    def power(self):
        return self._power

    def toughness(self):
        return self._toughness

    def loyalty(self):
        return self._loyalty


class CardSearch:
    def __init__(
        self,
        uuid: str,
        oracle_id:str,
        hcid: str,
        name: str,
        cardset: str,
        accepted_order: str,
        image: str,
        mana_value: int|float,
        colors: list[str],
        legalities: str,
        creators: list[str],
        artists: list[str],
        rulings: str,
        tags: list[str],
        sides: list[Side],
        related: list[str],
    ):
        self._uuid = uuid
        self._oracle_id = oracle_id
        self._hcid = hcid
        self._name = name
        self._cardset = cardset
        self._accepted_order = accepted_order
        self._image = image
        self._mana_value = mana_value
        self._colors = colors
        self._legalities = legalities
        self._creators = creators
        self._artists = artists
        self._rulings = rulings
        self._tags = tags
        self._sides = sides
        self._related = related

    def uuid(self):
        return self._uuid

    def oracleId(self):
        return self._oracle_id

    def hcid(self):
        return self._hcid

    def name(self):
        return self._name

    def cardset(self):
        return self._cardset

    def acceptedOrder(self):
        return self._accepted_order
    
    def image(self):
        return self._image

    def manaValue(self):
        return [self._mana_value]

    def colors(self):
        return self._colors

    def legalities(self):
        return self._legalities

    def creators(self):
        return self._creators

    def artists(self):
        return self._artists

    def rulings(self):
        return self._rulings

    def tags(self):
        return self._tags

    def sides(self):
        return self._sides

    def related(self):
        return self._related

    def addTag(self, tag):
        if (not tag in self._tags):
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

    def oracleText(self):
        returnString = ""
        for i in self._sides:
            returnString += i.oracleText()
        return returnString

    def flavorText(self):
        returnString = ""
        for i in self._sides:
            returnString += i.flavorText()
        return returnString
