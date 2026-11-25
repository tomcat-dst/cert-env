#!/usr/bin/env python3
"""
Writes the jammer-search missions for QGroundControl (Plan view -> Open):

  tsuniv_search.plan       short demo, ~25 min: search box 6-8 km out at 250 m
  tsuniv_search_long.plan  near full endurance, ~1 h 30 min: 8-leg grid 16-24 km out at 900 m
  tsuniv_rf_search.plan    RF direction finding: two half-loiters either side of the search area
  tsuniv_rf_multi.plan     RF direction finding, several sources: six half-loiters on a ring, ~1 h 30 min
  tsuniv_rf_sweep.plan     RFSEARCH route (the autopilot sweeps); started as the ring as plain waypoints
                           (RF_SWEEP), reworked in QGC since: not written by this script
  tsuniv_rf_ellipse.plan   RFSEARCH route: an ellipse from home with the search area in its far focus

Both: catapult takeoff -> climb-out -> faster transit (DO_CHANGE_SPEED) -> search legs at constant
height and cruise speed -> LOITER_TURNS around the estimated source -> landing sequence
(DO_LAND_START, approach, NAV_LAND on runway 28).

Plus a geofence: inclusion circle around home (the ceiling, FENCE_ALT_MAX, is a parameter in
sim/params/believer_mission*.parm, not part of the plan). Altitudes are relative to home. Distances
are along the launch heading (runway 10/28, 109 deg), so the search area lies beyond the ~5 km RC
range the RC-loss test relies on.

  sim/missions/make_tsuniv_plan.py            # rewrites every .plan file listed in MISSIONS
  sim/missions/make_tsuniv_plan.py tsuniv_rf_ellipse.plan    # only the ones named (QGC edits elsewhere stay)
"""
import json
import math
import sys
from pathlib import Path

HOME = (49.825888, 23.689912, 290.0)    # Tsuniv, as compare_planes.HOME
HDG = 109.0                              # launch heading, deg

R = 6371000.0
WAYPOINT, LOITER_TURNS, LAND, TAKEOFF, CHANGE_SPEED, DO_LAND_START = 16, 18, 21, 22, 178, 189


def offset(along, across=0.0, base=HOME[:2], hdg=HDG):
    """Point `along` m on heading `hdg` and `across` m to its left (negative = right) of `base`."""
    n = along * math.cos(math.radians(hdg)) - across * math.sin(math.radians(hdg))
    e = along * math.sin(math.radians(hdg)) + across * math.cos(math.radians(hdg))
    lat = base[0] + math.degrees(n / R)
    lon = base[1] + math.degrees(e / (R * math.cos(math.radians(base[0]))))
    return round(lat, 7), round(lon, 7)


def nav(seq, cmd, latlon, alt, p1=0, p2=0, p3=0, p4=None):
    return {"AMSLAltAboveTerrain": None, "Altitude": alt, "AltitudeMode": 1, "autoContinue": True,
            "command": cmd, "doJumpId": seq, "frame": 3,
            "params": [p1, p2, p3, p4, latlon[0], latlon[1], alt], "type": "SimpleItem"}


def do(seq, cmd, p1=0, p2=0, p3=0, p4=0):
    return {"autoContinue": True, "command": cmd, "doJumpId": seq, "frame": 2,
            "params": [p1, p2, p3, p4, 0, 0, 0], "type": "SimpleItem"}


def speed(v):
    return ("do", CHANGE_SPEED, None, None, dict(p1=0, p2=v, p3=-1))


def loiter(along, across, alt, turns, radius):
    # p4 (exit xtrack) must be a number: QGC loads null here as NaN and then uploads only the
    # items before it
    return ("nav", LOITER_TURNS, offset(along, across), alt, dict(p1=turns, p3=radius, p4=0))


def grid(centre, legs, leg_len, gap, alt):
    """Lawnmower legs across the heading, centred `centre` m out, flown away from home."""
    out = []
    for k in range(legs):
        along = centre + (k - (legs - 1) / 2) * gap
        a, b = (-leg_len / 2, leg_len / 2) if k % 2 == 0 else (leg_len / 2, -leg_len / 2)
        out += [("nav", WAYPOINT, offset(along, a), alt, {}), ("nav", WAYPOINT, offset(along, b), alt, {})]
    return out


