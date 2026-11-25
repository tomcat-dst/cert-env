#!/usr/bin/env python3
"""
Companion computer for the RF direction-finding demo (Pi Zero 2 W + tinySA on the aircraft, here
synthetic). Connects to SITL's SERIAL2 the way the Pi sits on a telemetry port, and:

1. Simulates the analyzer: received power from hidden omnidirectional noise sources (50 W each, one
   frequency, so the analyzer sees their sum) through a nose-mounted axial-mode helix (~12 turns, ~0.5 m at
   1.8 GHz: 15 dBi, 30 deg beam, -3 dB at +-15 deg, sidelobes -20 dB). Path loss is free space to 100 m, then 30 dB per decade
   (ground-level propagation), plus 1.5 dB fading per source and a -110 dBm noise floor. The angle off
   boresight comes from the aircraft's real attitude and position. Scenario "single" (one source,
   tsuniv_rf_search.plan) or "multi" (three, tsuniv_rf_multi.plan); by default from the plan.
2. During each half-loiter (LOITER_TURNS with fewer than 1 turn in the plan) records power against
   heading. A plan without half-loiters is flown in RFSEARCH (ArduPlane mode 27, ArduPlane/rf_search.cpp):
   the autopilot weaves the nose through the course +-90 deg every RFS_SPACING m while our reading
   (RF_dBm, sent to it on every sample) is above RFS_THR_DBM, and reports the weave as
   NAMED_VALUE_FLOAT RFS_SWP (0 tracking, 1-4 sweeping); each weave is then one observation. Unless at least MIN_VALID readings clear the detection threshold VALID_DBM, reports no
   detection. Otherwise fits the antenna pattern: one beam (single) or several (multi, fitted in dB),
   each peak a bearing from where the aircraft was when its nose pointed that way.
3. Single: crosses the two bearings and refines the fix with the on-axis power difference (the
   distance ratio, with the path-loss exponent known and the source power not). Multi: candidate
   positions where bearings from >= 3 points agree, then the subset of candidates that best explains
   the recorded readings (BIC), which rejects ghost crossings, and positions refined against them. The
   readings include the straight legs between loiters: they give no bearing (the heading hardly
   changes) but power against position still constrains where the sources are.
4. Sends everything to QGC through the autopilot (broadcast MAVLink is forwarded to the GCS link):
   NAMED_VALUE_FLOAT RF_dBm (live), DEBUG_FLOAT_ARRAY RF_BRG (each bearing) and RF_FIX (each source),
   RF_TRU (each simulated source's true position, unless --hide-truth),
   which our QGC build draws (src/qgroundcontrol branch rf-scan-overlay), and STATUSTEXT messages. At
   the end it reveals the errors against the hidden true positions (simulation only).

  compare/rf_companion.py --plan sim/missions/tsuniv_rf_search.plan --out <dir> [--instance 0]

Started by compare/mission.py --rf. Outputs: <out>/rf_samples.csv, <out>/rf_result.json.
"""
import argparse
import csv
import itertools
import json
import math
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from pymavlink import mavutil

# hidden source (simulation truth, never used by the estimator): 13.8 km out on the launch heading,
# ~1.8 km off the search-area centre the plan aims at
SOURCE = (49.7999384, 23.8795259)
# several sources on one frequency for tsuniv_rf_multi.plan (truth only): (along, across) offsets
# (17.8, 1.8), (21.5, -1.5), (23.2, 2.2) km from home on the launch heading, 3.9-5.4 km apart
SCENARIOS = {"single": [(*SOURCE, 47.0)],
             "multi": [(49.7584654, 23.916365, 47.0), (49.7756929, 23.9801122, 47.0), (49.7392535, 23.9857272, 47.0)],
             # a second set inside tsuniv_rf_ellipse.plan, (along, across) (15.5, -3.0), (19.5, 3.5), (18.0, -6.0) km:
             # 3.9-9.6 km apart, 3-6.7 km inside the route abeam, none within 2.4 km of a "multi" source
             "multi_b": [(49.8060152, 23.9078339, 47.0), (49.7390325, 23.9310572, 47.0), (49.8242052, 23.9544023, 47.0)]}
# per-peak bearing sigma = hypot(PEAK_SIGMA_SCALE * fit sigma, PEAK_SIGMA_FLOOR_DEG): calibrated on 120
# offline-study peaks against their true bearings (66 % within 1 sigma, 98 % within 2; median ~2 deg).
# The raw fit sigma tracks the error (correlation 0.82) and widens for weak peaks, but assumes
# independent readings, which neighbouring readings in a sweep are not.
PEAK_SIGMA_SCALE, PEAK_SIGMA_FLOOR_DEG = 3.0, 1.25
# source ellipses from the bearings are too large once the position is refined against all readings:
# x0.6 puts the true source inside the 2-sigma ellipse in 87 % of 30 offline fixes (86 % expected for a
# 2-D Gaussian), 53 % inside 1 sigma (39 % expected), 100 % inside 3 sigma
ELLIPSE_SCALE = 0.6
MERGE_M = 1500.0                         # refined fixes closer than this are one source
# estimator v2 (2026-11-25): each update used to start from scratch, so a source with two near-equal
# solutions (two sources overlapping from most of the route) flipped between them, and re-assigning
# every bearing could drop most of a source's bearings and blow its ellipse up. v2: the previous
# estimate is a prior in the position refinement, a bearing keeps its source while within STICKY_GATE
# sigma, bearings that fit two sources are left out of the ellipses, and an ellipse is widened when
# the refined position disagrees with its own bearings' crossing
ESTIMATOR_V2 = True
STICKY_GATE = 5.0                        # sigma; a new assignment needs the usual 3
PRIOR_MATCH_M, PRIOR_SCALE, PRIOR_MIN_M = 2000.0, 2.0, 150.0   # prior sigma = max(scale x previous, min)
MOVED_WARN_MIN_BRG = 4                   # "moved outside its ellipse" only with at least this many bearings
EIRP_DBM, FREQ_HZ = 47.0, 1.8e9          # 50 W noise source; only sets the power level
PL_EXP, D0_M = 3.0, 100.0                # log-distance path loss beyond D0 (free space below)
G0_DBI, BEAM_DEG, BACK_DB = 15.0, 30.0, 20.0    # helix; was a 45 deg, 8 dBi patch until 2026-11-24
# the helix is mounted tilted down: from 900 m, sources 3-10 km away are 5-17 deg below the horizon. Tilted,
# its boresight swings with roll (sin(tilt) sin(roll): ~5 deg sideways at 30 deg bank), so every reading
# carries the boresight from the aircraft's attitude (the Pi has it over MAVLink), not the heading
TILT_DEG = 10.0
# a lone source falls 3 dB by BEAM_DEG / 2 either side of its peak; a peak whose fitted -3 dB width
# (peak_width, the sweep's other peaks modelled) is more than WIDE_MARGIN_DEG over the beam is several sources
# the multi-peak fit could not separate (with this beam: closer than ~20 deg): flagged, and its bearing sigma
# doubled (it leans towards the stronger one). Off since 2026-11-24: in flight a lone source fits 26-51 deg wide
# and pairs 8-15 deg apart widen it by only 1-5 deg, so it raised more false alarms than real ones. The width is
# still measured and sent (RF_BRG width); telling one source from several is left to the position fit (BIC)
WIDE_FLAG = False
WIDE_MARGIN_DEG = 3.0
FADING_DB, FLOOR_DBM = 1.5, -110.0
VALID_DBM, MIN_VALID = -95.0, 20         # detection threshold (15 dB over the floor), samples needed
RATIO_SIGMA_DB = 1.0                     # assumed error of the on-axis power difference between the two
                                         # points (fit + model); real shadowing (4-8 dB) is far worse
