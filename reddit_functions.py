import os
from typing import Dict, List

import asyncpraw
from dotenv import load_dotenv

load_dotenv()

ID = os.environ["REDDIT_ID"]
SECRET = os.environ["REDDIT_SECRET"]
PASSWORD = os.environ["REDDIT_PASSWORD"]
USER_AGENT = os.environ["REDDIT_USER_AGENT"]
NAME = os.environ["REDDIT_NAME"]


async def post_to_reddit(image_path: str, title: str, flair: str = ""):
    reddit = asyncpraw.Reddit(
        client_id=ID,
        client_secret=SECRET,
        password=PASSWORD,
        user_agent=USER_AGENT,
        username=NAME,
    )
    # print(await reddit.user.me())
    hellscubeSubreddit: asyncpraw.reddit.Subreddit = await reddit.subreddit("HellsCube")

    await hellscubeSubreddit.submit_image(
        title=title, image_path=image_path, flair_id=flair
    )
    return await reddit.close()


async def post_gallery_to_reddit(
    images: List[Dict[str, str]], title: str, flair: str = ""
):
    reddit = asyncpraw.Reddit(
        client_id=ID,
        client_secret=SECRET,
        password=PASSWORD,
        user_agent=USER_AGENT,
        username=NAME,
    )
    # print(await reddit.user.me())
    hellscubeSubreddit: asyncpraw.reddit.Subreddit = await reddit.subreddit("HellsCube")

    await hellscubeSubreddit.submit_gallery(title=title, images=images, flair_id=flair)
    await reddit.close()
