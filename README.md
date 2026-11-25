# cert-env — ArduPilot + Gazebo + QGC + MAVSDK

Host: Ubuntu 24.04.5 (noble), x86_64, gcc 13.3, cmake 3.28. Built 2026-11-19.

| Component | Version | Location | Status |
|---|---|---|---|
| ArduPilot SITL | `Copter-4.7.3` tag | `src/ardupilot/build/sitl/bin/{arducopter,arduplane,ardurover}` | Built, verified |
| MAVSDK (C++) | `v4.2.1` | `install/mavsdk` | Built, installed, verified |
| QGroundControl | `v5.1.5` (Qt 6.11.1 via aqt in `Qt/`) | `src/qgroundcontrol/build/Release/QGroundControl` | Built, verified |
| Gazebo Harmonic | gz-sim 8.15.0 (gazebodistro `collection-harmonic.yaml`) | `src/gz-harmonic` → `install/gz` | Built (16/16), **1 local patch**, verified |
| ardupilot_gazebo | `main` | `src/ardupilot_gazebo/build` | Built, verified |

## Quick start

Run `source ~/cert-env/env.sh` in each terminal first.

Copter (Iris quad):

```bash
gz sim -v4 -r iris_runway.sdf                                    # terminal 1 (GUI)
sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --map --console   # terminal 2
$QGC_BIN                                                          # terminal 3 (auto-connects on UDP 14550)
```

Fixed wing (Zephyr flying wing):

```bash
gz sim -v4 -r zephyr_runway.sdf                                  # terminal 1 (GUI)
sim_vehicle.py -v ArduPlane -f gazebo-zephyr --model JSON --map --console  # terminal 2
$QGC_BIN                                                          # terminal 3
```

Then in the MAVProxy prompt: `mode fbwa`, `arm throttle`, `rc 3 1800`, and once it's climbing, `mode circle`.

**Auto takeoff (TAKEOFF mode / AUTO mission `NAV_TAKEOFF`) needs one parameter first:**

```
param set FLIGHT_OPTIONS 4
mode takeoff
arm throttle
```

The stock world spawns the Zephyr standing on its tail (pitch about 88°). ArduPlane's takeoff attitude check refuses to launch above 45° pitch and reports `Bad launch AUTO`. `FLIGHT_OPTIONS` bit 2 (value 4) disables that check (OR it in if you use other bits).
Verified: TAKEOFF climbed to 45 m of 50 (`smoke/run_gz_e2e.sh plane-takeoff`).

`worlds/zephyr_runway_15deg.sdf` spawns it 15° nose-up instead, which does pass the attitude check. **But the aircraft can't take off from it:** with no landing gear it tips onto its nose (settles at pitch −17°, roll −11°), and TAKEOFF mode stayed at 0 m (`smoke/run_gz_e2e.sh plane-takeoff-15`).
A 15° launch would need something holding the airframe at that angle, such as a launch rail or ramp in the world, and probably a launch impulse.

Automated end-to-end checks (headless, no windows, clean up after themselves, about 1–3 min each):

```bash
~/cert-env/smoke/run_gz_e2e.sh copter
```
```bash
~/cert-env/smoke/run_gz_e2e.sh plane
```

## What was verified (and how)

- **SITL:** `arducopter` listened on TCP 5760. pymavlink received a HEARTBEAT with type=2 (quad) and autopilot=3 (ArduPilot).
- **MAVSDK:** `smoke/mavsdk` linked against `install/mavsdk` and connected to SITL. It discovered the autopilot (sysid 1) and read telemetry.
  Position read NaN 3 s after boot. That's likely because the EKF hadn't aligned yet; I didn't check further.
- **QGC:** `--simple-boot-test` exited 0. A live run (offscreen, sandbox HOME) auto-connected to SITL on UDP 14550 and identified it as ArduPilot quad.
  It loaded all parameters via MAVLink FTP in about 1.6 s. Log: `logs/qgc-sitl.log`.
  QGC ignored SIGINT/SIGTERM under `QT_QPA_PLATFORM=offscreen` and needed SIGKILL. A normal desktop session shouldn't be affected (not tested).