SAMPLE_S = 0.2                           # analyzer sweep period, sim seconds
RESEND_S = 3.0                           # bearings and sources re-sent to the GCS this often, wall s
LEG_STEP, LEG_MIN_ALT = 15, 100.0        # readings outside the loiters used in the source fit: every 15th
                                         # (one per 3 s of flight) above 100 m. In replays of two flights
                                         # this improved 5 of 6 fixes (e.g. 46/73/234 -> 14/65/214 m) at
                                         # ~2.5x the time; every 5th was better on one flight, worse on
                                         # the other and ~7x slower
R_EARTH = 6371000.0
LOITER_TURNS = 18


def gain_db(off_deg):
    return G0_DBI - min(12.0 * (off_deg / BEAM_DEG) ** 2, BACK_DB)


def ned(frm, to):
    """North/east metres from frm to to (lat, lon), local flat earth."""
    return (math.radians(to[0] - frm[0]) * R_EARTH,
            math.radians(to[1] - frm[1]) * R_EARTH * math.cos(math.radians(frm[0])))


def latlon(base, n, e):
    return (base[0] + math.degrees(n / R_EARTH),
            base[1] + math.degrees(e / (R_EARTH * math.cos(math.radians(base[0])))))


def path_loss_db(d):
    fspl = lambda x: 20 * math.log10(x) + 20 * math.log10(FREQ_HZ) - 147.55   # noqa: E731
    return fspl(d) if d <= D0_M else fspl(D0_M) + 10 * PL_EXP * math.log10(d / D0_M)


def cross(p1, b1, p2, b2):
    """Intersection of two bearings (deg) from p1, p2 (lat, lon): position, ranges t1, t2."""
    n2, e2 = ned(p1, p2)
    u1 = (math.cos(math.radians(b1)), math.sin(math.radians(b1)))
    u2 = (math.cos(math.radians(b2)), math.sin(math.radians(b2)))
    det = u1[0] * (-u2[1]) - u1[1] * (-u2[0])
    if abs(det) < 1e-6:
        return None
    t1 = (n2 * (-u2[1]) - e2 * (-u2[0])) / det
    t2 = (u1[0] * e2 - u1[1] * n2) / det
    return latlon(p1, t1 * u1[0], t1 * u1[1]), t1, t2


def refine(obs1, obs2, start, span=3000.0, step=25.0):
    """Joint fix from both bearings and the on-axis power difference (A1 - A2 = 10 n log10(d2 / d1)),
    by grid search around the bearing crossing `start`. Returns position, 1-sigma radius (the
    chi-square + 1 region) and the distance ratio d1/d2 the powers alone imply."""
    def cost(pos):
        j, d = 0.0, []
        for o in (obs1, obs2):
            n, e = ned(o["pos"], pos)
            j += (((math.degrees(math.atan2(e, n)) - o["bearing"] + 180) % 360 - 180) / o["sigma"]) ** 2
            d.append(math.hypot(math.hypot(n, e), o["alt"]))
        model = 10 * PL_EXP * math.log10(d[1] / d[0])
        return j + ((obs1["peak_dbm"] - obs2["peak_dbm"] - model) / RATIO_SIGMA_DB) ** 2

    k = int(span / step)
    cells = [(cost(latlon(start, i * step, j * step)), i * step, j * step)
             for i in range(-k, k + 1) for j in range(-k, k + 1)]
    best = min(cells)
    sig = max(math.hypot(n - best[1], e - best[2]) for c, n, e in cells if c <= best[0] + 1.0)
    ratio = 10 ** (-(obs1["peak_dbm"] - obs2["peak_dbm"]) / (10 * PL_EXP))
    return latlon(start, best[1], best[2]), max(sig, step), ratio


# --- several sources on one frequency (multi-source mission) ---------------------------------------

def boresight(roll, pitch, yaw, tilt_deg=TILT_DEG):
    """Unit vector (north, east, down) of the antenna axis: the body x axis tilted down by tilt_deg, rotated
    by the aircraft's roll, pitch and yaw (rad)."""
    t = math.radians(tilt_deg)
    x, y, z = math.cos(t), 0.0, math.sin(t)                        # body frame: forward, right, down
    y, z = y * math.cos(roll) - z * math.sin(roll), y * math.sin(roll) + z * math.cos(roll)
    x, z = x * math.cos(pitch) + z * math.sin(pitch), -x * math.sin(pitch) + z * math.cos(pitch)
    x, y = x * math.cos(yaw) - y * math.sin(yaw), x * math.sin(yaw) + y * math.cos(yaw)
    return x, y, z


def received_dbm_multi(pos, alt, roll, pitch, yaw, rng, sources):
    """Summed power of several sources (independent fading each) through the nose antenna."""
    total = 10 ** (FLOOR_DBM / 10)
    nose = boresight(roll, pitch, yaw)
    for lat, lon, eirp in sources:
        n, e = ned(pos, (lat, lon))
        rng3 = math.sqrt(n * n + e * e + alt * alt)
        cosang = (n * nose[0] + e * nose[1] + alt * nose[2]) / rng3
        off = math.degrees(math.acos(max(-1.0, min(1.0, cosang))))
        total += 10 ** ((eirp - path_loss_db(rng3) + gain_db(off) + rng.gauss(0, FADING_DB)) / 10)
    return 10 * math.log10(total)


