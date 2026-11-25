# Roll/pitch oscillations: MFE Believer with MakeFlyEasy stock gains (SITL)

Date: 2026-11-22. Written from the logs listed below; numbers come from `compare/log_health.py`
(`health.md` in each run folder) and `compare/log_tuning.py` (`tuning.md`).

## Setup

- ArduPlane 4.7.3 SITL with the local patch (`patches/ardupilot-sitl-plane-electric-propulsion.patch`),
  now including the backported upstream fix for the SITL pitot double EAS conversion. After the fix the
  simulated airspeed sensor matches SITL's pitot EAS (mean offset 0.00 m/s, was -0.53 m/s at 590 m AMSL).
- Airframes: `believer-5kg-avl-mfe` (5.0 kg, 1.96 m) and `believer-avl-mfe` (5.9 kg, 2.36 m inserts,
  Starlink). Aerodynamics from AVL with an ESTIMATED tail, control surfaces and CG
  (`aero/avl/believer_avl.py`); ruddervator authority for MIXING_GAIN 1.
- Gains and limits: MakeFlyEasy stock `Believer_V4.6.3.param` (`sim/params/believer_mfe.parm`),
  AIRSPEED_CRUISE 19 (the file's 1900 is a cm/s leftover), ROLL_LIMIT_DEG 30, loop rate 100 Hz.
- Flight: Tsuniv home (290 m AMSL), rubber-catapult launch, TAKEOFF to 120 m, GUIDED to 300 m above home,
  500 m orbit at 19 m/s, RTL at the end. Still air (no wind, no turbulence).

## Method

For every roll demand step larger than 8 deg after liftoff (SITL truth altitude > 0.5 m, plus 1 s):
- overshoot = how far the roll angle went past the new demand;
- sign changes = how often the roll error changed sign while larger than 1.5 deg, within 6 s or until
  the demand moved by more than 5 deg;
- peaks = successive error extrema; decay = second peak / first peak (below 0.3 well damped,
  above 0.6 lightly damped).

## Verdict

- **Base 5.0 kg: lightly damped roll ringing after every roll command.** Overshoot 9-16 deg past the
  demand, 6-9 error sign changes, decay 0.66-0.73 per half-cycle, period about 1.25 s (0.8 Hz). Roll
  reaches 45 deg against ROLL_LIMIT_DEG 30. Same in the 10-minute and the endurance flight, so it is
  repeatable, not a one-off.
- **Starlink 5.9 kg: one overshoot, then it settles.** Overshoot 4-10 deg, 2-3 sign changes, roll up to
  39 deg. The -31 -> 0 deg step is flagged by the decay rule (0.81-0.83) but its error goes
  4.5 -> 3.6 -> 0.9 deg: one overshoot and one undershoot, then settled.
- **Cruise: no oscillation on either model.** Roll varies by 0.07 deg and pitch by 0.03 deg after
  removing slow drift; the largest gyro spectral peaks are 0.1 deg/s (roll, 0.6-0.7 Hz).
- **Pitch: no oscillation of its own** (no pitch steps; pitch rate peaks below 0.1 deg/s). The pitch
  excursions to 20.5-23.9 deg (limit 15) happen 1-2 s after GUIDED takes over, during the roll
  overshoot at -33 deg bank, so they are driven by the roll ringing.
- **Dutch roll: present but tiny.** Sideslip oscillation at 0.6 Hz (Starlink) and 0.8 Hz (base),
  0.01-0.08 deg RMS.

## Roll steps

| Model | Flight | Step (deg) | Overshoot | Sign changes | Error peaks (deg) | Decay |
|---|---|---|---|---|---|---|
| Base 5.0 kg | 10 min | +15 -> -29 (GUIDED entry) | 16.1 | 9 | 16.1, 11.0, 10.2, 7.1 | 0.68 |
| Base 5.0 kg | 10 min | -32 -> 0 | 12.2 | 8 | 12.2, 8.9, 5.7, 4.9 | 0.73 |
| Base 5.0 kg | 10 min | +4 -> +30 (RTL entry) | 9.1 | 3 | 9.1, 6.0 | 0.66 |
| Base 5.0 kg | endurance | +14 -> -29 (GUIDED entry) | 15.9 | 9 | 15.9, 10.7, 10.0, 6.8 | 0.67 |
| Base 5.0 kg | endurance | -29 -> 0 | 11.0 | 6 | 11.0, 7.9, 5.1, 4.4 | 0.72 |
| Base 5.0 kg | endurance | +4 -> +30 (RTL entry) | 9.1 | 3 | 9.1, 6.1 | 0.66 |
| Starlink 5.9 kg | 10 min | +16 -> -29 (GUIDED entry) | 10.3 | 3 | 10.3, 2.8 | 0.28 |
| Starlink 5.9 kg | 10 min | -31 -> 0 | 4.2 | 2 | 4.2, 3.5, 0.7 | 0.83 |
| Starlink 5.9 kg | 10 min | +4 -> +30 (RTL entry) | 4.7 | 2 | 4.7, 1.9 | 0.41 |
| Starlink 5.9 kg | endurance | +17 -> -29 (GUIDED entry) | 10.3 | 3 | 10.3, 2.6 | 0.25 |
| Starlink 5.9 kg | endurance | -31 -> 0 | 4.5 | 2 | 4.5, 3.6, 0.9 | 0.81 |
| Starlink 5.9 kg | endurance | +4 -> +30 (RTL entry) | 4.7 | 2 | 4.7, 2.0 | 0.43 |

Short steps right after liftoff (TAKEOFF heading corrections, 1-1.3 s windows) are left out: 4-8 deg
overshoot, 1-2 sign changes.

## Mechanism (base, step at 57 s, earlier run with the same gains)

At the step the roll rate demand hits RLL2SRV_RMAX 75 deg/s; feed-forward (RLL_RATE_FF 0.571) puts the
ailerons at -74 % and the measured roll rate reaches -124 deg/s while the demand has already dropped
to -29 deg/s. The low P and I (0.116, 0.024) then add little damping, and the angle loop
(RLL2SRV_TCONST 0.45 s) keeps re-commanding the swing. The Starlink model has more roll inertia
(0.55 vs 0.34 kg m^2) and about 18 % less aileron moment per unit of roll inertia
(q S b c_l_deltaa / Ixx), so the same feed-forward overshoots less.

## Same airframes with SITL's plane.parm gains (for comparison)

Earlier 10-minute flights at 175 m (before the airspeed fix, ~3 % faster than commanded):
- Base: largest roll step +27 -> +9 deg, 1.2 deg overshoot, no sign changes.
- Starlink: +28 -> -61 deg reversal did not reach the demand before the demand moved (rate-limited);
  no ringing.

So on this model the stock SITL gains are sluggish and the MFE gains overshoot; the right roll
feed-forward for this model lies between 0.24 and 0.57.

## What this does and does not show

- The AVL aerodynamics use an estimated tail, aileron size and CG. MFE's gains were presumably tuned
  on a real Believer; the ringing means either the real aircraft has less roll authority (or more
  roll damping) than this model, or MFE's tune is aggressive. Measured aileron dimensions or a real
  flight log would decide which.
- Still air only; SITL's turbulence model is unsuitable for this (see the turbulence runs).
- The SITL launcher pushes the aircraft along the ground, so everything before liftoff + 1 s is
  excluded (aileron saturation and high angle of attack there are ground-run artifacts).
- No gains were changed. Any retune (AUTOTUNE or manual) is the operator's call.

## Endurance with the airspeed fix (corrected: payload draw added, 90 % of pack)

| | Base 5.0 kg, 6S4P | Starlink 5.9 kg, 6S5P |
|---|---|---|
| Cruise 19 m/s EAS, 19.5 m/s ground | 167 W | 195 W |
| Corrected flight time | 2 h 07 min | 1 h 58 min |
| Same before the fix | 2 h 01 min (177 W) | 1 h 52 min (207 W) |

## Logs

| Run | Folder |
|---|---|
| Base, 10 min | `compare/results/endurance-20261122-185519/believer-5kg-avl-mfe` |
| Base, endurance | `compare/results/endurance-20261122-185515/believer-5kg-avl-mfe` |
| Starlink, 10 min | `compare/results/endurance-20261122-185521/believer-avl-mfe` |
| Starlink, endurance | `compare/results/endurance-20261122-185517/believer-avl-mfe` |

# After AUTOTUNE (SITL, same airframes)

`compare/autotune.py` flew ArduPlane AUTOTUNE (AUTOTUNE_LEVEL 6, the autotest procedure: full-stick
doublets reversed every 1 s, roll then pitch) at 300 m, starting from the MFE gains. Both axes printed
"Finished", so the gains were saved. Results: `sim/params/believer_5kg_avl_autotune.parm` and
`sim/params/believer_avl_autotune.parm` (runs `compare/results/autotune-20261122-191414` and `-191416`),
flown with harness models `believer-5kg-avl-at` / `believer-avl-at` (MFE layer + tuned layer). The
baseline before the tune is stored in `sim/params/snapshots/mfe-baseline-20261122/`.

## Gains

| Parameter | SITL plane.parm | MFE stock | AUTOTUNE base 5.0 kg | AUTOTUNE Starlink 5.9 kg |
|---|---|---|---|---|
| RLL_RATE_P | 0.3 | 0.116 | 1.354 | 1.760 |
| RLL_RATE_I | 0.25 | 0.024 | 0.297 | 0.415 |
| RLL_RATE_D | 0.0174 | 0 | 0.0164 | 0.0470 |
| RLL_RATE_FF | 0.237 | 0.571 | 0.297 | 0.415 |
| RLL2SRV_TCONST | 0.25 | 0.45 | 0.5 | 0.5 |
| PTCH_RATE_P | 0.15 | 0.108 | 0.746 | 0.746 |
| PTCH_RATE_I | 0.11 | 0.054 | 0.560 | 0.560 |
| PTCH_RATE_D | 0.0073 | 0 | 0.0164 | 0.0164 |
| PTCH_RATE_FF | 0.596 | 0.517 | 0.264 | 0.299 |
| PTCH2SRV_TCONST | 0.25 | 0.45 | 0.75 | 0.75 |
| Rate filters FLTT / FLTD | 3 / 12 | 3 / 12 | 3.18 / 10 roll, 2.12 / 10 pitch | same |

Pitch P and D are identical for both airframes: plane AUTOTUNE changes P and D in fixed steps, and
both tunes stopped on the same step (the ArduPilot autotest notes the same repeatability).

## Roll steps, 10-minute flights (Tsuniv, 300 m, 19 m/s, still air)

| Model | Step (deg) | MFE: overshoot / sign changes | AUTOTUNE: overshoot / sign changes |
|---|---|---|---|
| Base 5.0 kg | GUIDED entry, ~+16 -> -29 | 16.1 / 9 | 2.1 / 1 |
| Base 5.0 kg | ~-31 -> 0 | 12.2 / 8 | 0.1 / 0 |
| Base 5.0 kg | RTL entry, +4 -> +30 | 9.1 / 3 | 0.3 / 0 |
| Starlink 5.9 kg | GUIDED entry, ~+16 -> -29 | 10.3 / 3 | 2.2 / 1 |
| Starlink 5.9 kg | ~-31 -> 0 | 4.2 / 2 | 0.0 / 0 |
| Starlink 5.9 kg | RTL entry, +4 -> +30 | 4.7 / 2 | 0.3 / 0 |

- Max roll 32.3 / 32.2 deg (limit 30) instead of 45 / 39 deg.
- Cruise: roll 0.04 deg, pitch 0.02 deg fast variation; largest roll gyro peak 0.05 deg/s (was 0.1).
- Dutch roll: 0.21 Hz, 0.02-0.03 deg sideslip RMS.
- Cruise power unchanged (167 W base, 195 W Starlink): the tune does not change endurance.

## New finding: pitch overshoot at liftoff

Both tuned flights pitch to about 28 deg (limit 15) right at liftoff, then take ~3 s to come down
with the elevator near neutral. During the SITL ground run the aircraft cannot follow the 15 deg
takeoff pitch demand, the elevator holds 66-87 % and the pitch integrator (I 0.56, ten times MFE's)
winds up; at liftoff the stored integrator keeps the nose high. With the MFE gains the liftoff peak was
lower (20-24 deg, and those peaks came from roll coupling at GUIDED entry). This is a SITL ground-launch
artifact for the catapult case, but it shows the tuned pitch integrator is sensitive to any phase where
the elevator cannot achieve the demand (ground contact, saturation).

## Caveats

- AUTOTUNE ran on the AVL model with an ESTIMATED tail, aileron size and CG; the gains fit that model,
  not necessarily the real aircraft. On the real Believer, AUTOTUNE has to be flown again.
- Logs: base `compare/results/endurance-20261122-191454/believer-5kg-avl-at`,
  Starlink `compare/results/endurance-20261122-191456/believer-avl-at`.

## Endurance at 900 m above Tsuniv (tuned gains, airspeed fix, 19 m/s)

| | Base 5.0 kg, 6S4P | Starlink 5.9 kg, 6S5P |
|---|---|---|
| Climb to 900 m | 3.5 min, 29.0 Wh | 3.5 min, 35.3 Wh |
| Cruise (19 m/s EAS, 20.1 m/s ground) | 169 W | 196 W |
| Corrected flight time | 2 h 02 min | 1 h 54 min |
| Same at 300 m (MFE gains; gains do not change cruise power) | 2 h 07 min, 167 W, climb 11.6 Wh | 1 h 58 min, 195 W, climb 15.0 Wh |

Roll behaviour at 900 m matches the 300 m tuned flights (overshoot ~2 deg, max roll 32 deg).
Logs: `compare/results/endurance-20261122-193336/believer-5kg-avl-at`,
`compare/results/endurance-20261122-193338/believer-avl-at`.

# Wind and turbulence at 900 m (tuned gains)

`compare/endurance.py --gusts 5:10 --gust-dir 60` re-draws SIM_WIND_SPD uniformly in 5-10 m/s and
SIM_WIND_DIR within 60 +- 30 deg every 5-20 s from a fixed seed (SITL eases to each value over
SIM_WIND_TC 5 s). Turbulence runs add `--param SIM_WIND_TURB=2` (about 2 m/s RMS, horizontal and
vertical, applied as one vector over the whole airframe). Tsuniv, 900 m above home, 19 m/s.
The EKF estimated 7.4 m/s from 61-62 deg in every run, confirming the schedule reached SITL.

## Endurance

| | Base 5.0 kg | Starlink 5.9 kg |
|---|---|---|
| Calm | 2 h 02 min, 169 W | 1 h 54 min, 196 W |
| Gusty wind 5-10 m/s | 2 h 01 min, 170 W | 1 h 54 min, 197 W |
| Wind + turbulence | 0 h 50 min, 466 W | 1 h 43 min, 227 W |

Runs: `endurance-20261123-114944` / `-114946` (wind), `-114207` / `-114948` (wind + turbulence);
10-minute flights `-113932` / `-113934` (wind), `-113936` / `-113938` (wind + turbulence).

## Gusty wind alone: no effect worth reporting

Cruise power is within 1 W of calm air and endurance is unchanged. Peak angle of attack 7.5-8.6 deg
(stall 12.5 deg), cruise roll error std 0.35 deg with a 4-5 deg maximum, airspeed held 14-27 m/s
against a 19 m/s demand, throttle peaking at 88-89 %. Roll steps still settle with about 2 deg
overshoot. Ground speed drops to 17.9-18.0 m/s because the orbit averages the headwind component.

## Wind + turbulence: repeated sustained stalls

Both airframes departed, at different times in different runs, and the SITL aircraft hit the ground
and kept flying (SITL does not end the flight on impact), which is why the endurance figures and the
466 W / 227 W cruise numbers are meaningless as power measurements.

| Run | Time past 12.5 deg AoA | Longest episode | Ground impacts |
|---|---|---|---|
| Base, endurance (3026 s) | 430 s | 222 s | 3 |
| Starlink, endurance (7578 s) | 278 s | 151 s | 2 |
| Base, 10 min | 1.9 s | 0.4 s | 0 |
| Starlink, 10 min | 181 s | 178 s | 1 |

### Mechanism (base endurance, first departure at 397 s)

| t, s | EAS, m/s | Throttle, % | Pitch / demand, deg | AoA, deg | h - hdem, m |
|---|---|---|---|---|---|
| 396 | 19.0 | 41 | 1.5 / 1.8 | 5.8 | +1.0 |
| 397 | 16.2 | 66 | -0.9 / 5.4 | 9.7 | -0.3 |
| 398 | 17.2 | 93 | 2.1 / 14.7 | 15.6 | -4.1 |
| 399 | 19.7 | 100 | 8.9 / 15.0 | 19.0 | -9.1 |
| 403 | 19.7 | 100 | 12.9 / 15.0 | 27.4 | -31.9 |
| 411 | 20.0 | 100 | 13.6 / 15.0 | 26.3 | -66.0 |

A gust drops the airspeed to 16 m/s. TECS answers with full throttle and the maximum pitch demand
(TECS_PITCH_MAX 15), which at that speed needs an angle of attack past the 12.5 deg stall. Lift
collapses, the aircraft sinks, the growing height error keeps the pitch demand pinned at 15 deg, and
it never recovers. The stall is driven by the climb demand, not by low speed as such: 16 m/s is still
1.4x the model's 11.6 m/s stall speed. Cruise spent 173 of 63647 samples below AIRSPEED_MIN 12 m/s.

### How much of this is the simulator

Uncertain, and worth saying plainly before any of it is quoted:

- **The trigger is plausible.** Pitching up to hold altitude when slow is a real ArduPlane behaviour,
  and MFE's TECS_SPDWEIGHT 0.8 biases pitch toward height rather than speed. The ArduPilot forum
  thread on a Believer crash in AUTO blames gusts plus attitude settings for a similar departure.
- **The non-recovery is probably exaggerated.** SITL blends to a flat-plate model past the stall with
  no spanwise variation, and the elevator at 100 % overrides the model's own nose-down moment. A real
  aircraft would likely drop its nose and recover.
- **The gust field is not realistic.** One uniform vector over the whole airframe, re-randomised in
  azimuth every physics step, with no spatial correlation. Earlier turbulence runs showed the model's
  own spectrum dominating the pitch response, and 2 m/s of turbulence lowering apparent cruise power.

**No parameters were changed.** Candidates if the margin is to be opened up, all the operator's call:
AIRSPEED_MIN, TECS_PITCH_MAX, TECS_SPDWEIGHT, or a higher cruise speed.

# Margin test: can a TECS setting prevent the stall lock-in?

Base airframe, 900 m, fixed 8 m/s wind from 60 deg plus SIM_WIND_TURB 2, so every run meets the same
deterministic turbulence sequence (SITL's rand() is never seeded, so glibc replays one sequence).
Full endurance runs. Replicated at 880 and 920 m, which shifts the aircraft's phase through that
sequence and so acts as an independent sample.

## First, a correction to the stall threshold

Earlier runs were scored against the json's `alpha_stall` (12.5 deg). That key is the centre of
SITL's sigmoid blend between the linear lift curve and the flat-plate model, not the angle of CLmax.
Reconstructing the blend (`compare/stall_summary.py`) puts CLmax at **10.0 deg**, where lift starts
falling. All figures here use 10.0 deg; the earlier numbers were undercounts.

## The stall is not a speed event

At 1190 m AMSL and 5.0 kg the model's 1 g stall is 12.3 m/s TAS, 11.6 m/s EAS. The aircraft was at
16-22 m/s EAS throughout every departure, where stalling by load factor alone would need 1.9-2.7 g.
What exceeded CLmax was the angle between the nose and the flight path:

| t, s | Pitch | Flight path (from inertial velocity) | pitch - gamma | AoA logged | EAS |
|---|---|---|---|---|---|
| 396 | +1.5 | -2.3 | 3.8 | 5.8 | 19.0 |
| 398 | +2.1 | -15.8 | 17.8 | 15.6 | 17.2 |
| 403 | +12.9 | -14.7 | 27.6 | 27.4 | 19.7 |
| 407 | +19.1 | -11.8 | 30.9 | 29.6 | 17.9 |

Nose held 8-19 deg up while descending along a path 12-17 deg down. Past CLmax the lift falls, the
sink rate grows, the path steepens and the angle of attack grows again: the loop closes on itself.
TECS_PITCH_MIN 0 means PTCH_LIM_MIN_DEG, so -25 deg of nose-down was available and simply unused.

## What the settings did

| Setting | 900 m | 880 m | 920 m | Departures |
|---|---|---|---|---|
| Baseline (SPDWEIGHT 0.8, PITCH_MAX 15) | 8591 s / 143 s | 8592 s / 139 s | none | 2 of 3 |
| TECS_SPDWEIGHT 1.5 | none | 4300 s / 147 s | none | 1 of 3 |
| TECS_PITCH_MAX 10 | 4301 s / 155 s | - | - | 1 of 1 |
| Both | 31 s (climb), 4296 s / 133 s | - | - | 1 of 1 |

**TECS_PITCH_MAX 10 is the wrong lever and makes things worse.** Capping pitch does not cap angle of
attack, because the flight path sets it just as much as the nose does. At the ~4300 s disturbance the
two runs with PITCH_MAX 10 departed while both runs with PITCH_MAX 15 rode it out. Its demanded pitch
sat pinned at its +10 cap through the whole departure.

**TECS_SPDWEIGHT 1.5 gives the right response but not reliable protection.** At the 4300 s event at
900 m it commanded **-8.3 deg of pitch**, traded height for speed, recovered in 1.3 s and lost 10 m;
the PITCH_MAX 10 runs commanded +10 and lost 900 m. That is exactly the intended behaviour. But the
same setting departed at 880 m, so one sample in three still failed.

With three samples a setting, 2 of 3 against 1 of 3 is not a result. Bank angle at the disturbance
was 4-6 deg in every run, so that is not the discriminator either. The outcome is bimodal (a run
either keeps station within 15 m or loses 880 m and reaches the ground) and sits near a knife edge
that 20 m of working altitude was enough to flip.

**Nothing is recommended on this evidence and no parameter was changed.**

## The scenario itself remains suspect

The runs that did not depart returned **2 h 24 min at 141 W**, against **2 h 02 min at 169 W in calm
air**. Turbulence cutting cruise power by 17 % is not physical; a fluctuating flow field should cost
energy, not supply it. A quasi-steady aerodynamic model sampling a rapidly changing uniform gust
vector appears to extract spurious energy from it. That is the third independent sign that SITL's
turbulence is unfit for this question, after the earlier runs where 2 m/s of turbulence lowered
measured power while 4 m/s raised it, and where the pitch response peaked at the gust filter's own
corner frequency.

Before spending more on TECS settings, the gust model is the thing to fix or replace.

# Fixed gust model (2026-11-23)

## The defect

SITL's `update_wind` (SIM_Aircraft.cpp) advanced the horizontal gust azimuth by `2 * rand()` every
physics step. That overflows a signed int (RAND_MAX 2147483647), so the azimuth jumped to ~1e9 deg and
`cosf`/`sinf` of ~1e7 rad carried no precision. Reproduced in a standalone harness
(scratchpad `gust/t.cpp`, same `rand()` and `rand_normal`):

| | Std N / E / D, m/s | Horizontal correlation time |
|---|---|---|
| Old SITL model, SIM_WIND_TURB 2 | 1.39 / 1.39 / 2.01 | 0.00083 s = one 1200 Hz step |
| Replacement | 2.0 per axis (exact in theory; 2.04 / 1.70 / 1.45 sampled over 600 s) | 27.3 s (target 28.1 s) |

So the horizontal gust direction was white noise at the frame rate while only its magnitude was
filtered, horizontal intensity came out at sigma/sqrt(2), and the 0.98-per-step filter made the
spectrum depend on SIM_RATE_HZ. A quasi-steady aerodynamic model fed that near-white gust extracted
spurious energy from it (cruise power 17 % below still air).

## The replacement

An exponentially correlated (Ornstein-Uhlenbeck) gust in each earth-frame axis, exactly discretised
(alpha = exp(-dt V/L), beta = sqrt(1 - alpha^2)) so the std is SIM_WIND_TURB at any frame rate. The
correlation length is the MIL-F-8785C Dryden integral scale: height above ground below 305 m, 533 m
above, floored at 10 m. Only the first-order (Dryden u) shape is used for all three axes; the true
lateral/vertical Dryden spectra are second order, a refinement not worth having while the gust is one
uniform vector over the airframe. No new parameters. In the local patch file; applies cleanly to 4.7.3.

## Results: same conditions before and after (900 m, tuned gains)

| Run | Corrected endurance | Cruise power | Longest AoA > CLmax | Worst height shortfall | In-flight ground impacts |
|---|---|---|---|---|---|
| Base, calm (reference) | 2 h 02 min | 169 W | - | - | 0 |
| Base, wind 8 m/s, turbulence off (control, new build) | 2 h 02 min | 169 W | 0 s | 15 m | 0 |
| Base, gusts 5-10 m/s + turbulence, **old model** | 0 h 50 min | 466 W | 229 s | 901 m | 3 |
| Base, gusts 5-10 m/s + turbulence, **new model** | **1 h 54 min** | **177 W** | 51 s | **15 m** | **0** |
| Starlink, calm (reference) | 1 h 54 min | 196 W | - | - | 0 |
| Starlink, gusts + turbulence, **old model** | 1 h 43 min | 227 W | 152 s | 901 m | 2 |
| Starlink, gusts + turbulence, **new model** | **1 h 48 min** | **213 W** | 32 s | **11 m** | **0** |
| Base, wind 8 m/s + turbulence, new model, 880 / 900 / 920 m | 1 h 48 / 1 h 57 / 1 h 56 | 192 / 174 / 178 W | 47 / 46 / 49 s | 8 / 11 / 15 m | 0 / 0 / 0 |

Ground contacts at 30-32 s in some runs are the catapult ground run, before liftoff.

- **The lock-in is gone.** In all five turbulence endurance flights the aircraft held its height within
  8-15 m; none fell from 900 m. Before the fix, three of four turbulence endurance flights did.
- **Energy is physical again.** Turbulence now costs power: +3 to +14 % on the base airframe, +9 % on
  Starlink, so 5-14 min of endurance, instead of the impossible 17 % saving.
- **The control run matches calm exactly** (2 h 02 min, 169 W), so the change does nothing when
  SIM_WIND_TURB is 0.

## What is left

- **Angle of attack still reaches CLmax 7-12 % of the time,** in episodes of up to 30-50 s, but the
  aircraft keeps its height through them, so this is flight near the lift peak, not a departure.
  Consistent with the margin: cruise sits at about 2 deg AoA against a 10 deg CLmax, which absorbs a
  vertical gust of about 2.8 m/s at 20 m/s TAS; a 2 m/s RMS vertical gust exceeds that about 8 % of
  the time. That match is an estimate; why individual episodes last tens of seconds is not traced.
- **ArduPlane now sometimes disables the airspeed sensor** in these conditions (base 10-min flight at
  114 s, Starlink endurance at 2126 s; both re-enabled 40-45 s later). The EKF's wind state cannot
  follow a slowly varying 2 m/s gust on top of 5-10 m/s gust steps, the airspeed innovation test ratio
  (XKF4 SVT) rises to 1.2-1.5, and with ARSPD_OPTIONS 11 / ARSPD_WIND_GATE 5 the health check
  disables the sensor. In the 10-min flight the stall started at 104 s, before the disable, so the
  disable followed the upset rather than causing it. False airspeed failures in fast-changing wind are
  a known real ArduPlane behaviour; it never appeared with the old white-noise gust because that
  averaged out.

# Margin test rerun on the fixed gust model (2026-11-23, 13:42-13:50)

Base airframe, tuned gains, fixed 8 m/s wind from 60 deg + SIM_WIND_TURB 2, full endurance, 900 and
920 m. Baselines from the earlier new-model batch. CLmax angle 10.0 deg. Ground contacts at 30 s are the
catapult ground run; no in-flight contact and no airspeed-sensor disable in any of the eight variants.

| Variant | Alt, m | Time past CLmax | Longest episode | Worst height loss | Cruise power | Corrected endurance | Run |
|---|---|---|---|---|---|---|---|
| Baseline | 900 | 8.8 % | 46 s | 11 m | 174 W | 1 h 57 | -131238 |
| Baseline | 920 | 8.5 % | 49 s | 15 m | 178 W | 1 h 56 | -131242 |
| TECS_PITCH_MAX 10 | 900 | 7.3 % | 17 s | 23 m | 198 W | 1 h 46 | -134212 |
| TECS_PITCH_MAX 10 | 920 | 4.6 % | 12 s | 15 m | 175 W | 1 h 59 | -134220 |
| TECS_SPDWEIGHT 1.5 | 900 | 5.4 % | 26 s | 15 m | 168 W | 2 h 02 | -134214 |
| TECS_SPDWEIGHT 1.5 | 920 | 10.6 % | 47 s | 11 m | 190 W | 1 h 48 | -134222 |
| **Both** | 900 | **4.4 %** | **12 s** | 15 m | 174 W | **1 h 59** | -134216 |
| **Both** | 920 | **4.4 %** | **12 s** | 15 m | 174 W | **1 h 59** | -134224 |
| AIRSPEED_CRUISE 21 | 900 | 2.9 % | 17 s | 15 m | 206 W | 1 h 43 | -134218 |
| AIRSPEED_CRUISE 21 | 920 | 5.5 % | 46 s | 15 m | 214 W | 1 h 38 | -134226 |

- **Both changes together are the only variant that is consistent:** time near or past CLmax halved
  (8.5-8.8 % -> 4.4 %), longest episode cut about four-fold (46-49 s -> 12 s), at no endurance cost
  (1 h 59 against 1 h 56-1 h 57, same 174 W).
- **TECS_SPDWEIGHT 1.5 alone is erratic** (5.4 % at 900 m, 10.6 % at 920 m, no better than baseline).
- **TECS_PITCH_MAX 10 alone helps** (episodes 12-17 s) but cost 11 min at 900 m.
- **Faster cruise** gives the least time past CLmax at 900 m but costs 14-19 min of endurance and did
  not shorten the worst episode at 920 m.
- **The broken gust model had pointed the other way:** there, TECS_PITCH_MAX 10 looked harmful. That
  conclusion came from the artifact and is withdrawn.

Caveats: two samples per variant against one deterministic turbulence sequence (SITL's rand() is never
seeded), estimated aerodynamics from AVL, still air apart from the modelled wind.

**Conclusion: no change.** "Time past CLmax" is a proxy, and on the fixed gust model it does not
correspond to any harm: the baseline already held height within 11-15 m, had no in-flight ground
contact and no airspeed disable, and lost no endurance. The variants improve the proxy only, and the
pitch cap costs climb rate (900 m in 5.1-6.0 min instead of 4.5-4.8 min). TECS_PITCH_MAX and
TECS_SPDWEIGHT stay at their MFE values. The one risk the proxy might stand for, a wing drop near the
stall in real turbulence with spanwise gust gradients, cannot appear in SITL's uniform-gust model; if
it matters, the lever is speed margin, and the place to judge it is flight test.
