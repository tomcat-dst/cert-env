# cert-env — ArduPilot SITL + QGC + MAVSDK

Host: Ubuntu 24.04.5 (noble), x86_64, gcc 13.3, cmake 3.28. Built 2026-11-19.

| Component | Version | Location | Status |
|---|---|---|---|
| ArduPilot SITL | `Plane-4.7.3` + branch `cert-rfsearch` ([fork](https://github.com/tomcat-dst/ardupilot/tree/cert-rfsearch)) | `src/ardupilot/build/sitl/bin/arduplane` | Built, verified |
| MAVSDK (C++) | `v4.2.1` | `install/mavsdk` | Built, installed, verified |
| QGroundControl | `v5.1.5` (Qt 6.11.1 via aqt in `Qt/`) + branch `rf-scan-overlay` ([fork](https://github.com/tomcat-dst/qgroundcontrol/tree/rf-scan-overlay)) | `src/qgroundcontrol/build/Release/QGroundControl` | Built, verified |

## Quick start

Run `source ~/cert-env/env.sh` in each terminal first.

The Believer with RFSEARCH and two hidden signal sources, flown from QGC:

```bash
python compare/mission.py --plan sim/missions/tsuniv_rf_two.plan --params sim/params/believer_mission_long.parm --rf --rf-scenario two --rc-fail-km 0 --wait-operator 7200
```
```bash
$QGC_BIN
```

QGC connects on UDP 14550. In QGC: Plan → Open `sim/missions/tsuniv_rf_two.plan` → Upload; Fly → Arm, switch to RFSearch, start the mission. The script releases the catapult once it sees the aircraft armed in AUTO or RFSEARCH. More in [Signal sources](#signal-sources-rf-search-in-sitl) below.

## What was verified (and how)

- **MAVSDK:** `smoke/mavsdk` linked against `install/mavsdk` and connected to SITL. It discovered the autopilot (sysid 1) and read telemetry.
  Position read NaN 3 s after boot. That's likely because the EKF hadn't aligned yet; I didn't check further.
- **QGC:** `--simple-boot-test` exited 0. Our build flew the RFSEARCH missions of 2026-11-23..25 with `arduplane` SITL over UDP 14550: plan and geofence upload, arming, mode change, the bearing map and the `RFS_` parameter descriptions.
  QGC ignored SIGINT/SIGTERM under `QT_QPA_PLATFORM=offscreen` and needed SIGKILL. A normal desktop session shouldn't be affected (not tested).

## Changes made to the system / environment

- `sudo ./install-deps.sh` (run by you): 78 packages requested, all confirmed installed (358 incl. dependencies).
  apt also upgraded 12 existing packages as a side effect: Mesa `25.2.8-…4 → …5` and sqlite3 `…2.8 → …2.9`.
- `venv/lib/python3.12/site-packages/wx` is a symlink to the system `python3-wxgtk4.0` package, so MAVProxy's map/console work. Only `wx` is linked; system-site-packages stays **off**.
  (An earlier attempt turned system-site-packages on. That let Ubuntu's matplotlib 3.6 `mpl_toolkits` shadow the venv's 3.11 copy, causing MAVProxy's "Unable to import Axes3D" warning. Reverted; verified Axes3D imports cleanly and no system `dist-packages` remain on the venv path.)
- `~/qgc` (your own QGC fork) was not touched. QGC test runs used `smoke/qgc-home` as HOME.

## Files

- `install-deps.sh`: apt list (already run).
- `env.sh`: source for PATH and libraries. Safe to source from scripts that use `set -u`.
- `smoke/`: test programs. `logs/`: build and test logs.

## Comparing fixed-wing models (`compare/compare_planes.py`)

Flies several fixed-wing physics models through one identical, scripted profile and tabulates the results:
TAKEOFF to 120 m → LOITER (20 s settle + 60 s scored) → power-off glide in LOITER with `THR_MAX=0` (first 5 s not scored).

```bash
source ~/cert-env/env.sh && python compare/compare_planes.py                          # all models
source ~/cert-env/env.sh && python compare/compare_planes.py --models plane,high-ar   # a subset
source ~/cert-env/env.sh && python compare/compare_planes.py --param AIRSPEED_CRUISE=15  # force a param on all
```

- **Timing:** about 40 s wall-clock per model at the default `--speedup 5`. Durations are measured in simulated time, so the speedup doesn't change results.
- **Output:** `compare/results/<timestamp>/` holds `summary.md` / `summary.csv`, `timeseries.png` and `loiter_tracks.png`. Each model's subfolder has `samples.csv`, `statustext.txt`, the SITL log and the onboard `logs/*.BIN` (open with `MAVExplorer.py`).
- **Parameters:** each model starts with its frame's stock defaults, exactly as `sim_vehicle.py` loads them. Key parameters are listed per model, and ones that differ are flagged. Use `--param` for a controlled, same-settings comparison.
- **Adding a model:** add an entry to `MODELS` at the top of the script.
  - SITL aircraft file: `model_file=<path to JSON>`, as in `compare/models/plane_high_ar.json`.
  - SITL can't open absolute paths: it strips the leading `/` and resolves them inside its run directory. So the harness copies `model_file` into each run directory. The same applies if you pass your own JSON to `sim_vehicle.py`: put it in the directory you launch from.

Things found while building it (run `20261121-143813`):
- **`skywalker_2013.json` is not a different aircraft.** All 38 coefficients and `CGOffset` are identical to SITL's built-in `plane` defaults (`SIM_Plane.h` says they come from the same file). It's kept as a control: `plane` vs `skywalker` differ by ≤0.1 s / ≤0.1 m/s, which is the harness's run-to-run noise. Smaller differences than that mean nothing.
- **`high-ar` is an illustrative variant** (span 3 m, area 0.6 m², parasitic drag halved; nothing else changed). Compared with `plane`:
  - loiter throttle 32% vs 48%
  - glide ratio 3.6 vs 3.1
  - max climb 13.2 vs 10.7 m/s
  - Its loiter hadn't fully converged after the 20 s settle (track still spiralling), so its 107.8 m loiter radius is an average.
- **SITL's built-in planes fly uncoordinated turns:** the measured loiter radius (~96 m) is well above the radius implied by their bank (~72 m). This is a property of the physics model.

## MFE Believer 1960 in SITL (built-in plane physics)

No Believer model exists for SITL (checked ArduPilot/SITL_Models, local sources and
the web on 2026-11-22), so `compare/models/believer.json` describes it for SITL's built-in
plane model. The file header explains every coefficient and its source; the parameters are in
`sim/params/believer.parm` (20 m/s cruise, 14/28 m/s limits, failsafes that keep AUTO running).

```bash
python compare/compare_planes.py --models believer
```

Interactive (run from a scratch folder, since SITL only opens relative model paths):

```bash
mkdir -p ~/sitl-believer && cd ~/sitl-believer && cp ~/cert-env/compare/models/believer.json .
```
```bash
sim_vehicle.py -v ArduPlane -f plane --model plane:believer.json --add-param-file=$HOME/cert-env/sim/params/believer.parm --map --console
```

Physics: ArduPilot's SITL plane, extended by a local patch
(`patches/ardupilot-sitl-plane-electric-propulsion.patch`, applied to `src/ardupilot`) so the
JSON can set real mass and inertia and an electric drive: X3120 585KV motors, APC 11x7E
propellers (Ct/Cp fitted to APC's data as functions of advance ratio) and the SITL battery model
(state of charge plus 25 mOhm sag). Stock SITL models are unaffected (the stock `plane` repeated
its earlier numbers exactly). Re-apply after updating ArduPilot:

```bash
git -C src/ardupilot apply ../../patches/ardupilot-sitl-plane-electric-propulsion.patch
```

Current design (`believer`, 2026-11-22): 2x20 cm EPO root wing inserts (span 2.36 m), Starlink
Mini on top, 6S5P, 5.9 kg. The 5.9 kg maximum is the design choice; the extended spar has not been
load-tested. The original 5.0 kg design is kept as `believer-5kg`.

Run `compare/results/20261122-162518`, read from the flight logs over the 50 s before the glide:

| | believer (5.9 kg) | believer-5kg |
|---|---|---|
| Loiter at 20 m/s, bank | 52.2% throttle, 31.7 deg | 50.4% throttle, 31.0 deg |
| Propulsion power | 9.9 A at 24.8 V, about 246 W | 8.4 A at 24.8 V, about 209 W |
| Climb / takeoff peak | 9.3 m/s / 31 m/s, 88 A | 9.9 m/s / 33 m/s, 86 A |
| Glide ratio | 8.3 | 8.8 |

SITL's battery feeds propulsion only, so Starlink (25-40 W) and avionics are not in these
figures. Hand estimate for straight flight with them: about 268 W, about 111 min on 6S5P.

Remaining limits:
- **Inertia is estimated** ([0.34, 0.20, 0.55] kg m2), and the stability and control derivatives
  are SITL's generic defaults, so control-loop behaviour is indicative only.
- **Battery voltage uses SITL's LiPo state-of-charge curve**, not a Li-ion (P50B) curve.
- **Motor no-load current (1 A) and the drag polar are assumptions**; see the JSON header.

## Signal sources (RF search in SITL)

SITL has no radio channel, so `compare/rf_companion.py` stands in for the Pi Zero with tinySA. It connects to SITL's
SERIAL2 and, every 0.2 s of simulated time, works out what the analyzer would read through the nose antenna from
hidden sources, then sends it to the autopilot as `NAMED_VALUE_FLOAT RF_dBm`. In RFSEARCH (ArduPlane mode 27) the
autopilot flies a 360° circle when that reading is at or above `RFS_THR_DBM`; the companion turns each circle into
bearings, crosses them and sends the estimates with error ellipses to QGC. `compare/mission.py --rf` starts it.

**The model.** Each source is an omnidirectional transmitter on the ground (home elevation), all on one frequency, so
the analyzer sees their sum. Default power 47 dBm EIRP (50 W). Path loss is free space to 100 m, then 30 dB per decade,
plus 1.5 dB random fading per source and reading and a −110 dBm noise floor. The antenna is a nose helix: 15 dBi,
30° beam, tilted 10° down; its pointing comes from the aircraft's real roll, pitch and heading. In the 25.11 flights the
strongest reading of a circle was about −63 to −80 dBm.

**Ready-made layouts** (`SCENARIOS` in `compare/rf_companion.py`; distances from home, Tsuniv):

| Name | Sources | Made for |
|---|---|---|
| `single` | 1, 13.8 km out on the launch heading | `tsuniv_rf_search.plan` |
| `multi` | 3, 17.8–23.2 km out, 3.9–5.4 km apart | `tsuniv_rf_multi.plan`, `tsuniv_rf_sweep.plan` |
| `multi_b` | 3, 15.5–19.5 km out, 3.9–9.6 km apart | `tsuniv_rf_ellipse.plan` |
| `sw5` | 5, 20–27.5 km south-west, at least 3.6 km apart | `tsuniv_rf_ellipse_sw.plan` |
| `sw4` | `sw5` without its middle source, at least 4.7 km apart | `tsuniv_rf_ellipse_sw.plan` |
| `two` | 2, 16 and 19.5 km north, 5.7 km apart | `tsuniv_rf_two.plan` |

Always pass `--rf-scenario` for an RFSEARCH plan: the default `auto` picks `multi` for any plan without half-loiters.

**Adding your own layout.**

1. Work out the coordinates. North/east offsets from home in km convert like this (it reproduces `two`):

   ```python
   import math
   HOME = (49.825888, 23.689912)          # Tsuniv, runway 10/28
   def at(north_km, east_km):
       return (HOME[0] + north_km / 111.195,
               HOME[1] + east_km / (111.195 * math.cos(math.radians(HOME[0]))))
   print(at(16.0, 2.5), at(19.5, -2.0))
   ```

2. Add an entry to `SCENARIOS`: a list of `(lat, lon, EIRP in dBm)`, for example
   `"mine": [(49.9697795, 23.7247633, 47.0), (50.0012557, 23.6620309, 40.0)]`. A lower EIRP makes a source weaker.
   `--rf-scenario` takes any key of `SCENARIOS`; nothing else needs changing.
3. Make a route that passes the sources from the side, about 4 km off. RFSEARCH circles only on plain waypoint legs,
   not closer than `RFS_MIN_LEG` (500 m) to the next waypoint, not on take-off or landing and not in a battery failsafe.
   Draw it in QGC (plain waypoints, then `DO_LAND_START`, approach waypoints and `NAV_LAND`) and save it in
   `sim/missions/`, or add it to `sim/missions/make_tsuniv_plan.py` and run that with the plan's name as the argument.
   Without arguments the script rewrites every plan it knows; `tsuniv_rf_sweep.plan` and `tsuniv_rf_ellipse_sw.plan`
   are edited in QGC and are not among them.

What worked in the flights so far:
- **At most four sources.** The estimator tries up to `MAX_SOURCES` = 4; allowing five let a false fifth source in.
- **Keep sources about 5 km apart.** `sw5`'s middle source overlapped a neighbour from everywhere on the route and was
  never separated; `sw4` (at least 4.7 km apart) found all four.
- **Sources in line with a leg merge** until the route sees them from the side: in the four-source QGC flight two such
  sources ended 335 and 434 m off, one with a 2.4 km ellipse.

**Flying it.** Headless, about 3–4 min wall time at `--speedup 20`, no QGC:

```bash
python compare/mission.py --plan sim/missions/tsuniv_rf_two.plan --params sim/params/believer_mission_long.parm --rf --rf-scenario two --mode RFSEARCH --upload --speedup 20 --rc-fail-km 0
```

- `--rc-fail-km 5 --rc-fail-s 0`: RC is cut beyond 5 km and comes back only inside 5 km on the way home; the search goes
  on without RC (`FS_SHORT_ACTN 0`, `FS_LONG_ACTN 0`).
- `--rf-seed N`: another draw of the fading. The same seed and the same flight path give the same readings.
- `--instance N`: several runs at once (ports shift by 10 per instance; the results folder gets `-iN`).
- With QGC instead: drop `--mode`, `--upload` and `--speedup`, add `--wait-operator 7200`, and start the mission from
  QGC as in [Quick start](#quick-start).

**Results** go to `compare/results/mission-<time>[-iN]/believer-5kg-avl-at/`:
- `rf_result.json`: the true sources (`truth`), the estimates (`fixes`, each with `error_m` against its true source and
  the 1σ ellipse `ellipse_m_deg`: semi-axes in m and orientation) and every bearing.
- `rf_samples.csv`: every reading with position, attitude and antenna pointing.
- `rf_companion.log`, `sitl.log` and the flight log `logs/00000001.BIN`.

Our QGC build draws the live reading, the bearings, the estimates `S<n>` with their ellipses and, in SITL, the true
positions `T<n>` with the distance to the nearest estimate. `rf_companion.py --hide-truth` leaves the true positions
out; `mission.py` does not pass that option.

Series of flights: `compare/rfsearch/run_batch.sh OUTDIR FIRST_INSTANCE PARM_FILE|- SEED...` flies five fixed layouts per
seed in parallel, and `compare/rfsearch/summarise.py LOG... > out.json` tabulates their errors.