def fit_peaks(samples, max_peaks=4, edge_deg=15.0, min_gain=25.0):
    """Several beams in one sweep, fitted in dB (fading is multiplicative): the model is
    10 log10(floor + sum of A_j * beam(heading - b_j)). Peaks are added one at a time (grid over
    bearing and on-axis power, then all refined) while each improves the sum of squares by more than
    min_gain fading variances. Returns peaks (bearing, on-axis dBm, statistical bearing sigma in deg) at
    or above VALID_DBM and at least edge_deg inside the swept arc, strongest first. The sigma is how far
    the peak's bearing can move (others fixed, power re-fitted) before the misfit grows by one residual
    variance: wide for a weak or flat peak, narrow for a strong sharp one."""
    hd = np.array([s["yaw"] for s in samples])
    p = np.array([s["dbm"] for s in samples])
    floor = 10 ** (FLOOR_DBM / 10)

    def g(b):
        d = (hd[None, :] - np.atleast_1d(b)[:, None] + 180) % 360 - 180
        return 10 ** (-np.minimum(12 * (d / BEAM_DEG) ** 2, BACK_DB) / 10)

    def lin_sum(peaks, skip=None):
        tot = np.full_like(p, floor)
        for i, (b, a) in enumerate(peaks):
            if i != skip:
                tot = tot + 10 ** (a / 10) * g(b)[0]
        return tot

    def best_one(base, bearings, amps):
        """Best (bearing, dBm) for one more beam on top of `base` (linear), over a grid."""
        gb = g(bearings)                                          # B x N
        model = base[None, None, :] + (10 ** (amps / 10))[None, :, None] * gb[:, None, :]
        sse = ((p[None, None, :] - 10 * np.log10(model)) ** 2).sum(axis=2)   # B x A
        i, j = np.unravel_index(int(np.argmin(sse)), sse.shape)
        return float(bearings[i]), float(amps[j]), float(sse[i, j])

    def profile(base, bearings, amps):
        """Misfit against bearing, power re-fitted at each."""
        gb = g(bearings)
        model = base[None, None, :] + (10 ** (amps / 10))[None, :, None] * gb[:, None, :]
        return ((p[None, None, :] - 10 * np.log10(model)) ** 2).sum(axis=2).min(axis=1)

    peaks = []
    sse_now = float(((p - 10 * np.log10(lin_sum(peaks))) ** 2).sum())
    lo, hi = hd.min(), hd.max()
    span = np.arange(0.0, 360.0, 1.0)
    for _ in range(max_peaks):
        b, a, sse = best_one(lin_sum(peaks), span, np.arange(-110.0, -35.0, 1.0))
        if sse_now - sse < min_gain * FADING_DB ** 2:
            break
        peaks.append([b, a])
        for _ in range(3):                                       # refine every peak, others fixed
            for j, (bj, aj) in enumerate(peaks):
                peaks[j][0], peaks[j][1], sse = best_one(lin_sum(peaks, skip=j), bj + np.arange(-6, 6.01, 0.25),
                                                         aj + np.arange(-3, 3.01, 0.25))
            for j, (bj, aj) in enumerate(peaks):
                peaks[j][0], peaks[j][1], sse = best_one(lin_sum(peaks, skip=j), bj + np.arange(-1, 1.01, 0.05),
                                                         aj + np.arange(-0.5, 0.51, 0.05))
        sse_now = sse
    res_var = sse_now / max(len(p) - 2 * len(peaks), 1)
    out = []
    for j, (b, a) in sorted(enumerate(peaks), key=lambda x: -x[1][1]):
        rel = (hd - b + 180) % 360 - 180
        if rel.min() > -edge_deg or rel.max() < edge_deg or a < VALID_DBM:
            continue
        offsets = np.arange(-8.0, 8.01, 0.1)
        prof = profile(lin_sum(peaks, skip=j), b + offsets, a + np.arange(-2.0, 2.01, 0.1))
        inside = offsets[prof <= prof.min() + res_var]
        out.append((b % 360, a, float(max(np.abs(inside).max(), 0.1))))
    return out


def peak_width(samples, bearing, others=(), span=BEAM_DEG):
    """-3 dB width (deg) of one beam fitted to the readings within +-span of `bearing`, its width free (in dB,
    over a grid of width, centre offset and on-axis power), with the sweep's other fitted peaks `others`
    ((bearing, on-axis dBm)) as fixed beams of the nominal width, so their skirts do not widen this one. Uses
    every reading, so fading averages out: in an offline study a lone source fitted 28-31 deg (beam 30), two
    sources 10 deg apart 30-34, 15 deg apart 33-37. None if the readings do not cover half a beam on both
    sides."""
    hd = np.array([s["yaw"] for s in samples])
    p = np.array([s["dbm"] for s in samples])
    rel = (hd - bearing + 180) % 360 - 180
    m = np.abs(rel) <= span
    if m.sum() < 8 or rel[m].min() > -0.5 * BEAM_DEG or rel[m].max() < 0.5 * BEAM_DEG:
        return None
    rel, p, hd = rel[m], p[m], hd[m]
    floor = np.full_like(p, 10 ** (FLOOR_DBM / 10))
    for b2, a2 in others:
        off = np.abs((hd - b2 + 180) % 360 - 180)
        floor = floor + 10 ** ((a2 - np.minimum(12 * (off / BEAM_DEG) ** 2, BACK_DB)) / 10)
    widths = np.arange(15.0, 90.0, 1.0)
    centres = np.arange(-6.0, 6.5, 1.0)
    amps = np.arange(p.max() - 3, p.max() + 3.1, 0.5)
    d = rel[None, None, :] - centres[None, :, None]                              # 1 x C x N
    g = 10 ** (-np.minimum(12 * (d / widths[:, None, None]) ** 2, BACK_DB) / 10)  # W x C x N
    model = floor[None, None, None, :] + (10 ** (amps / 10))[:, None, None, None] * g[None]   # A x W x C x N
    sse = ((p - 10 * np.log10(model)) ** 2).sum(axis=3)
    return float(widths[np.unravel_index(int(np.argmin(sse)), sse.shape)[1]])


def peak_origin(samples, bearing, window=10.0):
    """Where the aircraft was while its nose pointed within `window` deg of `bearing`: the origin of
    that bearing (the loiter circle shifts it by up to the radius)."""
    near = [s for s in samples if abs(((s["yaw"] - bearing + 180) % 360) - 180) < window] or samples
    return sum(s["lat"] for s in near) / len(near), sum(s["lon"] for s in near) / len(near)


