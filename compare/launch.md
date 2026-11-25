# Catapult load: 59 m/s^2 vs a gentler 25 m/s^2 launch (2026-11-24)

The model jsons launched with `launch_accel 59`, `launch_time 0.39` (assumed 18 m/s exit over ~3.5 m).
Measured on the IMU (AccX, body x) that is **61 m/s^2 peak = 6.3 g, 54-55 m/s^2 mean** over 0.39-0.40 s:
too rough for an EPO airframe MFE rates for hand launch. Gentler variant: `launch_accel 25`,
`launch_time 0.65` (`compare/models/*_gentle.json`, models `believer-avl-at-gentle`,
`believer-5kg-avl-at-gentle`).

Runs: `compare/endurance.py --alt 200 --max-hours 0.1 --param THR_MAX=75 --param TKOFF_DIST=2000
--param TECS_CLMB_MAX=2`; gusts = `--gusts 5:10 --gust-dir 60 --gust-dir-var 30 --seed 1 --param
SIM_WIND_TURB=2`. Measured from the dataflash logs (scratchpad `launch_sum.py`), times from the push.

| Build | Air | Launch | IMU peak / mean | Airspeed at release | Above 3 m | 108 m | Ground contact after release | Peak current | Run |
|---|---|---|---|---|---|---|---|---|---|
| Base 5.0 kg | calm | 59 m/s^2 | 6.3 g / 54.8 | 17.2 m/s | 6.6 s | 27.2 s | none | 41.1 A | 011216 |
| Base 5.0 kg | calm | 25 m/s^2 | 2.7 g / 22.4 | 13.2 m/s | 20.5 s | 43.1 s | 7.0 s, 1.9 m/s | 42.4 A | 011044 |
| Base 5.0 kg | gusts | 25 m/s^2 | 2.7 g / 22.6 | 12.9 m/s | 6.5 s | 21.3 s | none | 42.0 A | 011046 |
| Starlink 5.9 kg | calm | 59 m/s^2 | 6.3 g / 54.8 | 18.2 m/s | 8.4 s | 30.7 s | none | 42.2 A | 011218 |
| Starlink 5.9 kg | calm | 25 m/s^2 | 2.7 g / 22.4 | 14.0 m/s | 155 s | 213 s | 8.5 s, 2.6 m/s, then belly roll | 42.8 A | 011048 |
| Starlink 5.9 kg | gusts | 25 m/s^2 | 2.7 g / 22.4 | 14.1 m/s | 8.3 s | 24.6 s | none | 42.6 A | 011050 |
| Starlink 5.9 kg | gusts | 59 m/s^2 (endurance run) | 6.3 g / 54.0 | ~19 m/s | - | - | ~9 s, 3.4 m/s | 42 A | 20261124-002024 |

- The gentle launch releases at 13-14 m/s, 1.15-1.25x the model's 1 g stall (11.2-11.6 m/s).
- In gusts both builds climbed out cleanly. In calm both hopped and touched down; the Starlink build then
  slid on its belly at 13 m/s and 75 % throttle for 2.5 min until the take-off stage ended by
  TKOFF_DIST (13 m/s x 150 s = 2000 m), then climbed normally.
- Peak current is 41-43 A in every case: the take-off throttle cap, not the launch, sets it.

Why calm is worse (inferred, not proven): SITL launches level along the ground, adds a downward force
of a/3 during the push (as its `-catapult` frame does), and drags the belly with 0.3 x v m/s^2
(~4 m/s^2 at 13 m/s), which 75 % thrust only just balances. A real rail is inclined and the aircraft is
airborne at release, so these runs do not show whether 2.5 g is enough in reality; they show that a
13-14 m/s release is marginal for SITL's level ground launch.

# 3 g launch + 5 s full-throttle boost (2026-11-24)

