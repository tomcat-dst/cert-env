"""Slide 1: key-figure strip under the title block (numbers from the deck and the 25.11 RC-loss flight of the two-source mission).
Dark theme of slide 1: background #121C17, green accent."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import diag as d  # noqa: F401  (sets the Noto Sans / DejaVu fonts)

BG, ACC, MUTED, SEP = "#121C17", "#4CC38A", "#A8B0BA", "#3A414B"

W, H = 100.0, 8.8
fig = plt.figure(figsize=(16, 16 * H / W), dpi=150)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
items = [("5,0 кг", "базова маса"), ("1,96 м", "розмах"), ("2 год 02 хв", "на 900 м, SITL"),
         ("76 км", "місія, 54 хв без RC"), ("0,60 м/с", "автопосадка"), ("16° → 2°", "крен після AUTOTUNE")]
w = W / len(items)
for i, (big, small) in enumerate(items):
    x = i * w + 0.5
    if i:
        ax.plot([x - 0.9, x - 0.9], [1.2, 7.6], color=SEP, lw=1.2)
    ax.text(x + 0.6, 7.6, big, fontsize=26, fontweight="bold", color=ACC, va="top")
    ax.text(x + 0.6, 2.2, small, fontsize=15, color=MUTED, va="bottom")
# opaque, in the slide's colour: Slides drew this strip's transparent pixels black
fig.patch.set_facecolor(BG)
fig.savefig("deck_v2/s01_strip_dark.png", facecolor=BG)
