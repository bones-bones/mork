from typing import Dict, List
import asyncpraw

from bot_secrets.reddit_secrets import ID, SECRET, PASSWORD, USER_AGENT, NAME


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
