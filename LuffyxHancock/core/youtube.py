import os
import re
import glob
import time
import yt_dlp
import random
import asyncio
import aiohttp
from dataclasses import replace
from pathlib import Path
from typing import Optional, Union

from pyrogram import enums, types
from py_yt import Playlist, VideosSearch
from LuffyxHancock import config, logger
from LuffyxHancock.helpers import Track, utils


class YouTube:
    def __init__(self):
        """Initialize YouTube handler with configuration and caching."""
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.warned = False

        # Get API configuration from config
        self.api_url = config.ARTISTBOTS_API_URL
        self.artistbots_key = config.ARTISTBOTS_KEY
        self.enable_api = config.ENABLE_API
        self.enable_cookies_fallback = config.ENABLE_COOKIES_FALLBACK
        self.api_timeout = config.API_TIMEOUT
        self.api_stream_timeout = config.API_STREAM_TIMEOUT

        # Regular expression to match YouTube URLs
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|live/|embed/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

        # Cache search results (10 minute TTL)
        self.search_cache = {}
        self._download_semaphore = asyncio.Semaphore(5)
        self._max_video_height = config.VIDEO_MAX_HEIGHT

        # Log configuration
        logger.info("=" * 50)
        logger.info("📹 YouTube Handler Initialized (Custom API Mode)")
        logger.info(f"🎵 API Priority: {'ENABLED' if self.enable_api else 'DISABLED'}")
        if self.enable_api:
            logger.info(f"🔗 Custom API URL: {self.api_url}")
            if self.artistbots_key:
                masked_key = self.artistbots_key[:5] + "..." if len(self.artistbots_key) > 5 else "***"
                logger.info(f"🔑 API Key: {masked_key}")
            else:
                logger.warning("⚠️ No API Key configured!")
        logger.info(f"🍪 Cookies Fallback: {'ENABLED' if self.enable_cookies_fallback else 'DISABLED'}")
        logger.info("=" * 50)

    def _locate_download_file(self, video_id: str, video: bool = False) -> Optional[str]:
        """Locate any completed download file for a video id."""
        pattern = f"downloads/{video_id}*"
        candidates = sorted([
            path for path in glob.glob(pattern)
            if not path.endswith((".part", ".ytdl", ".info.json", ".temp"))
        ])

        video_exts = {".mp4", ".mkv", ".webm", ".mov"}
        audio_exts = {".m4a", ".webm", ".opus", ".mp3", ".ogg", ".wav", ".flac"}

        if video:
            for path in candidates:
                if os.path.isdir(path):
                    continue
                if Path(path).suffix.lower() in video_exts:
                    return path
        else:
            for path in candidates:
                if os.path.isdir(path):
                    continue
                if Path(path).suffix.lower() in audio_exts:
                    return path

        for path in candidates:
            if os.path.isdir(path):
                continue
            return path
        return None

    def get_cookies(self):
        """Get random cookie file from cookies directory."""
        if not self.checked:
            cookies_dir = "LuffyxHancock/cookies"
            if os.path.exists(cookies_dir):
                for file in os.listdir(cookies_dir):
                    if file.endswith(".txt"):
                        self.cookies.append(file)
            self.checked = True
        
        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("🍪 Cookies are missing; downloads might fail.")
            return None
        
        cookie_file = f"LuffyxHancock/cookies/{random.choice(self.cookies)}"
        logger.debug(f"Using cookie file: {cookie_file}")
        return cookie_file

    async def save_cookies(self, urls: list[str]) -> None:
        """Save cookies from URLs to files."""
        logger.info("🍪 Saving cookies from urls...")
        saved_count = 0
        cookies_dir = Path("LuffyxHancock/cookies")
        cookies_dir.mkdir(parents=True, exist_ok=True)
        
        for url in urls:
            try:
                path = cookies_dir / f"cookie{random.randint(10000, 99999)}.txt"
                if "pastebin.com" in url:
                    link = url.replace("pastebin.com", "pastebin.com/raw")
                elif "batbin.me" in url:
                    link = url.replace("batbin.me", "batbin.me/raw")
                else:
                    link = url
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(link, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status != 200:
                            continue
                        content = await resp.read()
                        if not content or len(content) < 50:
                            continue
                        with open(path, "wb") as fw:
                            fw.write(content)
                        if path.exists() and path.stat().st_size > 0:
                            saved_count += 1
                            if path.name not in self.cookies:
                                self.cookies.append(path.name)
            except Exception as e:
                logger.error(f"❌ Cookie download error from {url}: {e}")
        self.checked = True

    async def download_via_api(self, link: str, video: bool = False) -> Optional[str]:
        """
        ကိုယ်ပိုင်ဖန်တီးထားသော FastAPI Server ကို အသုံးပြု၍ ဒေါင်းလုဒ်ဆွဲခြင်း (Modified for Custom API)
        """
        if not self.enable_api or not self.api_url:
            return None

        # Extract video ID and full URL
        full_target_url = link
        if "v=" in link:
            video_id = link.split("v=")[-1].split("&")[0]
        elif "youtu.be" in link:
            video_id = link.split("/")[-1].split("?")[0]
        else:
            video_id = link
            full_target_url = self.base + video_id

        DOWNLOAD_DIR = "downloads"
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        file_ext = ".mp4" if video else ".m4a" # yt-dlp config in API uses m4a for audio
        file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}{file_ext}")

        if os.path.exists(file_path):
            return file_path

        try:
            logger.info(f"🚀 [CUSTOM API] Requesting file from Custom API for {video_id}")
            
            # FastAPI Server သို့ ပို့မည့် Parameters များ
            params = {
                "url": full_target_url,
                "api_key": self.artistbots_key,
                "is_audio": str(not video).lower()  # Audio သာဖြစ်လျှင် true
            }
            
            async with aiohttp.ClientSession() as session:
                # Base URL အနောက်တွင် /api/download မပါသေးလျှင် ပေါင်းထည့်ပေးမည်
                base_url = self.api_url.rstrip('/')
                api_endpoint = f"{base_url}/api/download" if not base_url.endswith("/download") else base_url
                
                async with session.get(
                    api_endpoint,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.api_stream_timeout)
                ) as response:
                    
                    if response.status != 200:
                        try:
                            error_text = await response.json()
                            logger.error(f"❌ API Error {response.status}: {error_text}")
                        except:
                            logger.error(f"❌ API Error: HTTP {response.status}")
                        return None
                    
                    logger.info(f"📥 Receiving file from Custom API for {video_id}...")
                    
                    # API မှ ဖြတ်ချပေးသော File အား Local တွင် သိမ်းဆည်းခြင်း
                    downloaded = 0
                    with open(file_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(65536):
                            f.write(chunk)
                            downloaded += len(chunk)
                    
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        logger.info(f"✅ [API SUCCESS] Downloaded: {file_path} ({file_size_mb:.2f} MB)")
                        return file_path
                    else:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        return None

        except asyncio.TimeoutError:
            logger.error(f"⏰ Custom API timeout for {video_id}")
            return None
        except Exception as e:
            logger.error(f"❌ Custom API download failed for {video_id}: {e}")
            return None

    async def download_via_cookies(self, video_id: str, video: bool = False) -> Optional[str]:
        """Fallback Method - Bot မှတိုက်ရိုက်ဆွဲခြင်း (Cookies ရှိရန်လိုအပ်သည်)"""
        if not self.enable_cookies_fallback:
            return None

        url = self.base + video_id
        located = self._locate_download_file(video_id, video=video)
        if located:
            return located

        os.makedirs("downloads", exist_ok=True)

        async with self._download_semaphore:
            cookie = self.get_cookies()
            base_opts = {
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "quiet": True,
                "noplaylist": True,
                "geo_bypass": True,
                "no_warnings": True,
                "nocheckcertificate": True,
                "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
                "cookiefile": cookie,
            }

            if video:
                ydl_opts = {**base_opts, "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best", "merge_output_format": "mp4"}
            else:
                ydl_opts = {**base_opts, "format": "bestaudio/best"}

            def _download():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        return ydl.prepare_filename(info)
                except Exception as ex:
                    logger.warning(f"⚠️ Local Download error for {video_id}: {ex}")
                    return None

            logger.info(f"🍪 [COOKIES FALLBACK] Downloading {video_id} locally...")
            result = await asyncio.to_thread(_download)
            if result:
                logger.info(f"✅ [COOKIES SUCCESS] Local Downloaded: {result}")
            return result

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def url(self, message_1: types.Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            text = message.text or message.caption or ""
            entities = message.entities or message.caption_entities or []
            for entity in entities:
                if entity.type == enums.MessageEntityType.URL:
                    return text[entity.offset: entity.offset + entity.length].split("&si")[0].split("?si")[0]
                if entity.type == enums.MessageEntityType.TEXT_LINK:
                    return entity.url.split("&si")[0].split("?si")[0]
        return None

    async def search(self, query: str, m_id: int) -> Track | None:
        cache_key = query
        current_time = asyncio.get_running_loop().time()
        if cache_key in self.search_cache:
            cached_result, cache_timestamp = self.search_cache[cache_key]
            if current_time - cache_timestamp < 600:
                fresh = replace(cached_result)
                fresh.message_id = m_id
                fresh.file_path = None
                return fresh
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
                    view_count=data.get("viewCount", {}).get("short"),
                    is_live=is_live,
                )
                self.search_cache[cache_key] = (track, current_time)
                return replace(track)
        except Exception as e:
            pass
        return None

    async def playlist(self, limit: int, user: str, url: str) -> list[Track]:
        try:
            plist = await Playlist.get(url)
            tracks = []
            if not plist or "videos" not in plist:
                return []
            for data in plist["videos"][:limit]:
                track = Track(
                    id=data.get("id", ""),
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration", "0:00"),
                    duration_sec=utils.to_seconds(data.get("duration", "0:00")),
                    title=(data.get("title", "Unknown")[:25]),
                    thumbnail=data.get("thumbnails", [{}])[-1].get("url", "").split("?")[0] if data.get("thumbnails") else "",
                    url=data.get("link", "").split("&list=")[0],
                    user=user,
                    view_count="",
                )
                tracks.append(track)
            return tracks
        except:
            return []

    async def download(self, video_id: str, is_live: bool = False, video: bool = False) -> Optional[str]:
        """
        PRIORITY: Custom API First → Local Cookies Fallback
        """
        if is_live:
            return await self.download_via_cookies(video_id, video)

        result = None
        if self.enable_api and self.api_url and self.artistbots_key:
            logger.info(f"🎯 [PRIORITY 1] Trying Custom API for {video_id}")
            result = await self.download_via_api(self.base + video_id, video=video)
            if result:
                return result
            logger.warning(f"⚠️ [API FAILED] Falling back to local cookies...")
        
        if self.enable_cookies_fallback:
            result = await self.download_via_cookies(video_id, video=video)
            if result:
                return result
        
        return None
