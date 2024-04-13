from shared_vars import allCards
from thefuzz import fuzz


def cardNameRequest(requestName):
  maxWeight = 1
  maxWeightName = ""
  for cardName in allCards.keys():
    currentWeight = fuzz.partial_ratio(cardName, requestName)
    if currentWeight > maxWeight:
      maxWeight = currentWeight
      maxWeightName = cardName
    elif cardName.lower() == requestName.lower():
        maxWeightName = cardName
    elif currentWeight == maxWeight and (len(cardName) < len(maxWeightName)): # if the similarity is a tie, use the shorter name. seems okay?
        maxWeightName = cardName
  return maxWeightName

def similarity(name:str, requestName:str):
    if name == requestName or name + " " == requestName:
        return 10000000
    weight = 0
    for i in range(len(requestName)):
        for j in range(len(name)):
            minOfNameAndRequest = min( len(name) - j , len(requestName) - i )
            for x in range(1, minOfNameAndRequest + 1):
                if requestName[i:i+x] != name[j:j+x] or x == minOfNameAndRequest:
                    weight += max((x-1) * (x-1) -1, 0) # the further along in the matching we are, the better
                    break
    return weight
