import json
import math
import textwrap
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from .TSHAltTextHelper import generate_bsky_text, generate_youtube
from .TSHLocaleHelper import TSHLocaleHelper
from src.SettingsManager import SettingsManager
from atproto import Client
from atproto_client.models.app.bsky.embed.defs import AspectRatio

def post_to_bsky(scoreboardNumber=1, image_path=None):
    locale = TSHLocaleHelper.programLocale
    bsky_account = SettingsManager.Get("bsky_account", {})
    if not bsky_account or not bsky_account.get("username") or not bsky_account.get("host") or not bsky_account.get("app_password"):
        raise ValueError(QApplication.translate("app", "TSH_legacy_00282"))
    client = Client(bsky_account.get("host", "https://bsky.social"))
    client.login(bsky_account["username"].lstrip("@"), bsky_account["app_password"])

    raw_text, builder = generate_bsky_text(scoreboard_id = scoreboardNumber)
    yt_title, yt_description = generate_youtube(scoreboard_id = scoreboardNumber)  # Use YouTube Description as Alt Text

    pixmap = QPixmap(image_path, "RGBA")
    aspect_ratio = AspectRatio(width=pixmap.width(), height=pixmap.height())

    with open(image_path, "rb") as image:
            post = client.send_images(builder, images=[image.read()], image_alts=[yt_description], langs=[locale], image_aspect_ratios=[aspect_ratio])
