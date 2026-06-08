import os
import re
import glob
import asyncio
import aiohttp
from dataclasses import replace
from typing import Optional, Union

from pyrogram import enums, types
from py_yt import Playlist, VideosSearch
from LuffyxHancock import config, logger
from LuffyxHancock.helpers import Track, utils

class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.search_cache = {}
        self._download_semaphore = asyncio.Semaphore(5)

        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|live/|embed/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

        logger.info("=" * 50)
        logger.info("📹 YouTube Handler Initialized (API ONLY MODE - NO COOKIES)")
        logger.info("=" * 50)

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def url(self, message: types.Message) -> Union[str, None]:
        messages = [message]
        if message.reply_to_message:
            messages.append(message.reply_to_message)

        for msg in messages:
            text = msg.text or msg.caption or ""
            entities = msg.entities or msg.caption_entities or []
            
            for entity in entities:
                if entity.type == enums.MessageEntityType.URL:
                    link = text[entity.offset: entity.offset + entity.length]
                    return link.split("&si")[0].split("?si")[0]
                elif entity.type == enums.MessageEntityType.TEXT_LINK:
                    return entity.url.split("&si")[0].split("?si")[0]
        return None

    async def search(self, query: str, m_id: int) -> Track | None:
        try:
            _search = VideosSearch(query, limit=1)
            results = await _search.next()
            
            if results and results["result"]:
                data = results["result"][0]
                is_live = data.get("duration") is None or data.get("duration") == "LIVE"
                
                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", {}).get("name"),
                    duration="LIVE" if is_live else data.get("duration"),
                    duration_sec=0 if is_live else utils.to_seconds(data.get("duration")),
                    message_id=m_id,
                    title=data.get("title")[:25],
                    thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                    url=data.get("link"),
                    view_count=data.get("viewCount", {}).get("short", ""),
                    is_live=is_live,
                )
                return track
        except Exception as e:
            logger.warning(f"⚠️ YouTube search failed: {e}")
        return None

    async def playlist(self, limit: int, user: str, url: str) -> list[Track]:
        try:
            plist = await Playlist.get(url)
            tracks = []
            if not plist or "videos" not in plist:
                return tracks

            for data in plist["videos"][:limit]:
                link = data.get("link", "").split("&list=")[0]
                track = Track(
                    id=data.get("id", ""),
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration", "0:00"),
                    duration_sec=utils.to_seconds(data.get("duration", "0:00")),
                    title=data.get("title", "Unknown")[:25],
                    thumbnail=data.get("thumbnails", [{}])[-1].get("url", "").split("?")[0] if data.get("thumbnails") else "",
                    url=link,
                    user=user,
                    view_count="",
                )
                tracks.append(track)
            return tracks
        except Exception as e:
            logger.error(f"Playlist extraction error: {e}")
            return []

    async def get_download_link_via_api(self, video_id: str, video: bool) -> Optional[str]:
        """Free Public API များကို အသုံးပြု၍ ဒေါင်းလုဒ် Link ရယူခြင်း"""
        url = self.base + video_id
        try:
            # Cobalt API (No API Key Required) ကို အသုံးပြုခြင်း
            api_url = "https://co.wuk.sh/api/json"
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            payload = {"url": url, "isAudioOnly": not video, "aFormat": "mp3"}

            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers, timeout=20) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("url")
                    else:
                        logger.error(f"API Error: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"Free API failed: {e}")

        return None

    async def download(self, video_id: str, is_live: bool = False, video: bool = False) -> Optional[str]:
        """API မှတဆင့် သီချင်းများကို တိုက်ရိုက်ဒေါင်းလုဒ်ဆွဲခြင်း (Cookies/yt-dlp အသုံးမပြုပါ)"""
        url = self.base + video_id
        os.makedirs("downloads", exist_ok=True)
        
        file_ext = ".mp4" if video else ".mp3"
        file_path = f"downloads/{video_id}{file_ext}"

        # ဖိုင်ရှိပြီးသားဆို ပြန်သုံးမည်
        if os.path.exists(file_path):
            return file_path

        async with self._download_semaphore:
            logger.info(f"🌐 API အသုံးပြု၍ ဒေါင်းလုပ်ဆွဲနေပါသည်... (No yt-dlp, No Cookies)")
            
            # 1. API မှတဆင့် ဒေါင်းလုဒ် Link ရယူခြင်း
            download_url = await self.get_download_link_via_api(video_id, video)

            if not download_url:
                logger.error("❌ API မှ Link မရရှိပါ။ (API ယာယီ ကျနေနိုင်ပါသည်)")
                return None

            try:
                # 2. ရလာသော Link အား Server ထဲသို့ ဒေါင်းလုဒ်ဆွဲခြင်း
                async with aiohttp.ClientSession() as session:
                    async with session.get(download_url) as file_resp:
                        if file_resp.status == 200:
                            with open(file_path, "wb") as f:
                                while True:
                                    chunk = await file_resp.content.read(65536) # 64KB chunks
                                    if not chunk:
                                        break
                                    f.write(chunk)
                            logger.info(f"✅ Download complete via API: {file_path}")
                            return file_path
                        else:
                            logger.error(f"❌ File download failed: HTTP {file_resp.status}")
                            return None
            except Exception as e:
                logger.error(f"❌ Exception during download: {e}")
                return None