# landing on runway 28 (heading 289), straight in from the search area: no wind, so no need to land
# into it. DO_LAND_START also lets an RTL (fence, failsafe) join here with RTL_AUTOLAND 1.
LANDING = [
    ("land_start", DO_LAND_START, offset(4000), 0, {}),
    ("nav", WAYPOINT, offset(4000), 150, {}),                       # approach entry, on the centreline
    ("nav", WAYPOINT, offset(1600), 60, {}),                        # final: 60 m over 1.5 km, ~2.3 deg
    ("nav", LAND, offset(100), 0, dict(p4=0)),                      # touchdown 100 m east of midpoint
]

SHORT = [
    ("nav", TAKEOFF, offset(0), 120, dict(p1=12)),                 # pitch 12 deg, catapult launch
    ("nav", WAYPOINT, offset(1500), 200, {}),                       # climb-out
    speed(22),                                                      # faster transit
    ("nav", WAYPOINT, offset(5000), 350, {}),                       # transit, edge of RC range
    speed(19),                                                      # back to cruise for clean data
    *grid(7000, 3, 2000, 700, 250),                                 # 3 legs of 2 km, 700 m apart
    loiter(7200, 300, 180, 2, 300),
    *LANDING,
]

# Sized from the SITL endurance of the base loadout at 900 m (2 h 02 min to reserve, 19 m/s, calm):
# ~98 km of track, ~1 h 27 min, leaving ~30 min.
LONG = [
    ("nav", TAKEOFF, offset(0), 120, dict(p1=12)),
    ("nav", WAYPOINT, offset(2000), 400, {}),                       # climb-out
    speed(22),
    ("nav", WAYPOINT, offset(8000), 900, {}),                       # climb to working height
    ("nav", WAYPOINT, offset(15000), 900, {}),                      # transit
    speed(19),
    *grid(20000, 8, 5000, 1000, 900),                               # 8 legs of 5 km, 1 km apart
    loiter(20500, 800, 700, 3, 500),                                # around the estimate, lower
    ("nav", WAYPOINT, offset(10000), 500, {}),                      # return, descending
    *LANDING,
]

# RF direction-finding demo (compare/rf_companion.py): the source is somewhere around the search area
# centre RF_AREA (the companion holds the hidden true position). Two observation points either side,
# each reached on an approach leg aimed at RF_AREA. ArduPlane joins a loiter at 90 deg to the approach
# heading H, so a half turn (LOITER_TURNS 0.5) sweeps the nose-mounted antenna through H +- 90 deg,
# centred on the search area. After the counted turns ArduPlane keeps circling until it heads for the
# next waypoint (verify_loiter_heading), so an exit waypoint sits 10 deg past the final heading
# (H +- 90) from the far side of the circle: the loiter ends after ~0.53 turns.
RF_AREA = (13000.0, 0.0)                 # (along, across) m
RF_OBS = [((5500.0, 4500.0), -1),        # (point, direction: 1 clockwise, -1 counter-clockwise)
          ((5500.0, -6500.0), 1)]
RF_ALT, RF_R, RF_LEAD, RF_EXIT = 350, 400, 2500, 2000   # height, loiter radius, leg lengths (m)


def azimuth(a, b):
    n = math.radians(b[0] - a[0]) * R
    e = math.radians(b[1] - a[1]) * R * math.cos(math.radians(a[0]))
    return math.degrees(math.atan2(e, n)) % 360


def observe(obs, direction, area=RF_AREA, alt=RF_ALT):
    da, dc = area[0] - obs[0], area[1] - obs[1]
    k = RF_LEAD / math.hypot(da, dc)
    lead, centre = offset(obs[0] - da * k, obs[1] - dc * k), offset(*obs)
    h = azimuth(lead, centre)
    far = offset(RF_R, 0.0, base=centre, hdg=h)              # where the half turn ends
    out = offset(RF_EXIT, 0.0, base=far, hdg=h + direction * 100)
    return [("nav", WAYPOINT, lead, alt, {}),
            ("nav", LOITER_TURNS, centre, alt, dict(p1=0.5, p3=direction * RF_R, p4=0)),
            ("nav", WAYPOINT, out, alt, {})]


