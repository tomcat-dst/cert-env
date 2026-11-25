"""Slides 2-12 (dark theme): put each transparent diagram PNG on the slide-1 grain background,
cut at the diagram's own slide box, so the grain runs through without a visible edge.
Boxes are in the 2400 x 1350 grid of s01_assets (5080 EMU per px); the printed EMU values are the
transforms the slide elements must get.
Run from the repo root: PYTHONPATH=deck_v2 venv/bin/python deck_v2/dark_tiles.py"""
from PIL import Image

from s01_assets import EMU_PX, background

BOX = (126, 270, 2142, 1000)         # the area under a one-line 28 pt title, the same on slides 2-12
SRC = {"s03": "s03_mission", "s04": "s04_wiring", "s05": "s05_loadouts", "s06": "s06_power",
       "s07": "s07_failsafe", "s08": "s08_sitl", "s10": "s10_log", "s11": "s11_autotune", "s13": "s13_next",
       "s14": "s14_rfsearch", "s15": "s15_scenarios"}
TILES = {key: BOX for key in SRC}

bg = background()
for key, (x, y, w, h) in TILES.items():
    fg = Image.open(f"deck_v2/{SRC[key]}.png").convert("RGBA").resize((w, h), Image.LANCZOS)
    t = bg.crop((x, y, x + w, y + h)).convert("RGBA")
    t.alpha_composite(fg)
    t.convert("RGB").save(f"deck_v2/dark/{key}_dark.jpg", quality=93, subsampling=0)
    print(key, "translate", x * EMU_PX, y * EMU_PX, "size", w * EMU_PX, h * EMU_PX)
