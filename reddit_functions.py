
from typing import Dict, List
import asyncpraw

from secrets.reddit_secrets import ID,SECRET,PASSWORD,USER_AGENT,NAME

async def postToReddit(image_path:str, title:str, flair:str=""):
    reddit = asyncpraw.Reddit(
        client_id = ID,
        client_secret = SECRET,
        password = PASSWORD,
        user_agent = USER_AGENT,
        username = NAME
    )
    # print(await reddit.user.me())
    hellscubeSubreddit: asyncpraw.reddit.Subreddit = await reddit.subreddit('HellsCube')
    
    return await hellscubeSubreddit.submit_image(title = title, image_path = image_path, flair_id = flair)

    

async def postGalleryToReddit( images: List[Dict[str, str]], title:str, flair:str=""):
    reddit = asyncpraw.Reddit(
        client_id = ID,
        client_secret = SECRET,
        password = PASSWORD,
        user_agent = USER_AGENT,
        username = NAME
    )
    # print(await reddit.user.me())
    hellscubeSubreddit: asyncpraw.reddit.Subreddit = await reddit.subreddit('HellsCube')
    
    return await hellscubeSubreddit.submit_gallery(title = title, images = images, flair_id = flair)