RF = [
    ("nav", TAKEOFF, offset(0), 120, dict(p1=12)),
    ("nav", WAYPOINT, offset(1500), 250, {}),                      # climb-out
    *observe(*RF_OBS[0]),
    *observe(*RF_OBS[1]),
    *LANDING,
]

# Several sources on one frequency over the long-mission area (compare/rf_companion.py --scenario
# multi): 6 observation points on a 7 km ring around the area centre, visited clockwise (increasing
# angle in the (along, across) frame is clockwise on the map). Each half-loiter is counter-clockwise,
# so it ends heading along the ring towards the next point. Sized in an offline study: 6 points at
# 7 km gave every source support from >= 3 points; 5 points or a 6 km ring missed sources.
RFM_AREA, RFM_RING, RFM_POINTS, RFM_ALT = (20000.0, 0.0), 7000.0, 6, 900
RFM_OBS = [(RFM_AREA[0] + RFM_RING * math.cos(math.radians(180 + i * 360 / RFM_POINTS)),
            RFM_AREA[1] + RFM_RING * math.sin(math.radians(180 + i * 360 / RFM_POINTS))) for i in range(RFM_POINTS)]

RF_MULTI = [
    ("nav", TAKEOFF, offset(0), 120, dict(p1=12)),
    ("nav", WAYPOINT, offset(2000), 400, {}),                      # climb-out
    ("nav", WAYPOINT, offset(8000), RFM_ALT, {}),                  # climb to working height
    *[item for o in RFM_OBS for item in observe(o, -1, RFM_AREA, RFM_ALT)],
    ("nav", WAYPOINT, offset(10000), 500, {}),                     # return, descending
    *LANDING,
]

# The same ring as plain waypoints, for RFSEARCH (ArduPlane mode 27): the autopilot itself weaves the
# antenna through the course +-90 deg every RFS_SPACING (3 km) while the signal is above RFS_THR_DBM,
# not within RFS_MIN_LEG of the next waypoint. The ring is closed so every 7 km side gets ~2 sweeps.
RF_SWEEP = [
    ("nav", TAKEOFF, offset(0), 120, dict(p1=12)),
    ("nav", WAYPOINT, offset(2000), 400, {}),                      # climb-out
    ("nav", WAYPOINT, offset(8000), RFM_ALT, {}),                  # climb to working height
    *[("nav", WAYPOINT, offset(*o), RFM_ALT, {}) for o in RFM_OBS + RFM_OBS[:1]],
    ("nav", WAYPOINT, offset(10000), 500, {}),                     # return, descending
    *LANDING,
]

# An ellipse from home around the search area: home at the near vertex, the area centre RFM_AREA (D km out
# on the launch heading) in the far focus, so one standoff RFE_STANDOFF (area to the far vertex) sets it all:
# a = (D + s) / 2, c = (D - s) / 2, b = sqrt(D s). With s = 5 km: 12.5 x 10.1 km semi-axes, the route 5 km
# beyond the area at the far end and b^2 / a = 8 km abeam it, ~72 km. Flown clockwise (out on the north
# side, back on the south) through RFE_POINTS waypoints, ~6 km apart so each leg has room for a sweep
# (RFS_MIN_LEG from the next waypoint, a third of it from the previous).
RFE_STANDOFF, RFE_POINTS = 5000.0, 12
_D = math.hypot(*RFM_AREA)
RFE_A, RFE_C = (_D + RFE_STANDOFF) / 2, (_D - RFE_STANDOFF) / 2
RFE_B = math.sqrt(RFE_A ** 2 - RFE_C ** 2)


def ellipse_point(k, n=RFE_POINTS):
    # k = 0 is the near vertex (home); positive "across" is right of the heading, so north is negative here
    t = math.pi - 2 * math.pi * k / n
    return RFE_A * (1 + math.cos(t)), -RFE_B * math.sin(t)


