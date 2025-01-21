from typing import Dict, Mapping
import discord
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from pydrive2.drive import GoogleDrive
from pydrive2.auth import GoogleAuth
from CardClasses import Card
import hc_constants


allCards: Dict[str, Card] = {}

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
intents.guilds = True


scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

gauth = GoogleAuth()
gauth.auth_method = "service"
creds = ServiceAccountCredentials.from_json_keyfile_name("./bot_secrets/client_secrets.json", scope)  # type: ignore
gauth.credentials = creds
drive = GoogleDrive(gauth)
about = drive.GetAbout()

googleClient = gspread.authorize(creds)  # type: ignore


# TODO: change this to use an id instead of an index
cardSheet = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE).get_worksheet(0)


# https://lh3.googleusercontent.com/d/1IZl1kGl0ajV4I7UY5DbQSL2yaF_i_uka
