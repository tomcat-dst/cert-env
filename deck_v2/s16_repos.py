"""Slide (code, after the conclusions): the two public forks and the private working repo, with what each holds.

Commit lists from `git log Plane-4.7.3..cert-rfsearch` (src/ardupilot) and `git log 3a67d31..rf-scan-overlay`
(src/qgroundcontrol); visibility from the GitHub API. The repo names are left out of the image: they are clickable
text boxes on the slide (LINK_Y below is where they go).
"""
import segno

import diag as d

d.H = 46.7                      # one-line title at 28 pt
fig, ax = d.canvas()
LINK_Y = 42.7                   # top of the clickable repo line, in slide units
QR_SIDE = 9.0

repos = [
    ("ArduPilot (форк)", d.GOOD, "https://github.com/tomcat-dst/ardupilot/tree/cert-rfsearch",
     "гілка cert-rfsearch · база Plane-4.7.3",
     "9 комітів:",
     ["SITL: маса й інерція з JSON-моделі", "SITL: мотор, гвинт і батарея", "SITL: трубка Піто без подвійного EAS",
      "SITL: корельована турбулентність", "SITL: катапульта в JSON-моделі", "Plane: режим RFSEARCH (№ 27)",
      "Tools: одиниця dBm для параметрів", "Plane: RFS_MIN_LEG 500 м", "Plane: кола тривають без RC"]),
    ("QGroundControl (форк)", d.C["uart"], "https://github.com/tomcat-dst/qgroundcontrol/tree/rf-scan-overlay",
     "гілка rf-scan-overlay · база 3a67d31",
     "2 коміти:",
     ["карта пеленгів: промені, еліпси 1σ,", "справжні джерела (лише в SITL)", "режим RFSearch у списку режимів",
      "метадані Plane 4.7 з групою RFS_:", "опис параметрів RFS_ у QGC"]),
    ("Робоче середовище", d.C["usb"], None,
     "приватний репозиторій · гілка main",
     "що всередині:",
     ["rf_companion.py: синтетичний канал,", "пеленги, оцінки з еліпсами",
      "mission.py: SITL + QGC, втрата RC", "моделі Believer (AVL, JSON), параметри", "плани місій QGC (.plan)",
      "аналіз логів, серії польотів RFSEARCH", "слайди й рисунки звіту (Python)",
      "patches/: коміти форків для git am"]),
]

w, gap = 32.0, 1.5
for i, (title, col, url, branch, head, items) in enumerate(repos):
    x = 0.5 + i * (w + gap)
    d.box(ax, x, 0.5, w, d.H - 1.0, None, ec=col, lw=2.2)
    d.note(ax, x + 1, d.H - 1.4, title, size=19, color=col, va="top", bold=True)
    d.note(ax, x + 1, LINK_Y - 2.6, branch, size=12.5, va="top")
    ax.plot([x + 1, x + w - 1], [LINK_Y - 5.2, LINK_Y - 5.2], color=d.LINE, lw=1, zorder=3)
    d.note(ax, x + 1, LINK_Y - 6.0, head, size=13.5, color=d.INK, va="top", bold=True)
    for j, ln in enumerate(items):
        d.note(ax, x + 1, LINK_Y - 8.4 - j * 2.05, ln, size=13, va="top")
    if url:                     # QR to the branch, bottom right of the box
        q = segno.make(url, error="m")
        m = [[1 - v for v in row] for row in q.matrix_iter(border=2)]
        x1, y1 = x + w - 1.0 - QR_SIDE, 1.5
        ax.imshow(m, cmap="gray", interpolation="nearest", extent=(x1, x1 + QR_SIDE, y1, y1 + QR_SIDE), zorder=4)
        ax.set_xlim(0, d.W)
        ax.set_ylim(0, d.H)
        ax.set_aspect("auto")
d.save(fig, "deck_v2/s16_repos.png")
