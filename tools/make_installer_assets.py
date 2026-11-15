"""Generate the Inno Setup artwork for TongSheng (dark, on-brand)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"C:\Local Repositories\TongSheng")
OUT = ROOT / "dist" / "installer_assets"
OUT.mkdir(parents=True, exist_ok=True)

LOGO = Image.open(ROOT / "assets" / "TS-mic.png").convert("RGBA")
FONTS = Path(r"C:\Windows\Fonts")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for candidate in (FONTS / name, FONTS / "segoeui.ttf"):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def gradient(width: int, height: int, top: tuple[int, int, int],
             bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(1, height - 1)
        draw.line(
            [(0, y), (width, y)],
            fill=tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)),
        )
    return image


def glow(base: Image.Image, box: tuple[int, int, int, int]) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(box, fill=(76, 194, 255, 26))
    base.alpha_composite(layer)


# --- big wizard panel: 164 x 314 -------------------------------------
W, H = 164, 314
panel = gradient(W, H, (14, 20, 27), (26, 36, 48)).convert("RGBA")

card = Image.new("RGBA", (W - 16, H - 16), (0, 0, 0, 0))
ImageDraw.Draw(card).rounded_rectangle(
    [(0, 0), (card.width - 1, card.height - 1)], radius=10,
    fill=(11, 16, 22, 200), outline=(76, 194, 255, 60), width=1)
panel.alpha_composite(card, (8, 8))

glow(panel, (22, 22, 142, 142))
logo = LOGO.resize((84, 84), Image.LANCZOS)
panel.alpha_composite(logo, ((W - 84) // 2, 40))

draw = ImageDraw.Draw(panel)
title = font("seguisb.ttf", 15)
subtitle = font("segoeui.ttf", 8)
caption = font("segoeui.ttf", 7)

def centred(text: str, y: int, f: ImageFont.FreeTypeFont, colour) -> None:
    box = draw.textbbox((0, 0), text, font=f)
    draw.text(((W - (box[2] - box[0])) / 2, y), text, font=f, fill=colour)

centred("TongSheng", 141, title, (232, 241, 250, 255))
centred("\u540c\u58f0  \u00b7  TongSheng", 163, font("msyh.ttc", 9), (143, 166, 188, 255))
draw.line([(46, 185), (118, 185)], fill=(76, 194, 255, 110), width=1)
centred("Your voice,", 196, caption, (150, 172, 193, 255))
centred("any language.", 208, caption, (150, 172, 193, 255))

centred("local  ·  offline  ·  GPT-SoVITS v4", 258, caption, (104, 124, 143, 255))
centred("v1.1.1", 276, caption, (104, 124, 143, 255))

panel.convert("RGB").save(OUT / "wizard_image.bmp", format="BMP")

# --- small wizard corner: 55 x 55 ------------------------------------
small = gradient(55, 55, (14, 20, 27), (24, 33, 44)).convert("RGBA")
mark = LOGO.resize((44, 44), Image.LANCZOS)
small.alpha_composite(mark, (5, 5))
small.convert("RGB").save(OUT / "wizard_small.bmp", format="BMP")

# --- application icon ------------------------------------------------
sizes = [16, 24, 32, 48, 64, 128, 256]
LOGO.save(OUT / "app.ico", format="ICO", sizes=[(s, s) for s in sizes])

# copy into the staged package so shortcuts and the uninstall entry can use it
staged = ROOT / "dist" / "TongSheng-1.1.1"
if staged.is_dir():
    (staged / "app.ico").write_bytes((OUT / "app.ico").read_bytes())

for name in ("wizard_image.bmp", "wizard_small.bmp", "app.ico"):
    path = OUT / name
    print(f"{name}: {path.stat().st_size / 1024:.1f} KB")
