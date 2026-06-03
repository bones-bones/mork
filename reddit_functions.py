import os
from typing import Dict, List, Union

import asyncpraw
from asyncpraw.const import API_PATH
from asyncpraw.exceptions import RedditAPIException
from dotenv import load_dotenv

load_dotenv()

ID = os.environ["REDDIT_ID"]
SECRET = os.environ["REDDIT_SECRET"]
PASSWORD = os.environ["REDDIT_PASSWORD"]
USER_AGENT = os.environ["REDDIT_USER_AGENT"]
NAME = os.environ["REDDIT_NAME"]


async def post_to_reddit(image_path: str, title: str, flair: str = ""):
    async with asyncpraw.Reddit(
        client_id=ID,
        client_secret=SECRET,
        password=PASSWORD,
        user_agent=USER_AGENT,
        username=NAME,
    ) as reddit:
        # print(await reddit.user.me())
        hellscubeSubreddit: asyncpraw.reddit.Subreddit = await reddit.subreddit(
            "HellsCube"
        )
        await hellscubeSubreddit.submit_image(
            title=title, image_path=image_path, flair_id=flair
        )


def _gallery_media_id(upload_result: Union[str, tuple]) -> str:
    # asyncpraw 7.7.x returns (asset_id, websocket_url); 7.8.x returns asset_id only.
    # submit_gallery still indexes [0], which breaks on 7.8.x (first char of the id).
    if isinstance(upload_result, tuple):
        return upload_result[0]
    return upload_result


async def post_gallery_to_reddit(
    images: List[Dict[str, str]], title: str, flair: str = ""
):
    async with asyncpraw.Reddit(
        client_id=ID,
        client_secret=SECRET,
        password=PASSWORD,
        user_agent=USER_AGENT,
        username=NAME,
    ) as reddit:
        hellscubeSubreddit: asyncpraw.reddit.Subreddit = await reddit.subreddit(
            "HellsCube"
        )
        hellscubeSubreddit._validate_gallery(images)
        data = {
            "api_type": "json",
            "items": [],
            "nsfw": False,
            "sendreplies": True,
            "show_error_list": True,
            "spoiler": False,
            "sr": str(hellscubeSubreddit),
            "title": title,
            "validate_on_submit": reddit.validate_on_submit,
        }
        if flair:
            data["flair_id"] = flair
        for image in images:
            media_id = _gallery_media_id(
                await hellscubeSubreddit._upload_media(
                    expected_mime_prefix="image",
                    media_path=image["image_path"],
                    upload_type="gallery",
                )
            )
            data["items"].append(
                {
                    "caption": image.get("caption", ""),
                    "outbound_url": image.get("outbound_url", ""),
                    "media_id": media_id,
                }
            )
        response = await reddit.request(
            json=data, method="POST", path=API_PATH["submit_gallery_post"]
        )
        response = response["json"]
        if response["errors"]:
            raise RedditAPIException(response["errors"])
