"""
Small helpers for the v2 deck schematics (matplotlib, Noto Sans, transparent background).

Coordinates are in "slide units": the canvas is W x H with the aspect of the area under a slide
title (10.88 M x 4.75 M EMU, about 2.29 : 1). Font sizes are chosen for a 16 in wide figure that
is placed 11.9 in wide on the slide, so a size here shrinks by about 0.74 on the slide.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# Noto Sans has no arrows (→ ↔); DejaVu Sans fills in those glyphs
plt.rcParams["font.family"] = ["Noto Sans", "DejaVu Sans"]

W, H = 100.0, 43.7
# dark theme of the v2 deck (slide 1: grain background #121C17, green accent); set DECK_THEME=light
# for the original white-slide colours
DARK = os.environ.get("DECK_THEME", "dark") == "dark"
if DARK:
    INK, MUTED, LINE = "#F2F2F2", "#A8B0BA", "#56635C"
    BOX, PANEL = "#18241E", "#1A2822"
    GOOD = "#4CC38A"      # done / verified
    C = {
        "uart": "#6CB4FF",
        "rc": "#B48CFF",
        "i2c": "#3FD0C0",
        "pwm": "#4CC38A",
        "power": "#FF6B5A",
        "usb": "#F0A640",
        "rf": "#9AA3AD",
    }
else:
    INK, MUTED, LINE = "#1E1E1E", "#6B6B6B", "#3A3A3A"
    BOX, PANEL = "#FFFFFF", "#EEF2F7"
    GOOD = "#2E8B2E"
    # one colour per kind of connection, used consistently on every slide
    C = {
        "uart": "#1A6BB8",    # MAVLink / serial data
        "rc": "#7A3DB8",      # RC link (CRSF / ELRS)
        "i2c": "#0F8A7E",     # I2C sensors
        "pwm": "#2E8B2E",     # PWM outputs
        "power": "#C8361B",   # battery / power
        "usb": "#B86E00",     # USB
        "rf": "#8C8C8C",      # radio / network, dashed
    }


def canvas(w_in=16.0):
    fig = plt.figure(figsize=(w_in, w_in * H / W), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    fig.patch.set_alpha(0)
    return fig, ax


def fit_h(title=None, lines=(), title_size=17, line_size=14):
    """Height a box needs for its title and lines (same metrics as box())."""
    h = 0.9 + 0.7
    if title:
        h += title_size * 0.095 + 0.5
    h += len(lines) * (line_size * 0.095 + 0.35)
    return h


def box(ax, x, y, w, h, title=None, lines=(), fc=BOX, ec=LINE, title_size=17, line_size=14,
        bold=True, align="left", lw=1.6, title_color=INK):
    """Rounded box with a bold title and smaller detail lines; (x, y) is the lower-left corner.
    h=None sizes the box to its content."""
    if h is None:
        h = fit_h(title, lines, title_size, line_size)
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.6",
                                fc=fc, ec=ec, lw=lw, zorder=2))
    tx = x + 0.8 if align == "left" else x + w / 2
    ha = "left" if align == "left" else "center"
    yy = y + h - 0.9
    if title:
        ax.text(tx, yy, title, ha=ha, va="top", fontsize=title_size, color=title_color,
                fontweight="bold" if bold else "normal", zorder=3)
        yy -= title_size * 0.095 + 0.5
    for ln in lines:
        ax.text(tx, yy, ln, ha=ha, va="top", fontsize=line_size, color=MUTED, zorder=3)
        yy -= line_size * 0.095 + 0.35
    return (x, y, w, h)


def panel(ax, x, y, w, h, label=None, size=13):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.8",
                                fc=PANEL, ec="none", zorder=0))
    if label:
        ax.text(x + 0.8, y + h - 0.6, label, ha="left", va="top", fontsize=size, color=MUTED,
                fontweight="bold", zorder=1)


def wire(ax, pts, kind, label=None, lpos=0.5, loff=(0, 0.6), size=13, arrow=None, lw=2.6,
         dashed=False, ha="center"):
    """Polyline through pts; optional label at fraction lpos of the way along segment 0..n."""
    col = C[kind]
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=col, lw=lw, solid_capstyle="round", zorder=1,
            linestyle=(0, (4, 2.5)) if dashed or kind == "rf" else "-")
    if arrow:
        (x0, y0), (x1, y1) = (pts[-2], pts[-1]) if arrow == "end" else (pts[1], pts[0])
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=22,
                                     color=col, lw=0, zorder=1))
    if label:
        n = len(pts) - 1
        seg = min(int(lpos * n), n - 1)
        f = lpos * n - seg
        (x0, y0), (x1, y1) = pts[seg], pts[seg + 1]
        lx, ly = x0 + (x1 - x0) * f + loff[0], y0 + (y1 - y0) * f + loff[1]
        ax.text(lx, ly, label, ha=ha, va="bottom", fontsize=size, color=col, fontweight="bold",
                zorder=3)


def pin(ax, x, y, text, side="left", kind="uart", size=13):
    """Port label sitting on a box edge, coloured by connection kind."""
    ax.text(x + (0.5 if side == "left" else -0.5), y, text, ha="left" if side == "left" else "right",
            va="center", fontsize=size, color=C[kind], fontweight="bold", zorder=3)


def legend(ax, x, y, kinds, size=12, step=13.5):
    names = {"uart": "UART / MAVLink", "rc": "RC (CRSF)", "i2c": "I2C", "pwm": "PWM",
             "power": "живлення", "usb": "USB", "rf": "радіо / мережа"}
    for i, k in enumerate(kinds):
        xx = x + i * step
        ax.plot([xx, xx + 2.2], [y, y], color=C[k], lw=3,
                linestyle=(0, (4, 2.5)) if k == "rf" else "-")
        ax.text(xx + 2.8, y, names[k], va="center", fontsize=size, color=MUTED)


def note(ax, x, y, text, size=12, color=MUTED, ha="left", va="bottom", bold=False):
    ax.text(x, y, text, ha=ha, va=va, fontsize=size, color=color,
            fontweight="bold" if bold else "normal", zorder=3)


def table(ax, x, y_top, col_x, rows, size=12.5, row_h=2.6, header=True, colors=None):
    """Rows of cells at fixed column offsets (proportional fonts don't line up with spaces)."""
    for r, row in enumerate(rows):
        yy = y_top - r * row_h
        for c, cell in enumerate(row):
            bold = header and r == 0
            col = (colors[r] if colors and colors[r] else (INK if bold else MUTED))
            ax.text(x + col_x[c], yy, cell, ha="left", va="top", fontsize=size, color=col,
                    fontweight="bold" if bold else "normal", zorder=3)


def save(fig, path):
    fig.savefig(path, transparent=True)
    plt.close(fig)
