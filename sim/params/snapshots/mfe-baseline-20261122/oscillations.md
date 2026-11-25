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