Models `believer-avl-at-3g`, `believer-5kg-avl-at-3g`: `launch_accel 29.4`, `launch_time 0.51`
(3 g, ~15 m/s over ~3.8 m on a real rail). Parameters: `TKOFF_THR_DELAY 2` (0.2 s; the parameter is in
0.1 s steps, so the requested 150 ms is not settable), `TKOFF_THR_MAX 100`, `TKOFF_THR_MAX_T 5` (full
throttle forced for 5 s from motor start), `THR_MAX 75`, and `--param-at 5.3:TKOFF_THR_MAX=75` to bring
the take-off cap back to 75 % after the boost. On the aircraft that last step needs a Lua script; with
parameters alone the take-off cap stays at TKOFF_THR_MAX for the whole take-off stage.

| Build | Air | IMU peak / mean | Motor on | Throttle >= 95 % | Above 3 m | 108 m | Ground contact | Peak current | Run |
|---|---|---|---|---|---|---|---|---|---|
| Base 5.0 kg | calm | 3.1 g / 26.9 | 0.29 s | 1.2-5.4 s | 3.9 s | 19.0 s | none | 86.9 A | 012128 |
| Base 5.0 kg | gusts | 3.1 g / 26.9 | 0.31 s | 1.2-5.3 s | 3.9 s | 17.5 s | none | 86.9 A | 012130 |
| Starlink 5.9 kg | calm | 3.1 g / 26.9 | 0.28 s | 1.2-5.3 s | 4.3 s | 22.1 s | none | 88.9 A | 012132 |
| Starlink 5.9 kg | gusts | 3.1 g / 26.9 | 0.31 s | 1.2-5.3 s | 4.3 s | 16.3 s | none | 88.9 A | 012134 |

- All four climb out cleanly, faster than with the 6.3 g launch at 75 % (calm: 108 m in 19-22 s vs 27-31 s).
- The motor starts 0.3 s after the push begins, i.e. while still on the 0.51 s stroke; the throttle
  slews to 95 % by 1.2 s, so full throttle is held ~4 s.
- Cost: 87-89 A for those ~4 s (44 A per motor), the same as the old 100 % take-off peak.
- Without the timed cap (Starlink, runs 012232 calm / 012234 gusts) TECS used up to 86-88 % throttle
  (59-62 A) between the end of the boost and 108 m, so the drop back to 75 % really needs the script.

## Full climbs to 900 m with the same set-up (gusts), and a failed launch

Runs 012657 (Starlink) and 012655 (base), `--alt 900`, otherwise as above. Starlink: clean, 900 m at
8.8 min, 88.9 A peak, at most 41 A after the boost. **Base: failed launch** - hopped to 1.7 m, hit the
ground at 6.3 s (3.5 m/s) and slid on its belly at ~41 A until 142 s, 108 m at 217 s. The same
configuration had launched cleanly in run 012130, so the boosted launch is 6 clean of 7 in SITL.

First 9 s, clean (012130) vs failed (012655): both roll on the ground for ~3.5 s at 100 % throttle to
~20 m/s with the pitch rising to the 15 deg take-off target. The clean one rotated to 26-34 deg and
climbed; the failed one reached 1.7 m at 19-22 deg, sank, and sat on the ground at 17 deg pitch while
airspeed fell 23 -> 15 m/s at 75 %. On the ground the pitch is the angle of attack, and 17 deg is past
the model's CLmax angle (10 deg, oscillations.md), so the wing is stalled while TAKEOFF holds 15 deg.
Inferred, not proven: this is the level-ground SITL launch again; from an inclined rail the aircraft
leaves along the rail with a low angle of attack. The chart on slide 4 shows the Starlink climb only.

# 3.3 g launch and a lower take-off pitch (2026-11-24, 12 + 12 take-offs)

Models `*-3g3`: `launch_accel 32.4`, `launch_time 0.48` (3.3 g over the same ~3.8 m stroke, IMU 3.4 g peak /
29.8 m/s^2 mean). Boost as above (100 % for 5 s from motor start, then 75 %). Each build x calm / gusts seed 1 /
gusts seed 2 x two repeats, `--alt 200`. Batch scripts in the scratchpad (`batch33.sh`, `batch33r.sh`).