- **Gazebo + ArduPilot, closed loop:** `smoke/run_gz_e2e.sh` ran headless gz-server (iris_runway) and ArduCopter SITL with `--model JSON` + `gazebo-iris.parm`.
  The test waited for EKF3/GPS and prearm, armed in GUIDED and took off. It reached **4.56 m** against a 4.5 m threshold → PASS (re-checked after the runner gained plane support). Log: `logs/gz-test-copter.log`.
- **Fixed wing, closed loop:** `smoke/run_gz_e2e.sh plane` runs `zephyr_runway.sdf` + `arduplane` with `gazebo-zephyr.parm` only, the same params `sim_vehicle.py -f gazebo-zephyr` loads.
  The test follows the plugin README procedure over MAVLink: FBWA → arm → throttle 1800 → climb to 40 m → CIRCLE (throttle override released).
  Result: **400° of turn in CIRCLE, altitude held between 38.1 and 40.2 m, average groundspeed 10.0 m/s (min 9.7)** vs the vehicle's `AIRSPEED_MIN` 9.0 → PASS.
  Two runs gave identical numbers (lockstep). Log: `logs/gz-test-plane.log`.
  - **Tuning note:** the margin over `AIRSPEED_MIN` is only about 1 m/s. That's expected for the stock setup, not a fault. `gazebo-zephyr.parm` sets `ARSPD_TYPE 0` (no airspeed sensor), so CIRCLE flies on `TRIM_THROTTLE` (45%) rather than holding `AIRSPEED_CRUISE` (12 m/s).
    If you want more margin, raise `TRIM_THROTTLE` or enable a simulated airspeed sensor. I haven't tested either.
- **Fixed wing, full workflow:** under Xvfb, Gazebo zephyr + `sim_vehicle.py -f gazebo-zephyr --map --console` + QGC ran together.
  MAVProxy loaded console and map and received 1356 params. QGC auto-connected via MAVProxy's UDP 14550 output, identified ArduPilot fixed-wing (type 1) and loaded all params. No errors.
  Logs: `logs/sim_vehicle-plane.log`, `logs/qgc-plane.log`.
- **sim_vehicle.py (documented workflow):** ran under Xvfb against gz-server with `--map --console`. MAVProxy loaded the console and map modules, detected vehicle 1:1 and received 1404 params. No tracebacks.
- **Gazebo GUI:** `gz sim -g` under Xvfb connected to the server, loaded all GUI plugins and rendered via OGRE2 with zero `[Err]` lines.
  This was **software GL on a virtual display**. It hasn't been tried on your real desktop/GPU.
- **Plugins:** every `gz-rendering` engine plugin and every `ardupilot_gazebo` plugin passed an `RTLD_NOW` dlopen, so all symbols resolve.

## Local patch: gz-rendering8 vs Ubuntu's ogre-next (important)

`patches/gz-rendering8-ubuntu-ogre-next-debug-abi.patch` is applied automatically by `build-after-deps.sh`.

- **Symptom without it:** `gz sim` segfaults. `libgz-rendering-ogre2.so` fails to load with `undefined symbol: _ZThn944_N4Ogre7HlmsPbs19_changeRenderSystem…`.
- **Cause (measured):** Ubuntu noble's `libogre-next` 2.3.3 is built with OGRE debug mode, so `Ogre::Hlms` is 864 bytes, not 800.
  The library exports the thunk at offset 1008, while gz-rendering compiled in release mode expects 944.
  A probe compiled against the same headers (`smoke/ogre-abi/probe.cpp`) gives 944 by default and 1008 with `_DEBUG` → exact match.
- **Fix:** `_DEBUG=1` (not `DEBUG`) on the `gz-rendering8-ogre2` and Terra targets only. `DEBUG` would make gz look for `_d`-suffixed OGRE plugins, which Ubuntu doesn't ship.
  This is upstream's own commented-out workaround in those CMakeLists, made unconditional. No other gz package includes OGRE headers.

## Changes made to the system / environment

