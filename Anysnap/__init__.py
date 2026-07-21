# ==========================================================
# Copyright (c) 2026 Anysnap
# All Rights Reserved.
#
# Project      : Anysnap API Telegram Music Bot
# Powered By   : Anysnap
# Type         : API Based Telegram Music Bot
#
# Channel      : @ANYSNAP
# GitHub       : https://github.com/themagmalord333-oss
#
# Unauthorized copying, modification, or redistribution
# of this source code without permission is prohibited.
# ==========================================================

import asyncio
import time
import logging
from logging.handlers import RotatingFileHandler
from typing import List

# Configure logging
logging.basicConfig(
    format="[%(asctime)s - %(levelname)s] - %(name)s: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("log.txt", maxBytes=10485760, backupCount=5),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)

# Reduce noise from third-party libraries
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("ntgcalls").setLevel(logging.CRITICAL)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)

logger = logging.getLogger("Anysnap")

# Version
__version__ = "3.0.1"

# Load configuration
from config import Config

config = Config()
config.check()

# Global task list for background tasks
tasks: List = []
boot: float = time.time()

# Initialize bot client
from Anysnap.core.bot import Bot
app = Bot()

# Ensure required directories exist
from Anysnap.core.dir import ensure_dirs
ensure_dirs()

# Initialize userbot/assistant clients
from Anysnap.core.userbot import Userbot
userbot = Userbot()

# Initialize database connection
from Anysnap.core.mongo import MongoDB
db = MongoDB()

# Initialize language system
from Anysnap.core.lang import Language
lang = Language()

# Initialize Telegram and YouTube utilities
from Anysnap.core.telegram import Telegram
from Anysnap.core.youtube import YouTube
tg = Telegram()
yt = YouTube()

# Initialize preload manager for background track downloading
from Anysnap.core.preload import PreloadManager
preload = PreloadManager()

# Initialize queue manager
from Anysnap.helpers import Queue
queue = Queue()

# Initialize preload manager for next-track downloading
from Anysnap.helpers._preload import PreloadManager
preload = PreloadManager()

# Initialize call handler
from Anysnap.core.calls import TgCall
tune = TgCall()


async def stop() -> None:
    """
    Gracefully shutdown the bot and all its components.
    
    This function:
    - Cancels all running background tasks
    - Closes bot and userbot connections
    - Closes database connection
    - Logs shutdown completion
    """
    logger.info("🛑 Stopping bot...")

    # Cancel all background tasks
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            # Expected when cancelling tasks - suppress the error
            pass
        except Exception:
            pass

    # Close all connections
    await app.exit()
    await userbot.exit()
    await db.close()

    logger.info("✅ Bot stopped successfully.\n")