RF_ELLIPSE = [
    ("nav", TAKEOFF, offset(0), 120, dict(p1=12)),
    ("nav", WAYPOINT, offset(2000), 400, {}),                       # climb-out
    ("nav", WAYPOINT, offset(*ellipse_point(1)), 700, {}),          # onto the ellipse, still climbing
    *[("nav", WAYPOINT, offset(*ellipse_point(k)), RFM_ALT, {}) for k in range(2, RFE_POINTS - 1)],
    ("nav", WAYPOINT, offset(*ellipse_point(RFE_POINTS - 1)), 700, {}),
    ("nav", WAYPOINT, offset(6000), 400, {}),                       # return, descending
    *LANDING,
]

# The same ellipse in another direction (2026-11-25): area of interest RFW_D out on bearing RFW_BRG (south-west,
# away from the first area), standoff RFW_STANDOFF beyond it: ~74 km of ellipse through RFW_POINTS waypoints
# ~5.4 km apart, ~87 km and ~1 h 15 min at 19 m/s with the climb-out and the return. The standoff was 8 km
# (~106 km) at first, but with the route 10-18 km from the cluster on its near half, four sources 4.7-8.7 km apart
# came out 100-970 m off; 4 km brings the route in. The far vertex is 28 km out, inside the 35 km fence.
# Hidden sources for it: rf_companion.py scenario "sw4".
# NOTE: tsuniv_rf_ellipse_sw.plan was reworked in QGC on 2026-11-25 14:01 (wider loop on the far side, 21 items,
# landing from the west) and saved over the generated file: QGC's file is the source now, do not regenerate it
# (it is left out of MISSIONS below; RF_ELLIPSE_SW stays as the record of the generated route).
RFW_BRG, RFW_D, RFW_STANDOFF, RFW_POINTS = 225.0, 24000.0, 4000.0, 14
RFW_A, RFW_C = (RFW_D + RFW_STANDOFF) / 2, (RFW_D - RFW_STANDOFF) / 2
RFW_B = math.sqrt(RFW_A ** 2 - RFW_C ** 2)


def ellipse_sw(k, n=RFW_POINTS):
    """Waypoint k of the south-west ellipse as (lat, lon): clockwise seen from above, k = 0 at home."""
    t = math.pi - 2 * math.pi * k / n
    return offset(RFW_A * (1 + math.cos(t)), -RFW_B * math.sin(t), hdg=RFW_BRG)


RF_ELLIPSE_SW = [
    ("nav", TAKEOFF, offset(0), 120, dict(p1=12)),
    ("nav", WAYPOINT, offset(2000), 400, {}),                       # climb-out on the runway heading
    ("nav", WAYPOINT, ellipse_sw(1), 700, {}),                      # onto the ellipse, still climbing
    *[("nav", WAYPOINT, ellipse_sw(k), RFM_ALT, {}) for k in range(2, RFW_POINTS - 1)],
    ("nav", WAYPOINT, ellipse_sw(RFW_POINTS - 1), 700, {}),
    ("nav", WAYPOINT, offset(6000), 400, {}),                       # past home to the landing side, descending
    *LANDING,
]

# A short two-source mission (2026-11-25): the same ellipse to the north, area RF2_D out on bearing RF2_BRG,
# standoff RF2_STANDOFF: ~60 km of ellipse through RF2_POINTS waypoints ~5 km apart, ~70 km with the climb-out and
# the return, ~1 h 05 min at 19 m/s. Climb-out on the runway heading leads onto the east side; flown clockwise.
# Hidden sources for it: rf_companion.py scenario "two".
RF2_BRG, RF2_D, RF2_STANDOFF, RF2_POINTS = 0.0, 18000.0, 4000.0, 12
RF2_A, RF2_C = (RF2_D + RF2_STANDOFF) / 2, (RF2_D - RF2_STANDOFF) / 2
RF2_B = math.sqrt(RF2_A ** 2 - RF2_C ** 2)


