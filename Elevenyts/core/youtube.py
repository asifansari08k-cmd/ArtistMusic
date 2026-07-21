import os
import re
import urllib.parse
import aiohttp
import asyncio
from dataclasses import replace
from typing import Optional, Union

from pyrogram import enums, types
from py_yt import VideosSearch, Playlist
from Elevenyts import config, logger
from Elevenyts.helpers import Track, utils

class YouTube:
    def __init__(self):
        """Initialize Anysnap YouTube handler (100% API Based)."""
        self.base = "https://www.youtube.com/watch?v="
        
        # Hardcoded URL set to your live AWS server to prevent localhost clashes
        self.api_url = os.getenv("ANYSNAP_API_URL", "http://18.209.168.200:8000").rstrip('/')
        
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|live/|embed/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

        self.search_cache = {}
        
        logger.info("=" * 50)
        logger.info("📹 Anysnap YouTube Handler Initialized")
        logger.info(f"🔗 API URL: {self.api_url}")
        logger.info("⚡ Mode: 100% Streamable API Link Mode")
        logger.info("=" * 50)

    def valid(self, url: str) -> bool:
        """Check if URL is a valid YouTube URL."""
        return bool(re.match(self.regex, url))

    def url(self, message_1: types.Message) -> Union[str, None]:
        """Extract YouTube URL from message."""
        messages = [message_1]
        link = None

        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            text = message.text or message.caption or ""
            if message.entities:
                for entity in message.entities:
                    if entity.type == enums.MessageEntityType.URL:
                        link = text[entity.offset: entity.offset + entity.length]
                        break
            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == enums.MessageEntityType.TEXT_LINK:
                        link = entity.url
                        break

        if link:
            return link.split("&si")[0].split("?si")[0]
        return None

    async def search(self, query: str, m_id: int) -> Track | None:
        """Search for a song on YouTube using Py_yt fallback."""
        cache_key = query
        current_time = asyncio.get_running_loop().time()

        if cache_key in self.search_cache:
            cached_result, cache_timestamp = self.search_cache[cache_key]
            if current_time - cache_timestamp < 600: 
                fresh = replace(cached_result)
                fresh.message_id = m_id
                fresh.file_path = None
                fresh.user = None
                fresh.time = 0
                fresh.video = False
                return fresh

        try:
            _search = VideosSearch(query, limit=1)
            results = await _search.next()
            
            if results and results["result"]:
                data = results["result"][0]
                duration = data.get("duration")
                is_live = duration is None or duration == "LIVE"

                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", {}).get("name"),
                    duration=duration if not is_live else "LIVE",
                    duration_sec=0 if is_live else utils.to_seconds(duration),
                    message_id=m_id,
                    title=data.get("title")[:25],
                    thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                    url=data.get("link"),
                    view_count=data.get("viewCount", {}).get("short"),
                    is_live=is_live,
                )
                self.search_cache[cache_key] = (track, current_time)
                
                if len(self.search_cache) > 100:
                    oldest_key = min(self.search_cache.keys(), key=lambda k: self.search_cache[k][1])
                    del self.search_cache[oldest_key]
                return replace(track)
        except Exception as e:
            logger.warning(f"⚠️ Search failed for '{query}': {e}")
            
        return None

    async def playlist(self, limit: int, user: str, url: str) -> list[Track]:
        """Extract tracks from a YouTube playlist."""
        try:
            plist = await Playlist.get(url)
            tracks = []
            if not plist or "videos" not in plist or not plist["videos"]:
                return []

            for data in plist["videos"][:limit]:
                try:
                    thumbnails = data.get("thumbnails", [])
                    thumbnail_url = thumbnails[-1].get("url", "").split("?")[0] if thumbnails else ""
                    link = data.get("link", "").split("&list=")[0]

                    track = Track(
                        id=data.get("id", ""),
                        channel_name=data.get("channel", {}).get("name", ""),
                        duration=data.get("duration", "0:00"),
                        duration_sec=utils.to_seconds(data.get("duration", "0:00")),
                        title=(data.get("title", "Unknown")[:25]),
                        thumbnail=thumbnail_url,
                        url=link,
                        user=user,
                        view_count="",
                    )
                    tracks.append(track)
                except Exception:
                    continue
            return tracks
        except Exception as e:
            logger.error(f"Playlist error: {e}")
            return []

    async def download(self, video_id: str, is_live: bool = False, video: bool = False) -> Optional[str]:
        """
        Hit Anysnap API (/download or /video) and return final /files/{filename} stream URL.
        No yt-dlp. No local downloads on the Bot Server.
        """
        try:
            youtube_url = self.base + video_id
            endpoint = "/video" if video else "/download"
            
            # API endpoint generate
            api_process_link = f"{self.api_url}{endpoint}?url={urllib.parse.quote(youtube_url)}"
            logger.info(f"🚀 Calling Anysnap API: {api_process_link}")

            async with aiohttp.ClientSession() as session:
                async with session.get(api_process_link, timeout=40) as response:
                    if response.status != 200:
                        logger.error(f"❌ API returned status {response.status}")
                        return None
                        
                    # Fix: content_type=None bypasses strict mimetype checking
                    track_data = await response.json(content_type=None)
                    
                    if track_data.get("status") is True:
                        # Extract exact filename URL from JSON response
                        filename_path = track_data.get("download_url") 
                        final_stream_link = f"{self.api_url}{filename_path}"
                        
                        logger.info(f"✅ Anysnap Stream Link Generated: {final_stream_link}")
                        return final_stream_link
                    else:
                        logger.error("❌ API processed but status is False.")
                        return None

        except Exception as e:
            logger.error(f"❌ Custom Download Error: {e}")
            return None