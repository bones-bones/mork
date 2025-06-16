import hc_constants
from shared_vars import googleClient

databaseSheets = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE)

mainSheet = databaseSheets.worksheet("Database")
startIndex = 3
endIndex = 5
cardNames = mainSheet.range("A3:A5")
fullImage = mainSheet.range("B3:B5")
draftImage = mainSheet.range("S3:S5")
side2 = mainSheet.range("AD3:AD5")
side3 = mainSheet.range("AN3:AN5")
side4 = mainSheet.range("AX3:AX5")


# A, B, S, AD, AN, AX
