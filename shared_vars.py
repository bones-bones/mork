from typing import Mapping
import discord
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from pydrive2.drive import GoogleDrive
from pydrive2.auth import GoogleAuth
from CardClasses import Card
import hc_constants


allCards:Mapping[str,Card] = {}

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
intents.guilds = True




scope = [
    "https://spreadsheets.google.com/feeds",
    'https://www.googleapis.com/auth/spreadsheets',
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"]


gauth = GoogleAuth()
gauth.auth_method = 'service'
creds = ServiceAccountCredentials.from_json_keyfile_name("secrets/client_secrets.json", scope)
gauth.credentials=creds
drive = GoogleDrive(gauth)
about = drive.GetAbout()

googleClient = gspread.authorize(creds)


cardSheet = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE).get_worksheet(0)
print(cardSheet)


#https://lh3.googleusercontent.com/d/1IZl1kGl0ajV4I7UY5DbQSL2yaF_i_uka