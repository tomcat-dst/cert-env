SITL: plane json models with mass, inertia and electric propulsion

## Summary

The SITL plane model (`libraries/SITL/SIM_Plane.cpp`) can load aerodynamic
coefficients from a json file, but three things cannot be configured:

- **Mass** is fixed at 2 kg.
- **Inertia** does not exist: aerodynamic torque is used directly as angular
  acceleration.
- **Thrust** is linear in throttle and independent of airspeed (full throttle =
  weight / 0.7), and battery current is a fixed `50 A * throttle^2`.

For an electric aircraft this is far from reality. For a 5 kg, 1.96 m twin-motor
airframe (2x 585 KV motor, APC 11x7E, 6S Li-ion) flown in SITL, the stock model
gave 7.8% cruise throttle at 20 m/s, a 21 m/s climb and 52 m/s airspeed on takeoff.

This series adds optional json keys. Models that do not use them behave exactly
as before.

1. `SITL: allow plane json models to set mass and inertia`
   - `mass` (kg), `inertia` ([Ixx, Iyy, Izz] kg m^2; divides the body torques)
2. `SITL: add optional electric propulsion model to plane`
   - `num_motors`, `motor_kv`, `motor_R`, `motor_I0`, `esc_eff`, `prop_diameter`,
     `prop_ct`, `prop_cp` (quadratics in advance ratio J), `prop_J_max`, `batt_R`
   - Each step the motor speed is the balance of motor and propeller torque
     (bisection); thrust is `Ct * rho * n^2 * D^4` per motor. The bus voltage is
     the existing SITL battery model's voltage; the computed current is fed back
     to it in `update_battery()`, replacing `50 A * throttle^2` for these models.
   - For these models the battery is re-initialised when `SIM_BATT_VOLTAGE`
     changes. On master its full voltage is fixed in the constructor, before
     parameter files load, and `maybe_reset()` caps later values at it: a model
     with `SIM_BATT_VOLTAGE 25.2` in its parameter file ran at 12.6 V and could
     not take off. The stock model is not changed here; reviewers may want the
     same treatment for every plane.

## Testing

Built with `./waf configure --board sitl && ./waf plane` on master 5a89ce5d6d plus
these two commits; no warnings in `SIM_Plane.cpp`. Flown with a scripted profile
(AUTO takeoff to 120 m -> 60 s loiter -> power-off glide, SPEEDUP 5):

- **Stock `plane`, master without vs with the patch:** identical metrics (takeoff
  21.8 s, climb 11.0 m/s, loiter 22.0 m/s at 45% throttle, 36.3 deg bank, glide
  ratio 3.1).
- **5 kg electric model** (2x 585 KV, 43.5 mOhm, APC 11x7E fitted to APC's
  PER3 data, 6S at 25.2 V), 29.5 deg bank loiter at 20 m/s, from the dataflash log:
  48.9% throttle, 7.8 A at 24.8 V (195 W). A hand calculation from the same motor
  and propeller data gives 193 W. Climb 11.2 m/s, takeoff peak 33 m/s at 86 A.
  With the stock thrust model the same airframe cruised at 7.8% throttle and
  climbed at 21 m/s.
- **Not run:** the autotest suite.

## Notes

- No parameters are added; everything is in the model json.
- An example model json can be added under `Tools/autotest/models/` if reviewers
  want one in-tree.
- AI-assisted: the change was written with Claude (Anthropic); the submitter is
  responsible for it and has reviewed and tested it as described above.