def locate(bearings, centre, half_size=9000.0, step=50.0, min_obs=3, merge_m=1000.0, max_cands=10):
    """Sources from bearings taken at several points: a cell scores one per point that has a bearing
    through it (Gaussian in angle), so true sources collect >= min_obs points and two-bearing ghost
    crossings do not. Each candidate is refined by weighted least squares over the bearings
    associated with it. bearings: dicts with obs, pos (lat, lon), bearing, sigma (deg).
    Returns fixes: dicts with pos, sigma_m, n, obs, score."""
    xs = np.arange(-half_size, half_size + step / 2, step)
    nn, ee = np.meshgrid(xs, xs, indexing="ij")
    by_obs = {}
    for b in bearings:
        n, e = ned(centre, b["pos"])
        by_obs.setdefault(b["obs"], []).append((n, e, b["bearing"], max(b["sigma"], 2.0)))
    score = np.zeros_like(nn)
    for lst in by_obs.values():
        best = np.zeros_like(nn)
        for n, e, brg, s in lst:
            az = np.degrees(np.arctan2(ee - e, nn - n))
            best = np.maximum(best, np.exp(-0.5 * (((az - brg + 180) % 360 - 180) / s) ** 2))
        score += best
    fixes = []
    order = np.argsort(score, axis=None)[::-1]
    for idx in order[:4000]:
        i, j = np.unravel_index(idx, score.shape)
        if score[i, j] < min_obs - 0.5:
            break
        if any(math.hypot(nn[i, j] - f[0], ee[i, j] - f[1]) < merge_m for f in fixes):
            continue
        fixes.append((nn[i, j], ee[i, j], score[i, j]))
    out = []
    for n0, e0, sc in fixes:
        x = np.array([n0, e0])
        for _ in range(8):                        # Gauss-Newton over the associated bearings
            rows, res, w, used = [], [], [], set()
            for o, lst in by_obs.items():
                cand = []
                for n, e, brg, s in lst:
                    dn, de = x[0] - n, x[1] - e
                    err = ((math.degrees(math.atan2(de, dn)) - brg + 180) % 360) - 180
                    if abs(err) < 3 * s:
                        cand.append((abs(err) / s, dn, de, err, s))
                if cand:
                    _, dn, de, err, s = min(cand)
                    r2 = dn * dn + de * de
                    rows.append([-de / r2, dn / r2])            # d(az rad)/d(n, e)
                    res.append(math.radians(err))
                    w.append(1 / math.radians(s) ** 2)
                    used.add(o)
            if len(rows) < 2:
                break
            a, rv, wv = np.array(rows), np.array(res), np.array(w)
            hess = (a * wv[:, None]).T @ a
            if np.linalg.cond(hess) > 1e12:
                break                             # bearings (nearly) parallel: nothing to cross
            step_v = np.linalg.solve(hess, -(a * wv[:, None]).T @ rv)
            x = x + step_v
            if np.hypot(*step_v) < 1.0:
                break
        if len(rows) < min_obs or np.linalg.cond(hess) > 1e12:
            continue
        # several grid peaks often refine onto the same point: keep the first (best-scored) of them
        if any(math.hypot(x[0] - o["ne"][0], x[1] - o["ne"][1]) < merge_m for o in out):
            continue
        cov = np.linalg.inv(hess)
        out.append(dict(pos=latlon(centre, x[0], x[1]), sigma_m=float(math.sqrt(max(np.linalg.eigvalsh(cov)))),
                        n=len(rows), obs=sorted(used), score=float(sc), ne=(float(x[0]), float(x[1]))))
    # select_sources tries every subset of up to 4: C(10, <=4) = 385 fits, C(52, <=4) would be ~290 000
    out = sorted(out, key=lambda c: -c["score"])[:max_cands]
    for o in out:
        del o["ne"]
    return out


def _model_terms(arr, pos):
    """Per-sample -path loss + antenna gain (dB) for a source at pos; arr holds numpy arrays of the
    samples' lat, lon, alt and boresight unit vector bn, be, bd (north, east, down)."""
    n = np.radians(pos[0] - arr["lat"]) * R_EARTH
    e = np.radians(pos[1] - arr["lon"]) * R_EARTH * np.cos(np.radians(arr["lat"]))
    r3 = np.sqrt(n * n + e * e + arr["alt"] ** 2)
    off = np.degrees(np.arccos(np.clip((n * arr["bn"] + e * arr["be"] + arr["alt"] * arr["bd"]) / r3, -1, 1)))
    fspl = lambda x: 20 * np.log10(x) + 20 * math.log10(FREQ_HZ) - 147.55      # noqa: E731
    pl = np.where(r3 <= D0_M, fspl(np.maximum(r3, 1.0)), fspl(D0_M) + 10 * PL_EXP * np.log10(np.maximum(r3, D0_M) / D0_M))
    return -pl + G0_DBI - np.minimum(12 * (off / BEAM_DEG) ** 2, BACK_DB)


def _sse(p, terms, eirp):
    floor = 10 ** (FLOOR_DBM / 10)
    return float(((p - 10 * np.log10(floor + (10 ** ((np.asarray(eirp)[:, None] + terms) / 10)).sum(axis=0))) ** 2).sum())


def _fit_eirp(p, terms, eirp=None, only=None):
    """Source powers by coordinate search (all, or just index `only`); returns sse, eirp."""
    eirp = np.full(len(terms), 45.0) if eirp is None else np.array(eirp, dtype=float)
    idx = range(len(eirp)) if only is None else [only]
    for step in (4.0, 1.0, 0.25):
        for _ in range(6 if only is None else 2):
            for k in idx:
                trials = np.clip(eirp[k] + np.arange(-6, 7) * step, 10.0, 70.0)
                vals = []
                for v in trials:
                    e2 = eirp.copy()
                    e2[k] = v
                    vals.append(_sse(p, terms, e2))
                eirp[k] = trials[int(np.argmin(vals))]
    return _sse(p, terms, eirp), eirp


def select_sources(samples, cands, max_k=4, weak_db=8.0, priors=()):
    """Which candidates are sources, and where exactly. Every subset of up to max_k candidates is
    fitted to all recorded readings (each source's power solved for) and the lowest BIC wins, so a
    ghost crossing that predicts readings nobody saw costs more than it explains. The chosen sources'
    positions are then refined against the raw readings (the full model separates overlapping beams
    that biased some bearings), with a 1-sigma radius from where the misfit grows by one residual
    variance. Sources more than weak_db below the strongest are returned as unconfirmed: with this
    beam, back lobe and fading they are not separable from fit artefacts (every ghost in the offline
    study and the first SITL run was 8-13 dB down, every real source within 2 dB)."""
    if not cands:
        return [], []
    arr = {k: np.array([s[k] for s in samples], dtype=float) for k in ("lat", "lon", "alt", "bn", "be", "bd")}
    p = np.array([s["dbm"] for s in samples])
    terms = [_model_terms(arr, c["pos"]) for c in cands]
    n = len(p)
    best = None
    for k in range(1, min(max_k, len(cands)) + 1):
        for sub in itertools.combinations(range(len(cands)), k):
            v, eirp = _fit_eirp(p, np.array([terms[i] for i in sub]))
            bic = n * math.log(v / n) + 3 * k * math.log(n)
            if best is None or bic < best[0]:
                best = (bic, sub, eirp)
    pos = [cands[i]["pos"] for i in best[1]]
    eirp = best[2]
    t = np.array([terms[i] for i in best[1]])
    sigma = [None] * len(pos)
    # v2: the previous estimate of the same source (within PRIOR_MATCH_M) is a Gaussian prior on its position,
    # in units of the residual variance, so the refinement does not flip to a second near-equal minimum
    prior = [None] * len(pos)
    res_var0 = _fit_eirp(p, t)[0] / n
    for k in range(len(pos)):
        near = [q for q in priors if math.hypot(*ned(q["pos"], pos[k])) < PRIOR_MATCH_M]
        if near:
            q = min(near, key=lambda q: math.hypot(*ned(q["pos"], pos[k])))
            prior[k] = (q["pos"], max(PRIOR_SCALE * q["sigma_m"], PRIOR_MIN_M))
    for _ in range(3):                            # refine each position, the others fixed
        for k in range(len(pos)):
            for span, step in ((800.0, 100.0), (150.0, 15.0)):
                cells = []
                for dn in np.arange(-span, span + step / 2, step):
                    for de in np.arange(-span, span + step / 2, step):
                        q = latlon(pos[k], dn, de)
                        t2 = t.copy()
                        t2[k] = _model_terms(arr, q)
                        v, e2 = _fit_eirp(p, t2, eirp, only=k)
                        if prior[k] is not None:
                            v += res_var0 * (math.hypot(*ned(prior[k][0], q)) / prior[k][1]) ** 2
                        cells.append((v, dn, de, q, e2))
                v0, dn0, de0, q0, e0 = min(cells, key=lambda c: c[0])
                res_var = v0 / n if prior[k] is None else res_var0
                sigma[k] = max([math.hypot(c[1] - dn0, c[2] - de0) for c in cells if c[0] <= v0 + res_var] + [step])
                pos[k], eirp = q0, e0
                t[k] = _model_terms(arr, q0)
    strongest = max(eirp)
    out, weak = [], []
    for i in sorted(range(len(pos)), key=lambda j: -eirp[j]):
        # two fixes this close are one source split between candidates (the beam cannot resolve them)
        if any(math.hypot(*ned(pos[i], f["pos"])) < MERGE_M for f in out + weak):
            continue
        c = best[1][i]
        # the misfit radius ignores correlated model errors (47-54 m reported against 81-112 m actual in
        # the first replay), so the larger, bearing-geometry radius of the candidate is reported
        f = dict(cands[c], pos=pos[i], sigma_m=max(float(sigma[i]), cands[c]["sigma_m"]), sigma_fit_m=float(sigma[i]),
                 eirp_dbm=float(eirp[i]))
        (out if eirp[i] >= strongest - weak_db else weak).append(f)
    return sorted(out, key=lambda f: -f["eirp_dbm"]), weak


