import os
import re
import glob
import asyncio
import yt_dlp
import random
from dataclasses import replace
from typing import Optional, Union

from pyrogram import enums, types
from py_yt import Playlist, VideosSearch
from LuffyxHancock import logger
from LuffyxHancock.helpers import Track, utils

class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        
        # ညီကို့ရဲ့ Cloudflare Proxy URL ကို သတ်မှတ်ခြင်း
        self.proxy_url = "https://velvet-aura-proxy.pyaesone5psp.workers.dev/"
        
        self.cookies_dir = "LuffyxHancock/cookies"
        self.search_cache = {}
        self._download_semaphore = asyncio.Semaphore(5)

        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|live/|embed/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

        logger.info("=" * 50)
        logger.info("📹 YouTube Handler Initialized (Optimized + Cloudflare Proxy)")
        logger.info(f"🌐 Active Proxy: {self.proxy_url}")
        logger.info("=" * 50)

    def _process_url(self, url: str) -> str:
        """မူရင်း YouTube URL ကို Proxy URL နှင့် ပေါင်းစပ်ရန်"""
        if url.startswith("http"):
            return f"{self.proxy_url}{url}"
        return url

    def get_cookies(self) -> Optional[str]:
        """Cookies ဖိုင်များကို ရယူရန် (Bot Activity ကိုကျော်ရန် အလွန်အရေးကြီးပါသည်)"""
        if os.path.exists(self.cookies_dir):
            cookies = [f for f in os.listdir(self.cookies_dir) if f.endswith(".txt")]
            if cookies:
                return os.path.join(self.cookies_dir, random.choice(cookies))
        logger.warning("⚠️ Cookies ဖိုင်များ မတွေ့ပါ။ Download ပြဿနာတက်နိုင်ပါသည်။")
        return None

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

    async def download(self, video_id: str, is_live: bool = False, video: bool = False) -> Optional[str]:
        """yt-dlp ကို အသုံးပြု၍ သီချင်း/ဗီဒီယို ဒေါင်းလုပ်ဆွဲရန် (Proxy နှင့် Bot Bypass ပါဝင်သည်)"""
        url = self.base + video_id
        os.makedirs("downloads", exist_ok=True)

        # 1. အရင် ဒေါင်းလုပ်ဆွဲထားပြီးသား ရှိမရှိ စစ်ဆေးခြင်း
        existing_files = glob.glob(f"downloads/{video_id}.*")
        for f in existing_files:
            if not f.endswith(('.part', '.temp')):
                return f

        async with self._download_semaphore:
            # Proxy URL ကို မူရင်း YouTube URL ၏ အရှေ့တွင် ကပ်ပေးခြင်း
            proxied_url = self._process_url(url)

            # 2. Bot Activity (403 Error) ကို ကျော်လွှားရန် အရေးကြီးဆုံး Settings များ
            ydl_opts = {
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "nocheckcertificate": True,
                "geo_bypass": True,
                "cookiefile": self.get_cookies(), # Cookies မဖြစ်မနေ လိုအပ်ပါသည်
                "extractor_args": {
                    "youtube": {
                        # Android နှင့် iOS ဖုန်းများအဖြစ် ဟန်ဆောင်ရန် (IP Block နှင့် Bot Detection အတွက် အထိရောက်ဆုံး)
                        "player_client": ["android", "ios", "web"], 
                    }
                }
            }

            if video:
                ydl_opts.update({
                    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
                    "merge_output_format": "mp4",
                })
            else:
                ydl_opts.update({
                    "format": "bestaudio/best",
                })

            def _process_download():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        if is_live:
                            # Live Stream ဖြစ်ပါက Proxy Link မှတဆင့် extract လုပ်မည်
                            info = ydl.extract_info(proxied_url, download=False)
                            return info.get("url") or info.get("manifest_url")
                        else:
                            # ပုံမှန် သီချင်း/ဗီဒီယို ဖြစ်ပါက Proxy မှတဆင့် ဒေါင်းလုပ်ဆွဲမည်
                            info = ydl.extract_info(proxied_url, download=True)
                            return ydl.prepare_filename(info)
                except Exception as e:
                    logger.error(f"❌ Download Failed for {video_id} via Proxy: {e}")
                    return None

            return await asyncio.to_thread(_process_download)
