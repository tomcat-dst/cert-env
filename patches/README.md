# Patches

| Directory / file | Applies to | What |
|---|---|---|
| `ardupilot-cert-rfsearch/` | ArduPilot `Plane-4.7.3` (d9c5097c3d), `git am` | the 7 commits of branch `cert-rfsearch`: SITL plane json mass/inertia and electric propulsion, pitot EAS fix, correlated turbulence, json catapult, RFSEARCH flight mode, dBm unit for param metadata |
| `ardupilot-upstream/` | ArduPilot master | the propulsion series prepared for upstream (pushed to the fork's `cert` branch) |
| `ardupilot-sitl-plane-electric-propulsion.patch` | ArduPilot 4.7.3 working tree | earlier single-file version of the SITL changes |
| `qgroundcontrol-rf-overlay/` | QGroundControl 3a67d31, `git am` | RF overlay, `rf` fact group, ArduPlane RFSearch mode name, Plane 4.7 parameter metadata with RFS_ |
| `gz-rendering8-ubuntu-ogre-next-debug-abi.patch` | gz-rendering 8 | build fix for Ubuntu's ogre-next |

The same commits are on public branches:
[tomcat-dst/ardupilot `cert-rfsearch`](https://github.com/tomcat-dst/ardupilot/tree/cert-rfsearch) (ArduPilot) and
[tomcat-dst/qgroundcontrol `rf-scan-overlay`](https://github.com/tomcat-dst/qgroundcontrol/tree/rf-scan-overlay) (QGroundControl).
