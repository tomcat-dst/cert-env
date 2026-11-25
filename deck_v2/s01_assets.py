"""Slide 1 (dark theme): a full-slide grain background and the three images that sit on it.

Every image is cut from the same background at its own slide position, so the grain runs on
without a visible edge. The grid is 2400 x 1350 px over the 12 192 000 x 6 858 000 EMU slide
(5080 EMU per px); each box below is in those px and must match the element's transform.
Needs the Lumenier photo of the Believer (white studio background) as the first argument.
Run from the repo root: PYTHONPATH=deck_v2 venv/bin/python deck_v2/s01_assets.py <photo.jpg>"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import segno
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import diag  # noqa: F401  (sets the Noto Sans / DejaVu fonts)

BG = (0x12, 0x1C, 0x17)
ACC, MUTED, SEP = "#4CC38A", "#A8B0BA", "#3A414B"
GW, GH = 2400, 1350
EMU_PX = 5080
# element boxes in grid px: x, y, w, h
BOX = {"photo": (408, 294, 1952, 714), "qr": (126, 800, 595, 311), "strip": (126, 1132, 2142, 187)}
QR = [("https://docs.google.com/document/d/1wx0OFE11Dwyom2-HsZwjzmUpkwdVmlF7ZSopIkJqRMw/edit", "Звіт (Google Doc)"),
      ("https://drive.google.com/drive/folders/1coa5XbTpCdm2tx11kVoqnQ6iPmjxdJ1T", "Логи .bin (Drive)")]
FONT = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"


def background(seed=7):
    rng = np.random.default_rng(seed)
    img = np.ones((GH, GW, 3)) * BG
    # coarse mottling: blurred noise, a few levels either way
    mott = Image.fromarray((rng.normal(128, 40, (GH // 8, GW // 8))).clip(0, 255).astype("uint8"))
    mott = mott.filter(ImageFilter.GaussianBlur(6)).resize((GW, GH), Image.BICUBIC)
    m = (np.asarray(mott, float) - 128) / 40.0
    img += m[..., None] * np.array([2.5, 4.5, 3.5])
    # fine grain, monochrome
    img += rng.normal(0, 4.5, (GH, GW))[..., None]
    return Image.fromarray(img.clip(0, 255).astype("uint8"))


def tile(bg, name):
    x, y, w, h = BOX[name]
    return bg.crop((x, y, x + w, y + h)).convert("RGBA")


def photo(bg, path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(int)
    # copy(): floodfill does nothing on an Image that shares the numpy buffer
    m = Image.fromarray(((a.min(axis=2) >= 246) * 255).astype("uint8")).copy()
    for xy in [(0, 0), (m.width - 1, 0), (0, m.height - 1), (m.width - 1, m.height - 1)]:
        ImageDraw.floodfill(m, xy, 128)
    alpha = Image.fromarray(((np.asarray(m) != 128) * 255).astype("uint8"))
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    im.putalpha(alpha)
    im = im.crop(alpha.getbbox())
    t = tile(bg, "photo")
    k = t.width / (im.width + 120)          # 60 px margin each side in source px, as before
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    t.alpha_composite(im, ((t.width - im.width) // 2, (t.height - im.height) // 2))
    return t.convert("RGB")


def qr_pair(bg):
    t = tile(bg, "qr")
    d = ImageDraw.Draw(t)
    side = 266
    gap = t.width - 2 * side
    font = ImageFont.truetype(FONT, 20)
    for i, (url, label) in enumerate(QR):
        x0 = i * (side + gap)
        q = segno.make(url, error="m")
        n = q.symbol_size(border=4)[0]
        mod = side / n
        d.rectangle([x0, 0, x0 + side - 1, side - 1], fill="white")
        for r, row in enumerate(q.matrix_iter(border=4)):
            for c, v in enumerate(row):
                if v:
                    d.rectangle([x0 + round(c * mod), round(r * mod), x0 + round((c + 1) * mod) - 1,
                                 round((r + 1) * mod) - 1], fill=(14, 18, 16))
        d.text((x0 + side / 2, side + 22), label, font=font, fill=MUTED, anchor="mm")
    return t.convert("RGB")


def strip(bg):
    x, y, w, h = BOX["strip"]
    W, H = 100.0, 100.0 * h / w
    fig = plt.figure(figsize=(16, 16 * h / w), dpi=w / 16)
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    items = [("5,0 кг", "базова маса"), ("1,96 м", "розмах"), ("2 год 02 хв", "на 900 м, SITL"),
             ("101 км", "місія без RC 1:15"), ("0,56 м/с", "автопосадка"), ("16° → 2°", "крен після AUTOTUNE")]
    cw = W / len(items)
    for i, (big, small) in enumerate(items):
        cx = i * cw + 0.5
        if i:
            ax.plot([cx - 0.9, cx - 0.9], [0.14 * H, 0.86 * H], color=SEP, lw=1.2)
        ax.text(cx + 0.6, 0.86 * H, big, fontsize=26, fontweight="bold", color=ACC, va="top")
        ax.text(cx + 0.6, 0.25 * H, small, fontsize=15, color=MUTED, va="bottom")
    fig.canvas.draw()
    fg = Image.frombuffer("RGBA", fig.canvas.get_width_height(), fig.canvas.buffer_rgba()).copy()
    plt.close(fig)
    t = tile(bg, "strip")
    t.alpha_composite(fg.resize(t.size))
    return t.convert("RGB")


if __name__ == "__main__":
    bg = background()
    bg.save("deck_v2/s01_bg_noise.jpg", quality=92)
    photo(bg, sys.argv[1]).save("deck_v2/s01_photo_noise.jpg", quality=92)
    qr_pair(bg).save("deck_v2/s01_qr_noise.png")
    strip(bg).save("deck_v2/s01_strip_noise.jpg", quality=92)
    for k, (x, y, w, h) in BOX.items():
        print(k, "translate", x * EMU_PX, y * EMU_PX, "size", w * EMU_PX, h * EMU_PX)