def bearing_ellipse(pos, bearings, scale=ELLIPSE_SCALE):
    """1-sigma error ellipse of a source at pos from the bearings pointing at it, each weighted by its
    own sigma: covariance inv(J^T W J) of the position from the bearing residuals, times `scale`
    (ELLIPSE_SCALE for the multi-source fixes, refined against all readings; 1 for the single-source
    bearing crossing, which has no such refinement). Returns semi-major,
    semi-minor (m) and the azimuth of the major axis (deg), or None with fewer than two bearings."""
    rows, w = [], []
    for b in bearings:
        n, e = ned(b["pos"], pos)
        r2 = n * n + e * e
        rows.append([-e / r2, n / r2])
        w.append(1.0 / math.radians(b["sigma"]) ** 2)
    if len(rows) < 2:
        return None
    a = np.array(rows)
    info = (a * np.array(w)[:, None]).T @ a
    if np.linalg.cond(info) > 1e12:
        return None
    vals, vecs = np.linalg.eigh(np.linalg.inv(info))
    major = vecs[:, 1]
    return (scale * float(math.sqrt(vals[1])), scale * float(math.sqrt(vals[0])),
            float(math.degrees(math.atan2(major[1], major[0])) % 180))


def assign_bearings(bearings, fixes, gate=3.0, prev=None):
    """Which source each bearing points at: pairs within `gate` (in units of max(sigma, 2 deg)) of the
    direction from the bearing's origin to a fix, closest first, at most one bearing per observation
    point per source. fixes: {id: fix}. Returns {bearing id: source id} (unassigned bearings left out)."""
    pairs = []
    for b in bearings:
        for sid, f in fixes.items():
            n, e = ned(b["pos"], f["pos"])
            err = abs(((math.degrees(math.atan2(e, n)) - b["bearing"] + 180) % 360) - 180) / max(b["sigma"], 2.0)
            # v2: a bearing keeps the source it had while within STICKY_GATE, ahead of any new pairing
            kept = prev is not None and prev.get(b["id"]) == sid and err < STICKY_GATE
            if err < gate or kept:
                pairs.append((err - 100.0 if kept else err, b["id"], b["obs"], sid))
    out, used = {}, set()
    for _, bid, o, sid in sorted(pairs):
        if bid not in out and (o, sid) not in used:
            out[bid] = sid
            used.add((o, sid))
    return out


def ambiguous_bearings(bearings, fixes, gate=3.0):
    """Ids of the bearings within `gate` of two or more fixes: their peak may be either source (or both,
    merged), so they say nothing about either position."""
    out = set()
    for b in bearings:
        hits = 0
        for f in fixes.values():
            n, e = ned(b["pos"], f["pos"])
            hits += abs(((math.degrees(math.atan2(e, n)) - b["bearing"] + 180) % 360) - 180) / max(b["sigma"], 2.0) < gate
        if hits > 1:
            out.add(b["id"])
    return out


def bearing_crossing(pos, bearings):
    """Weighted least-squares crossing of these bearings, started at pos; None if they do not cross."""
    x = np.zeros(2)
    for _ in range(10):
        rows, res, w = [], [], []
        for b in bearings:
            n, e = ned(b["pos"], latlon(pos, x[0], x[1]))
            r2 = n * n + e * e
            rows.append([-e / r2, n / r2])
            res.append(math.radians(((math.degrees(math.atan2(e, n)) - b["bearing"] + 180) % 360) - 180))
            w.append(1 / math.radians(b["sigma"]) ** 2)
        a, rv, wv = np.array(rows), np.array(res), np.array(w)
        hess = (a * wv[:, None]).T @ a
        if len(rows) < 2 or np.linalg.cond(hess) > 1e12:
            return None
        dx = np.linalg.solve(hess, -(a * wv[:, None]).T @ rv)
        x = x + dx
        if np.hypot(*dx) < 0.5:
            break
    return latlon(pos, x[0], x[1])


def ellipse_distance(centre, ell, p):
    """Distance of p from centre in units of the ellipse (semi-major, semi-minor, major-axis azimuth)."""
    a, b, ori = ell
    n, e = ned(centre, p)
    th = math.radians(ori)
    return math.hypot((n * math.cos(th) + e * math.sin(th)) / max(a, 1.0),
                      (-n * math.sin(th) + e * math.cos(th)) / max(b, 1.0))


