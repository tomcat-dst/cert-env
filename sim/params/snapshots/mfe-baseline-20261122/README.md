# Snapshot: MFE stock gains baseline, 2026-11-22

State before running AUTOTUNE. Restoring it means using these files as the parameter layers
(src/ardupilot/Tools/autotest/models/plane.parm, then believer*.parm, then believer_mfe.parm) with
the *_avl_mfe.json models, on ArduPlane 4.7.3 + the patch in this folder (includes the SITL pitot fix).

Results with this state (Tsuniv home, 300 m above it, 19 m/s, still air), see oscillations.md:
- compare/results/endurance-20261122-185515/believer-5kg-avl-mfe  base, endurance, 2 h 07 min corrected
- compare/results/endurance-20261122-185517/believer-avl-mfe      Starlink, endurance, 1 h 58 min corrected
- compare/results/endurance-20261122-185519/believer-5kg-avl-mfe  base, 10 min
- compare/results/endurance-20261122-185521/believer-avl-mfe      Starlink, 10 min