def ellipse_two(k, n=RF2_POINTS):
    """Waypoint k of the northern ellipse as (lat, lon): clockwise seen from above, k = 0 at home."""
    t = math.pi - 2 * math.pi * k / n
    return offset(RF2_A * (1 + math.cos(t)), -RF2_B * math.sin(t), hdg=RF2_BRG)


RF_TWO = [
    ("nav", TAKEOFF, offset(0), 120, dict(p1=12)),
    ("nav", WAYPOINT, offset(2000), 400, {}),                       # climb-out on the runway heading
    ("nav", WAYPOINT, ellipse_two(1), 700, {}),                     # onto the ellipse, still climbing
    *[("nav", WAYPOINT, ellipse_two(k), RFM_ALT, {}) for k in range(2, RF2_POINTS - 1)],
    ("nav", WAYPOINT, ellipse_two(RF2_POINTS - 1), 700, {}),
    ("nav", WAYPOINT, offset(6000), 400, {}),                       # past home to the landing side, descending
    *LANDING,
]

MISSIONS = {"tsuniv_search.plan": (SHORT, 9000.0), "tsuniv_search_long.plan": (LONG, 35000.0),
            "tsuniv_rf_two.plan": (RF_TWO, 35000.0),
            "tsuniv_rf_search.plan": (RF, 15000.0), "tsuniv_rf_multi.plan": (RF_MULTI, 35000.0),
            "tsuniv_rf_ellipse.plan": (RF_ELLIPSE, 35000.0)}
# tsuniv_rf_sweep.plan started as RF_SWEEP but has since been reworked in QGC (2026-11-24): QGC's file is
# the source now and is not rewritten here


def build(steps, fence_radius):
    items = []
    for i, (kind, cmd, latlon, alt, kw) in enumerate(steps, start=1):
        if kind == "nav":
            items.append(nav(i, cmd, latlon, alt, **kw))
        elif kind == "land_start":     # a DO command with a position (picks the nearest sequence)
            it = do(i, cmd)
            it["frame"] = 3
            it["params"][4:6] = latlon
            items.append(it)
        else:
            items.append(do(i, cmd, **kw))
    return {
        "fileType": "Plan",
        "geoFence": {"circles": [{"circle": {"center": list(HOME[:2]), "radius": fence_radius},
                                  "inclusion": True, "version": 1}],
                     "polygons": [], "version": 2},
        "groundStation": "QGroundControl",
        "mission": {"cruiseSpeed": 19, "firmwareType": 3, "globalPlanAltitudeMode": 1, "hoverSpeed": 5,
                    "items": items, "plannedHomePosition": list(HOME), "vehicleType": 1, "version": 2},
        "rallyPoints": {"points": [], "version": 2},
        "version": 1,
    }


def track_km(items):
    pts = [HOME[:2]] + [tuple(it["params"][4:6]) for it in items
                        if it["frame"] == 3 and it["command"] != DO_LAND_START]
    k = (111195, 111195 * math.cos(math.radians(HOME[0])))
    d = sum(math.hypot((a[0] - b[0]) * k[0], (a[1] - b[1]) * k[1]) for a, b in zip(pts, pts[1:]))
    for it in items:            # loiter turns add their circumference
        if it["command"] == LOITER_TURNS:
            d += it["params"][0] * 2 * math.pi * abs(it["params"][2])
    return d / 1000


only = sys.argv[1:]
unknown = [n for n in only if n not in MISSIONS]
if unknown:
    sys.exit(f"unknown plan(s) {unknown}; known: {list(MISSIONS)}")
for name, (steps, fence) in MISSIONS.items():
    if only and name not in only:
        continue
    plan = build(steps, fence)
    items = plan["mission"]["items"]
    out = Path(__file__).with_name(name)
    out.write_text(json.dumps(plan, indent=4) + "\n")
    k = (111195, 111195 * math.cos(math.radians(HOME[0])))
    far = max(math.hypot((it["params"][4] - HOME[0]) * k[0], (it["params"][5] - HOME[1]) * k[1])
              for it in items if it["frame"] == 3)
    print(f"{out.name}: {len(items)} items, ~{track_km(items):.0f} km of track, farthest point "
          f"{far / 1000:.2f} km, fence radius {fence / 1000:.0f} km")
