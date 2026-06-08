import aiohttp
import os
import aiofiles

async def download(self, video_id: str, is_live: bool = False, video: bool = False) -> Optional[str]:
    """ကိုယ်ပိုင် API Server ကိုသုံးပြီး Telegram Bot ဆီ ဖိုင်ယူခြင်း"""
    
    # ညီကို့ရဲ့ Render API URL (ဥပမာ)
    api_url = "https://velvet-aura-api.onrender.com/api/download"
    api_key = "VelvetAura2026SecureKey"
    target_url = self.base + video_id
    
    os.makedirs("downloads", exist_ok=True)
    file_ext = ".mp4" if video else ".m4a"
    local_file_path = f"downloads/{video_id}{file_ext}"

    # ဖိုင်ရှိပြီးသားဆို ထပ်မဒေါင်းပါ
    if os.path.exists(local_file_path):
        return local_file_path

    try:
        async with aiohttp.ClientSession() as session:
            # API ဆီသို့ Request ပို့ခြင်း
            params = {
                "url": target_url,
                "api_key": api_key,
                "is_audio": str(not video).lower()
            }
            
            async with session.get(api_url, params=params, timeout=300) as response:
                if response.status == 200:
                    # API မှပေးပို့လာသော ဖိုင်ကို Bot ၏ Local ထဲသို့ သိမ်းခြင်း
                    async with aiofiles.open(local_file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(65536):
                            await f.write(chunk)
                    return local_file_path
                else:
                    print(f"API Error: HTTP {response.status}")
                    return None
    except Exception as e:
        print(f"Download failed from API: {e}")
        return None
