
import os
import re
import asyncio
import aiohttp
import base64

from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont
)

from LuffyxHancock import config
from LuffyxHancock.helpers import Track


PANEL_W, PANEL_H = 1030, 610
PANEL_X = (1280 - PANEL_W) // 2
PANEL_Y = 55

THUMB_W, THUMB_H = 930, 420
THUMB_X = PANEL_X + (PANEL_W - THUMB_W) // 2
THUMB_Y = PANEL_Y + 30

TITLE_X = THUMB_X + 5
TITLE_Y = THUMB_Y + THUMB_H + 25

META_Y = TITLE_Y + 58

BAR_X = THUMB_X + 5
BAR_Y = META_Y + 60

BAR_RED_LEN = 330
BAR_TOTAL_LEN = 920

ICONS_W, ICONS_H = 420, 45
ICONS_X = PANEL_X + (PANEL_W - ICONS_W) // 2
ICONS_Y = BAR_Y + 65

MAX_TITLE_WIDTH = 850

_f = "QXJ0aXN0Ym90cw=="


def _decode_f():
    decoded = base64.b64decode(_f).decode("utf-8")
    return f"✦ {decoded} ✦"


def trim_to_width(text: str, font, max_w: int) -> str:

    ellipsis = "…"

    if font.getlength(text) <= max_w:
        return text

    for i in range(len(text) - 1, 0, -1):

        if font.getlength(text[:i] + ellipsis) <= max_w:
            return text[:i] + ellipsis

    return ellipsis


class Thumbnail:

    def __init__(self):

        try:

            self.title_font = ImageFont.truetype(
                "LuffyxHancock/helpers/Raleway-Bold.ttf",
                42
            )

            self.regular_font = ImageFont.truetype(
                "LuffyxHancock/helpers/Inter-Light.ttf",
                24
            )

            self.signature_font = ImageFont.truetype(
                "LuffyxHancock/helpers/Raleway-Bold.ttf",
                28
            )

        except OSError:

            self.title_font = ImageFont.load_default()
            self.regular_font = ImageFont.load_default()
            self.signature_font = ImageFont.load_default()

    async def save_thumb(self, output_path: str, url: str):

        async with aiohttp.ClientSession() as session:

            async with session.get(url) as resp:

                with open(output_path, "wb") as f:
                    f.write(await resp.read())

        return output_path

    async def generate(self, song: Track, size=(1280, 720)) -> str:

        try:

            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}_ultra.png"

            if os.path.exists(output):
                return output

            await self.save_thumb(temp, song.thumbnail)

            return await asyncio.get_event_loop().run_in_executor(
                None,
                self._generate_sync,
                temp,
                output,
                song,
                size
            )

        except Exception:
            return config.DEFAULT_THUMB

    def _generate_sync(
        self,
        temp: str,
        output: str,
        song: Track,
        size=(1280, 720)
    ) -> str:

        try:

            with Image.open(temp) as temp_img:
                base = temp_img.resize(size).convert("RGBA")

            bg = base.filter(ImageFilter.GaussianBlur(28))

            bg = ImageEnhance.Brightness(bg).enhance(0.25)

            bg = ImageEnhance.Contrast(bg).enhance(1.4)

            overlay = Image.new(
                "RGBA",
                size,
                (0, 0, 0, 120)
            )

            bg = Image.alpha_composite(bg, overlay)

            panel = Image.new(
                "RGBA",
                (PANEL_W, PANEL_H),
                (10, 10, 10, 155)
            )

            border = Image.new(
                "RGBA",
                (PANEL_W, PANEL_H),
                (0, 0, 0, 0)
            )

            bd = ImageDraw.Draw(border)

            bd.rounded_rectangle(
                (0, 0, PANEL_W - 1, PANEL_H - 1),
                radius=42,
                outline=(0, 255, 255, 220),
                width=3
            )

            mask = Image.new(
                "L",
                (PANEL_W, PANEL_H),
                0
            )

            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, PANEL_W, PANEL_H),
                radius=42,
                fill=255
            )

            panel = Image.alpha_composite(panel, border)

            bg.paste(
                panel,
                (PANEL_X, PANEL_Y),
                mask
            )

            draw = ImageDraw.Draw(bg)

            draw.text(
                (45, 22),
                _decode_f(),
                fill=(255, 255, 255, 230),
                font=self.signature_font
            )

            thumb = base.resize((THUMB_W, THUMB_H))

            tmask = Image.new(
                "L",
                thumb.size,
                0
            )

            ImageDraw.Draw(tmask).rounded_rectangle(
                (0, 0, THUMB_W, THUMB_H),
                radius=28,
                fill=255
            )

            bg.paste(
                thumb,
                (THUMB_X, THUMB_Y),
                tmask
            )

            clean_title = re.sub(
                r"\W+",
                " ",
                song.title
            ).title()

            final_title = trim_to_width(
                clean_title,
                self.title_font,
                MAX_TITLE_WIDTH
            )

            draw.text(
                (TITLE_X + 2, TITLE_Y + 2),
                final_title,
                fill=(0, 0, 0),
                font=self.title_font
            )

            draw.text(
                (TITLE_X, TITLE_Y),
                final_title,
                fill=(255, 255, 255),
                font=self.title_font
            )

            meta_text = (
                f"Now Playing  •  YouTube  •  "
                f"{song.view_count or 'Unknown Views'}"
            )

            draw.text(
                (TITLE_X, META_Y),
                meta_text,
                fill=(180, 180, 180),
                font=self.regular_font
            )

            draw.rounded_rectangle(
                (
                    BAR_X,
                    BAR_Y - 5,
                    BAR_X + BAR_TOTAL_LEN,
                    BAR_Y + 5
                ),
                radius=12,
                fill=(60, 60, 60)
            )

            draw.rounded_rectangle(
                (
                    BAR_X,
                    BAR_Y - 5,
                    BAR_X + BAR_RED_LEN,
                    BAR_Y + 5
                ),
                radius=12,
                fill=(0, 255, 255)
            )

            draw.ellipse(
                (
                    BAR_X + BAR_RED_LEN - 12,
                    BAR_Y - 12,
                    BAR_X + BAR_RED_LEN + 12,
                    BAR_Y + 12
                ),
                fill=(0, 255, 255)
            )

            draw.text(
                (BAR_X, BAR_Y + 18),
                "00:00",
                fill="white",
                font=self.regular_font
            )

            is_live = getattr(song, "is_live", False)

            end_text = "LIVE" if is_live else song.duration

            draw.text(
                (BAR_X + BAR_TOTAL_LEN - 80, BAR_Y + 18),
                end_text,
                fill=(0, 255, 255) if is_live else "white",
                font=self.regular_font
            )

            icons_path = "LuffyxHancock/helpers/play_icons.png"

            if os.path.isfile(icons_path):

                with Image.open(icons_path) as icons_img:

                    ic = icons_img.resize(
                        (ICONS_W, ICONS_H)
                    ).convert("RGBA")

                    r, g, b, a = ic.split()

                    cyan_ic = Image.merge(
                        "RGBA",
                        (
                            r.point(lambda _: 0),
                            g.point(lambda _: 255),
                            b.point(lambda _: 255),
                            a
                        )
                    )

                    bg.paste(
                        cyan_ic,
                        (ICONS_X, ICONS_Y),
                        cyan_ic
                    )

            bg.save(output)

            try:
                os.remove(temp)

            except OSError:
                pass

            return output

        except Exception:
            return config.DEFAULT_THUMB
