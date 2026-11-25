"""Chart styling shared by the v2 deck plots (same fonts and colours as diag.py)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import diag as d

if d.DARK:
    ACC, ACC2, GREY = "#4CC38A", "#2F6B50", "#7E8790"
    SPINE, GRID = "#56635C", "#26332C"
else:
    ACC, ACC2, GREY = "#1A6BB8", "#9BB8D8", "#8C8C8C"
    SPINE, GRID = "#9A9A9A", "#DADADA"


def axes(fig, rect, xlabel=None, ylabel=None, size=14):
    ax = fig.add_axes(rect)
    ax.patch.set_alpha(0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(SPINE)
    ax.tick_params(colors=d.MUTED, labelsize=size)
    ax.grid(axis="y", color=GRID, lw=0.8)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=size, color=d.MUTED)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=size, color=d.MUTED)
    return ax


def figure(w_in, h_in):
    fig = plt.figure(figsize=(w_in, h_in), dpi=150)
    fig.patch.set_alpha(0)
    return fig