class Gcs:
    """Our MAVLink output: rate-limited live power, messages, and the bearings and sources our QGC
    build draws (DEBUG_FLOAT_ARRAY "RF_BRG" with a bearing id and the source it points at, "RF_FIX" per
    source id, sigma < 0 removing it). Those are re-sent every RESEND_S in case one is lost. Source ids stay
    stable between updates (matched by position) so their colours do not jump."""

    def __init__(self, m, ellipse_scale=ELLIPSE_SCALE):
        self.m, self.bearings, self.fixes, self.removed = m, [], {}, set()
        self.ellipse_scale = ellipse_scale
        self.next_id = 1
        self.truth = []                           # (lat, lon, EIRP dBm) of the simulated sources
        self.last_live = self.last_resend = self.last_hb = 0.0

    def text(self, s, sev=mavutil.mavlink.MAV_SEVERITY_INFO):
        print(time.strftime("%H:%M:%S"), s, flush=True)
        self.m.mav.statustext_send(sev, s[:50].encode())

    def live(self, dbm, t_ms):
        # every sample (SAMPLE_S of sim time): the autopilot's RFSEARCH sweeps on it. Stamped with the
        # autopilot's boot time: mission.py takes sim time from any time_boot_ms it sees
        self.m.mav.named_value_float_send(t_ms, b"RF_dBm", dbm)

    def _array(self, name, array_id, values):
        self.m.mav.debug_float_array_send(int(time.time() * 1e6), name, array_id,
                                          [float(v) for v in values] + [0.0] * (58 - len(values)))

    def bearing(self, b):
        b["id"], b["source"] = len(self.bearings) + 1, 0
        self.bearings.append(b)
        self._send_bearing(b)

    def _send_bearing(self, b):
        self._array(b"RF_BRG", 0, [b["pos"][0], b["pos"][1], b["bearing"], b["dbm"], b["sigma"], b["obs"],
                                   b["id"], b["source"], b.get("wide", 0), b.get("width", 0.0)])

    def _send_fix(self, sid):
        if sid in self.removed:
            self._array(b"RF_FIX", sid, [0.0, 0.0, -1.0, 0.0])
        else:
            f = self.fixes[sid]
            major, minor, orient = f.get("ellipse_m_deg", (f["sigma_m"], f["sigma_m"], 0.0))
            self._array(b"RF_FIX", sid, [f["pos"][0], f["pos"][1], major, len(f["bearings"]), minor, orient])

    def set_sources(self, fixes):
        """New source estimates: keep the id of the nearest previous source within 2 km, remove the
        previous ones that are gone, re-assign every bearing and send what changed."""
        new, free = {}, dict(self.fixes)
        for f in fixes:
            near = min(free, key=lambda i: math.hypot(*ned(free[i]["pos"], f["pos"])), default=None)
            if near is not None and math.hypot(*ned(free[near]["pos"], f["pos"])) < 2000.0:
                new[near] = f
                del free[near]
            else:
                new[self.next_id] = f
                self.next_id += 1
        self.removed |= set(free)
        self.removed -= set(new)
        old = self.fixes
        self.fixes = new
        prev = {b["id"]: b["source"] for b in self.bearings} if ESTIMATOR_V2 else None
        assigned = assign_bearings(self.bearings, new, prev=prev)
        amb = ambiguous_bearings(self.bearings, new) if ESTIMATOR_V2 else set()
        by_id = {b["id"]: b for b in self.bearings}
        for sid, f in new.items():
            # the label counts the bearings drawn in this source's colour, not the localisation's own
            # count (n), which can include a bearing the refined position no longer supports
            f["id"], f["bearings"] = sid, sorted(bid for bid, s in assigned.items() if s == sid)
            mine = [by_id[i] for i in f["bearings"]]
            clear = [b for b in mine if b["id"] not in amb]
            use = clear if len(clear) >= 2 else mine
            ell = bearing_ellipse(f["pos"], use, self.ellipse_scale)
            if ell is not None and ESTIMATOR_V2:
                # the published position comes from the fit to all readings; where it disagrees with its own
                # bearings' crossing by more than 2 sigma, the ellipse is widened to cover that crossing
                cross = bearing_crossing(f["pos"], use)
                m = ellipse_distance(f["pos"], ell, cross) if cross is not None else 0.0
                if m > 2.0:
                    ell = (ell[0] * m / 2.0, ell[1] * m / 2.0, ell[2])
            if ell is not None:
                f["ellipse_m_deg"] = ell
                f["sigma_m"] = ell[0]
            o = old.get(sid)
            # only once the source has MOVED_WARN_MIN_BRG bearings: before that the first fixes move by km anyway
            if ESTIMATOR_V2 and o is not None and "ellipse_m_deg" in o and len(f["bearings"]) >= MOVED_WARN_MIN_BRG and \
                    ellipse_distance(o["pos"], o["ellipse_m_deg"], f["pos"]) > 2.0:
                self.text(f"RF: S{sid} moved {math.hypot(*ned(o['pos'], f['pos'])):.0f} m, outside its ellipse",
                          mavutil.mavlink.MAV_SEVERITY_WARNING)
        for sid in list(new) + list(free):
            self._send_fix(sid)
        for b in self.bearings:
            src = assigned.get(b["id"], 0)
            if src != b["source"]:
                b["source"] = src
                self._send_bearing(b)
        return new

    def tick(self):
        now = time.time()
        if now - self.last_hb >= 1.0:
            self.last_hb = now
            self.m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                                      mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
        if now - self.last_resend >= RESEND_S:
            self.last_resend = now
            for b in self.bearings:
                self._send_bearing(b)
            for sid in list(self.fixes) + list(self.removed):
                self._send_fix(sid)
            # simulation only: the hidden true positions, so the fixes can be checked on the map
            for i, src in enumerate(self.truth, start=1):
                self._array(b"RF_TRU", i, [src[0], src[1], src[2]])


def solve_single(bearings):
    """Two bearings: crossing, refined with the power ratio (the single-source demo). Returns the fix
    list (empty if the bearings do not cross ahead) and the details for the result file."""
    by_obs = {b["obs"]: b for b in bearings}
    if len(by_obs) < 2:
        return [], dict(note="need two detections")
    b1, b2 = (dict(by_obs[i], peak_dbm=by_obs[i]["dbm"]) for i in sorted(by_obs)[:2])
    x = cross(b1["pos"], b1["bearing"], b2["pos"], b2["bearing"])
    if x is None or x[1] < 0 or x[2] < 0:
        return [], dict(note="bearings do not cross ahead")
    est, t1, t2 = x
    gam = math.radians(abs(((b1["bearing"] - b2["bearing"] + 180) % 360) - 180))
    sig = math.hypot(t1 * math.radians(b1["sigma"]), t2 * math.radians(b2["sigma"])) / max(math.sin(gam), 0.1)
    joint, jsig, ratio = refine(b1, b2, est)
    return [dict(pos=joint, sigma_m=jsig, n=2)], dict(bearing_fix=est, bearing_sigma_m=sig, ranges_m=(t1, t2),
                                                      cross_deg=math.degrees(gam), power_ratio_d1_d2=ratio)