**`TKOFF_LVL_PITCH` alone does not lower the take-off pitch.** With an airspeed sensor it is only the minimum;
TECS sets the target up to PTCH_LIM_MAX_DEG (15), which is the 15 deg seen in every log of the first batch.
The take-off-only cap in 4.7.3 is the rotation hold: `TKOFF_ROTATE_SPD 15` (about 1.3x stall) with
`TKOFF_GND_PITCH 5` holds 5 deg until 15 m/s airspeed, then ramps to `TKOFF_LVL_PITCH 8` (scaled by ground
speed / AIRSPEED_CRUISE) until ground speed reaches cruise, then TECS takes over (takeoff.cpp).

| Batch | Pitch target at 3 s | Ground contact after release | Above 3 m | 108 m | Pitch peak (first 15 s) | Max pitch below 1.5 m |
|---|---|---|---|---|---|---|
| 3.3 g, target 15 deg (`TKOFF_LVL_PITCH 8` ineffective) | 15 | **1 of 12** (Starlink, gusts s1, 5.5 s, 2.0 m/s) | 3.8-4.3 s (11.0 s for the contact) | 20-33 s | 21-54 deg | 19-27 deg |
| 3.3 g + rotation hold (5 deg to 15 m/s, then <= 8 deg) | 8 Starlink / 13 base | **0 of 12** | 4.7-5.6 s | 23-38 s | 26-35 deg | 18-23 deg |

Peak current 86.7 A (base) / 88.8 A (Starlink) in all 24, as before.

- 0 of 12 against 1 of 12 is not a statistically separable difference on its own; with the earlier 1 of 7 at
  3 g / 15 deg, the record is 2 contacts in 19 take-offs at a 15 deg target and 0 in 12 with the hold.
- The hold lowers the peak pitch (32-54 -> 26-35 deg) and costs ~1 s to 3 m and ~4 s to 108 m.
- **The attitude still overshoots the target by 3-4x** (18-23 deg while below 1.5 m against a 5-8 deg demand),
  around the lift-off and the end of the boost (4.4-6.1 s). Not traced. The model's pitch stability and
  control derivatives are SITL's skywalker defaults, so this may be the model rather than the gains.

## Adopted (2026-11-24)

The 3.3 g launch is now the default in the six believer model jsons, and the take-off block (TKOFF_THR_DELAY 2,
TKOFF_THR_MAX 100, TKOFF_THR_MAX_T 5, TKOFF_ROTATE_SPD 15, TKOFF_GND_PITCH 5, TKOFF_LVL_PITCH 8) is in
sim/params/believer.parm and believer_5kg.parm. Full climbs to 900 m in gusts with the defaults (plus
`--param-at 5.3:TKOFF_THR_MAX=75`): base 015048 and Starlink 015050, both clean (above 3 m at 4.8 / 5.5 s,
108 m at 26.7 / 33.6 s, 86.7 / 88.8 A peak, 900 m at 9.2 / 8.8 min). With the hold: 0 contacts in 14.

## AIRSPEED_MIN 14 (2026-11-24)

AIRSPEED_MIN raised from MFE's 12 to 14 m/s in believer_mfe.parm (and believer.parm / believer_5kg.parm,
which it overrides). 13.5 was asked, but AIRSPEED_MIN is an AP_Int16 in 4.7.3 (AP_FixedWing.h), so the user
chose 14: 1.21x the 5.0 kg model's stall, 1.25x the 5.9 kg. Check flights 021734-021740 (both builds, calm and
gusts, to 900 m): PARM shows AIRSPEED_MIN 14 and the take-off block; all four launches clean (0 of 18 with the
pitch hold now); calm cruise 169 W / 196 W, identical to the earlier references.