- `sudo ./install-deps.sh` (run by you): 78 packages requested, all confirmed installed (358 incl. dependencies).
  apt also upgraded 12 existing packages as a side effect: Mesa `25.2.8-…4 → …5` and sqlite3 `…2.8 → …2.9`.
- `venv/lib/python3.12/site-packages/wx` is a symlink to the system `python3-wxgtk4.0` package, so MAVProxy's map/console work. Only `wx` is linked; system-site-packages stays **off**.
  (An earlier attempt turned system-site-packages on. That let Ubuntu's matplotlib 3.6 `mpl_toolkits` shadow the venv's 3.11 copy, causing MAVProxy's "Unable to import Axes3D" warning. Reverted; verified Axes3D imports cleanly and no system `dist-packages` remain on the venv path.)
- `~/qgc` (your own QGC fork) was not touched. QGC test runs used `smoke/qgc-home` as HOME.

## Files

- `install-deps.sh`: apt list (already run).
- `build-after-deps.sh`: rebuild Gazebo + plugin from clean (applies the patch).
- `env.sh`: source for PATH/libs/plugin paths. Safe to source from scripts that use `set -u`.
- `smoke/`: test programs. `logs/`: every build and test log.

## Comparing fixed-wing models (`compare/compare_planes.py`)

Flies several fixed-wing physics models through one identical, scripted profile and tabulates the results:
TAKEOFF to 120 m → LOITER (20 s settle + 60 s scored) → power-off glide in LOITER with `THR_MAX=0` (first 5 s not scored).

```bash
source ~/cert-env/env.sh && python compare/compare_planes.py                          # all models
source ~/cert-env/env.sh && python compare/compare_planes.py --models plane,high-ar   # a subset
source ~/cert-env/env.sh && python compare/compare_planes.py --param AIRSPEED_CRUISE=15  # force a param on all
```

- **Timing:** about 40 s wall-clock per model at the default `--speedup 5`. Durations are measured in simulated time, so the speedup doesn't change results.
- **Output:** `compare/results/<timestamp>/` holds `summary.md` / `summary.csv`, `timeseries.png` and `loiter_tracks.png`. Each model's subfolder has `samples.csv`, `statustext.txt`, the SITL/Gazebo logs and the onboard `logs/*.BIN` (open with `MAVExplorer.py`).
- **Parameters:** each model starts with its frame's stock defaults, exactly as `sim_vehicle.py` loads them. Key parameters are listed per model, and ones that differ are flagged. Use `--param` for a controlled, same-settings comparison.
- **Adding a model:** add an entry to `MODELS` at the top of the script.
  - SITL aircraft file: `model_file=<path to JSON>`, as in `compare/models/plane_high_ar.json`.
  - Gazebo model: `engine="gazebo"` plus a world name.
  - SITL can't open absolute paths: it strips the leading `/` and resolves them inside its run directory. So the harness copies `model_file` into each run directory. The same applies if you pass your own JSON to `sim_vehicle.py`: put it in the directory you launch from.

Things found while building it (run `20261121-143813`):
- **`skywalker_2013.json` is not a different aircraft.** All 38 coefficients and `CGOffset` are identical to SITL's built-in `plane` defaults (`SIM_Plane.h` says they come from the same file). It's kept as a control: `plane` vs `skywalker` differ by ≤0.1 s / ≤0.1 m/s, which is the harness's run-to-run noise. Smaller differences than that mean nothing.
- **`high-ar` is an illustrative variant** (span 3 m, area 0.6 m², parasitic drag halved; nothing else changed). Compared with `plane`:
  - loiter throttle 32% vs 48%
  - glide ratio 3.6 vs 3.1
  - max climb 13.2 vs 10.7 m/s
  - Its loiter hadn't fully converged after the 20 s settle (track still spiralling), so its 107.8 m loiter radius is an average.
- **SITL's built-in planes fly uncoordinated turns:** the measured loiter radius (~96 m) is well above the radius implied by their bank (~72 m). The Gazebo Zephyr's turn is coordinated (63.9 vs 63.3 m). This is a property of the physics models, so it's another reason not to compare across engines.
- **Gazebo aircraft are fully defined in their SDF model file.** Mass/inertia, geometry, per-surface aerodynamics (`LiftDrag` or the stability-derivative `AdvancedLiftDrag`, both installed), propeller and control-surface joints, and the servo-to-joint mapping (`ArduPilotPlugin` `<control>` blocks).

## X-UAV Talon (1718 mm) in Gazebo

Third-party model from [yunusemretom/toy-px4-sim](https://github.com/yunusemretom/toy-px4-sim) (MIT, commit `1115b45`, 2026-11-11). It's the only public full-size Talon found; no tuned ArduPilot params exist publicly.

| Where | What |
|---|---|
| `ref/talon_xuav_toy-px4-sim/` | Untouched upstream copy: model, meshes, `talon.parm`, the author's `run.sh` and `plane_specs.py` (the geometry it was generated from) |
| `sim/models/talon_ap`, `sim/models/talon` | Working copy of the model (meshes live in `talon`) |
| `sim/worlds/talon_runway.sdf` | The Zephyr runway world with the Talon instead (nose down the runway, yaw 93°) |
| `sim/params/xuav_talon.parm` | The author's ArduPilot params, unchanged |

`env.sh` puts `sim/models` and `sim/worlds` on Gazebo's path. Run it interactively (after `source ~/cert-env/env.sh` in each terminal):

```bash
gz sim -v4 -r talon_runway.sdf
sim_vehicle.py -v ArduPlane -f plane --model JSON --add-param-file=$HOME/cert-env/sim/params/xuav_talon.parm --map --console
```

Verified: SITL loads `plane.parm` then `xuav_talon.parm` (same as the author's launcher) and MAVProxy receives 1419 params. Gazebo loads the model with no errors (ArduPilotPlugin, AdvancedLiftDrag, Thruster and 4 servo controllers).
In the harness it's `xuav-talon-gz` (`python compare/compare_planes.py --models xuav-talon-gz`).

**What the model is:**
- Generated from published specs: 1718 mm span, 60 dm² wing, 2.5–3.0 kg (set to 2.8), V-tail, pusher. Geometry details are the author's estimates (chords, NACA 2412 wing, tail sizes); aerodynamics computed with AVL into `AdvancedLiftDrag` coefficients.
- **Motor:** an idealised `Thruster`. ArduPilot throttle (SERVO5) commands 0–30 N directly; there's no prop or motor model. Change `max_thrust_cmd` and the `multiplier` on `<control channel="4">` together.
- **Ground contact:** one low-friction box (μ = 0.1), no wheels, so it takes off sliding on its belly.
- **Params:** simulator setup only. Servo mapping, airspeeds (cruise 15, min 11, max 20 m/s), `TRIM_THROTTLE 34`, `THR_MAX 90`.
  - No roll/pitch rate gains or TECS settings, so ArduPilot flies it on **default gains**.
  - It also sets `ARMING_CHECK 0` and turns failsafes off.

**Measured in the harness** (run `20261121-152139`; repeat run within 0.1):
- takeoff to 108 m in 28.6 s
- loiter at 15.0 m/s with 10.9% throttle
- coordinated turns (85.3 m measured vs 85.2 m implied by bank)
- power-off glide ratio 8.3 at 15 m/s

Cross-check: weight / glide ratio = 2.8 × 9.81 / 8.3 ≈ 3.3 N of drag, versus loiter thrust 10.9% × 30 N ≈ 3.3 N. The aerodynamics and thrust model are consistent with each other.

**First thing to tune:** with 30 N on a 2.8 kg airframe (thrust-to-weight ≈ 1.1), full takeoff throttle gives a ~16 m/s climb and an airspeed overshoot to ~39 m/s, about twice `AIRSPEED_MAX`. A real Talon on its stock power system can't do that. Set `max_thrust_cmd` (and the channel 4 `multiplier`) from your motor/prop's static thrust.

## MFE Believer 1960 in SITL (built-in plane physics)

No Believer model exists for Gazebo or SITL (checked ArduPilot/SITL_Models, local sources and
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