def solve_multi(bearings, samples, centre, half_size=9000.0, priors=()):
    """Several bearings from several points: candidates, model check against the raw readings
    (already thinned: loiter readings and straight-leg readings), fixes. Runs in a worker thread on
    copies."""
    cands = locate(bearings, centre, half_size, step=max(50.0, 2 * half_size / 360))
    fixes, weak = select_sources(samples, cands, priors=priors if ESTIMATOR_V2 else ())
    return fixes, dict(unconfirmed=weak, candidates=cands)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--instance", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--scenario", choices=["auto", *SCENARIOS], default="auto",
                    help="hidden sources; auto: multi when the plan has more than two half-loiters or none "
                         "(RFSEARCH sweeps)")
    ap.add_argument("--hide-truth", action="store_true",
                    help="do not send the true source positions (DEBUG_FLOAT_ARRAY RF_TRU) for the map")
    ap.add_argument("--linger", type=float, default=1800.0,
                    help="wall seconds to keep re-sending the result after it is done")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    items = json.loads(args.plan.read_text())["mission"]["items"]
    obs = {it["doJumpId"]: dict(centre=(it["params"][4], it["params"][5]), radius=abs(it["params"][2]))
           for it in items if it["command"] == LOITER_TURNS and 0 < it["params"][0] < 1}
    order = sorted(obs)
    # no half-loiters: observations are the autopilot's RFSEARCH sweeps, numbered as they come, and
    # the result is final once the mission reaches its landing sequence
    sweeps = not order
    if len(order) == 1:
        sys.exit(f"{args.plan}: need two half-loiters (LOITER_TURNS < 1) or none, found 1")
    land_seq = min((it["doJumpId"] for it in items if it["command"] in (189, 21)), default=None)
    scenario = args.scenario if args.scenario != "auto" else ("multi" if len(order) != 2 else "single")
    sources = SCENARIOS[scenario]
    ring_centre = None if sweeps else (sum(o["centre"][0] for o in obs.values()) / len(obs),
                                       sum(o["centre"][1] for o in obs.values()) / len(obs))

    m = None
    for _ in range(120):                          # SITL may still be starting
        try:
            m = mavutil.mavlink_connection(f"tcp:127.0.0.1:{5763 + 10 * args.instance}",
                                           source_system=1, source_component=191, autoreconnect=True)
            break
        except OSError:
            time.sleep(1)
    if m is None or m.wait_heartbeat(timeout=60) is None:
        sys.exit("no heartbeat from the autopilot on SERIAL2")
    m.mav.request_data_stream_send(m.target_system, m.target_component,
                                   mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
    gcs = Gcs(m, ELLIPSE_SCALE if scenario == "multi" else 1.0)
    if not args.hide_truth:
        gcs.truth = sources
    gcs.text("RF: companion up, sweeps in RFSEARCH" if sweeps else f"RF: companion up, {len(order)} observation points")

    att = pos = None
    seq, last_t, done = 0, -1.0, []
    swp, landing = 0, False                       # RFSEARCH: current sweep number (0: none), search over
    was_armed = False
    rec = {k: [] for k in order}
    legs = []                                     # readings outside the loiters
    fh = open(args.out / "rf_samples.csv", "w", newline="", buffering=1)
    w = csv.writer(fh)
    # yaw: the antenna's azimuth (boresight, from attitude and TILT_DEG); bn, be, bd: its unit vector
    w.writerow(["t", "seq", "lat", "lon", "alt", "roll", "pitch", "yaw", "dbm", "bn", "be", "bd"])
    worker = ThreadPoolExecutor(max_workers=1)
    job, rerun, result_t = None, False, None      # job: (observations covered, future, final)

    def end_observation(k):
        i = order.index(k) + 1
        samples = rec[k]
        nvalid = sum(s["dbm"] >= VALID_DBM for s in samples)
        obs[k].update(n=len(samples), n_valid=nvalid)
        if nvalid < MIN_VALID:
            gcs.text(f"RF: observation {i}: no detection above {VALID_DBM:.0f} dBm",
                     mavutil.mavlink.MAV_SEVERITY_WARNING)
            return
        # same fit and calibrated sigma for both scenarios; one source: keep the strongest peak
        peaks = [(b, a, math.hypot(PEAK_SIGMA_SCALE * sg, PEAK_SIGMA_FLOOR_DEG)) for b, a, sg in fit_peaks(samples)]
        if not peaks:
            # enough readings over the threshold but none stands out as a peak (e.g. the source on the beam's edge)
            gcs.text(f"RF: observation {i}: no peak in {nvalid} valid readings", mavutil.mavlink.MAV_SEVERITY_WARNING)
            return
        if scenario == "single":
            peaks = peaks[:1]
        for b, a, sd in peaks:
            # a fitted peak much wider than the beam (the other peaks modelled): several sources in similar
            # directions that the fit could not separate
            width = peak_width(samples, b, [(b2, a2) for b2, a2, _ in peaks if b2 != b])
            wide = WIDE_FLAG and width is not None and width > BEAM_DEG + WIDE_MARGIN_DEG
            if wide:
                sd *= 2
                gcs.text(f"RF: obs {i}: {b:.0f} deg is {width:.0f} deg wide: several sources?",
                         mavutil.mavlink.MAV_SEVERITY_WARNING)
            gcs.bearing(dict(obs=i, pos=peak_origin(samples, b), bearing=b, sigma=sd, dbm=a, wide=int(wide),
                             width=width or 0.0, alt=sum(s["alt"] for s in samples) / len(samples)))
        obs[k]["peaks"] = [(round(b, 2), round(a, 1)) for b, a, _ in peaks]
        if scenario == "single":
            b, a, sd = peaks[0]
            gcs.text(f"RF: bearing {i} = {b:.1f} +-{sd:.1f}, {a:.0f} dBm, {nvalid} valid",
                     mavutil.mavlink.MAV_SEVERITY_NOTICE)
        else:
            gcs.text(f"RF: obs {i}: " + (" / ".join(f"{b:.0f}" for b, _, _ in peaks) or "no peak") + " deg",
                     mavutil.mavlink.MAV_SEVERITY_NOTICE)

    def submit():
        snapshot_b = [dict(b) for b in gcs.bearings]
        snapshot_s = [s for k in done for s in rec[k]][::3] + legs[::LEG_STEP]
        centre, half = ring_centre, 9000.0
        if sweeps:
            # the grid covers the sweep points with margin: the sources lie among them
            pts = [b["pos"] for b in snapshot_b]
            centre = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            half = min(max(9000.0, max(math.hypot(*ned(centre, p)) for p in pts) + 3000.0), 20000.0)
        final = len(done) == len(order) and (not sweeps or landing)
        priors = [dict(pos=f["pos"], sigma_m=f["sigma_m"]) for f in gcs.fixes.values()]
        return len(done), worker.submit(solve_multi, snapshot_b, snapshot_s, centre, half, priors), final

    def publish(fixes, details, final):
        ids = gcs.set_sources(fixes)
        if not final:
            gcs.text(f"RF: {len(done)} obs: " + (", ".join(f"S{i} +-{f['sigma_m']:.0f}" for i, f in sorted(ids.items()))
                                               or "no source yet"), mavutil.mavlink.MAV_SEVERITY_NOTICE)
            return None
        for f in details.get("unconfirmed", []):
            gcs.text(f"RF: weak, unconfirmed {f['pos'][0]:.4f} {f['pos'][1]:.4f} {f['eirp_dbm']:.0f}dBm")
        errs = []
        for sid, f in sorted(ids.items()):
            ax = f.get("ellipse_m_deg", (f["sigma_m"], f["sigma_m"], 0))
            gcs.text(f"RF: S{sid} {f['pos'][0]:.5f} {f['pos'][1]:.5f} {ax[0]:.0f}x{ax[1]:.0f} m",
                     mavutil.mavlink.MAV_SEVERITY_NOTICE)
            d = [math.hypot(*ned(f["pos"], s[:2])) for s in sources]
            f["truth_index"], f["error_m"] = int(np.argmin(d)) + 1, float(min(d))
            errs.append(f"S{sid} {f['error_m']:.0f}")
        found = {f["truth_index"] for f in ids.values() if f["error_m"] < 500}
        gcs.text(f"RF truth: {', '.join(errs) or 'no fix'} m; missed {len(sources) - len(found)}")
        res = dict(details, scenario=scenario, truth=sources, fixes=[ids[i] for i in sorted(ids)],
                   bearings=gcs.bearings, observations={str(order.index(k) + 1): obs[k] for k in order})
        (args.out / "rf_result.json").write_text(json.dumps(res, indent=2, default=float) + "\n")
        return time.time()

    while True:
        gcs.tick()
        if result_t and time.time() - result_t > args.linger:
            break
        if job is not None and job[1].done():
            covered, fut, final = job
            job = None
            try:
                fixes, details = fut.result()
            except Exception as e:                # a failed fit must not stop the live reading
                print(f"solve over {covered} obs failed: {e!r}", flush=True)
                gcs.text(f"RF: solve failed ({type(e).__name__}), fixes kept", mavutil.mavlink.MAV_SEVERITY_WARNING)
                if final:
                    (args.out / "rf_result.json").write_text(json.dumps(dict(error=repr(e))) + "\n")
                    result_t = time.time()
                elif rerun:
                    rerun = False
                    job = submit()
                continue
            t_done = publish(fixes, details, final)
            if final:
                result_t = t_done
            elif rerun:
                rerun = False
                job = submit()
        msg = m.recv_match(type=["ATTITUDE", "GLOBAL_POSITION_INT", "MISSION_CURRENT", "NAMED_VALUE_FLOAT", "HEARTBEAT"],
                           blocking=True, timeout=0.5)
        if msg is None:
            continue
        t = msg.get_type()
        if t == "NAMED_VALUE_FLOAT":
            if not sweeps or msg.name != "RFS_SWP" or msg.get_srcComponent() != 1:
                continue
            if msg.value > 0 and not swp:
                k = len(order) + 1
                order.append(k)
                obs[k], rec[k], swp = dict(), [], k
                gcs.text(f"RF: sweep {k}")
            elif msg.value == 0 and swp:
                k, swp = swp, 0
                if rec[k]:
                    obs[k].update(centre=(sum(s["lat"] for s in rec[k]) / len(rec[k]),
                                          sum(s["lon"] for s in rec[k]) / len(rec[k])))
                done.append(k)
                end_observation(k)
                if len({b["obs"] for b in gcs.bearings}) >= 3:
                    if job is None:
                        job = submit()
                    else:
                        rerun = True
            continue
        # RFSEARCH: the search is over once the mission reaches its landing sequence, or the aircraft is
        # sent home (RTL, AUTOLAND) or disarms after flying: then the final solve
        end_why = None
        if sweeps and t == "MISSION_CURRENT" and land_seq is not None and msg.seq >= land_seq:
            end_why = "landing"
        elif t == "HEARTBEAT":
            if sweeps and msg.get_srcComponent() == 1:
                is_armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                if is_armed and msg.custom_mode in (11, 26):
                    end_why = "RTL" if msg.custom_mode == 11 else "AUTOLAND"
                elif was_armed and not is_armed and done:    # not a disarm on the ground before flying
                    end_why = "disarmed"
                was_armed = was_armed or is_armed
            if end_why is None:
                continue
        if end_why is not None:
            if not landing and result_t is None:
                landing = True
                if len({b["obs"] for b in gcs.bearings}) < 3:
                    gcs.text(f"RF: {end_why}, bearings from {len({b['obs'] for b in gcs.bearings})} sweeps: no fix",
                             mavutil.mavlink.MAV_SEVERITY_WARNING)
                    result_t = publish([], {}, True)
                    continue
                gcs.text(f"RF: {end_why}, final solve over {len(done)} sweeps")
                if job is None:
                    job = submit()
                else:
                    rerun = True
            continue
        if t == "MISSION_CURRENT" and sweeps:
            continue
        if t == "MISSION_CURRENT":
            if msg.seq != seq:
                if seq in obs and seq not in done and len(rec[seq]) > 20:
                    done.append(seq)
                    end_observation(seq)
                    if scenario == "single" and len(done) == len(order):
                        fixes, details = solve_single(gcs.bearings)
                        if not fixes:
                            gcs.text(f"RF: no fix: {details['note']}", mavutil.mavlink.MAV_SEVERITY_WARNING)
                        else:
                            d = details
                            gcs.text(f"RF: bearings cross +-{d['bearing_sigma_m']:.0f} m, {d['cross_deg']:.0f} deg",
                                     mavutil.mavlink.MAV_SEVERITY_NOTICE)
                            gcs.text(f"RF: power d1/d2 {d['power_ratio_d1_d2']:.2f}, bearings "
                                     f"{d['ranges_m'][0] / d['ranges_m'][1]:.2f}", mavutil.mavlink.MAV_SEVERITY_NOTICE)
                        result_t = publish(fixes, details, True)
                    elif scenario == "multi" and len(done) >= 3:
                        if job is None:
                            job = submit()
                        else:
                            rerun = True
                seq = msg.seq
                if seq in obs and seq not in done:
                    gcs.text(f"RF: observation {order.index(seq) + 1}, half-loiter sweep")
            continue
        if t == "GLOBAL_POSITION_INT":
            pos = msg
            continue
        att = msg
        if pos is None:
            continue
        ts = att.time_boot_ms / 1000.0
        if ts - last_t < SAMPLE_S:
            continue
        last_t = ts
        here = (pos.lat / 1e7, pos.lon / 1e7)
        alt = pos.relative_alt / 1000.0
        dbm = received_dbm_multi(here, alt, att.roll, att.pitch, att.yaw, rng, sources)
        gcs.live(dbm, att.time_boot_ms)
        # the bearing fits work in the antenna's azimuth, which a tilted helix swings away from the heading in a bank
        bn, be, bd = boresight(att.roll, att.pitch, att.yaw)
        yaw = math.degrees(math.atan2(be, bn)) % 360
        w.writerow([f"{ts:.2f}", seq, f"{here[0]:.7f}", f"{here[1]:.7f}", f"{alt:.1f}",
                    f"{math.degrees(att.roll):.1f}", f"{math.degrees(att.pitch):.1f}", f"{yaw:.1f}", f"{dbm:.2f}",
                    f"{bn:.5f}", f"{be:.5f}", f"{bd:.5f}"])
        sample = dict(lat=here[0], lon=here[1], alt=alt, yaw=yaw, dbm=dbm, bn=bn, be=be, bd=bd)
        if swp:
            rec[swp].append(sample)
        elif not sweeps and seq in obs and seq not in done and math.hypot(*ned(obs[seq]["centre"], here)) < obs[seq]["radius"] + 150:
            rec[seq].append(sample)
        elif alt >= LEG_MIN_ALT:
            legs.append(sample)
    worker.shutdown(wait=False)
    fh.close()


if __name__ == "__main__":
    main()
