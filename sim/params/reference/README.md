# Reference Believer parameter sets (not loaded by anything)

- `Believer_V4.6.3.param`, `Believer_V4.4.4.param`: MakeFlyEasy's stock frame parameters,
  https://fw.makeflyeasy.com/Frame_params/ArduPlane_V4.6.3/ and .../ArduPlane_V4.4.4/
  (linked from github.com/makeflyeasy/MFE_ArduPlane Believer1960/README.md). Fetched 2026-11-22.
  Note: the 4.6.3 file sets AIRSPEED_CRUISE 1900, which is the old TRIM_ARSPD_CM value in cm/s;
  AIRSPEED_CRUISE is in m/s (ArduPlane/Parameters.cpp), so 19 is presumably intended.
- `forum_FlyingSandal_MFE_Believer_20240403.param`: full parameter dump attached to
  https://discuss.ardupilot.org/t/mfe-believer-documenting-setup/115741 (ArduPlane 4.5 dev,
  AUW 3.78 kg, 2x KDE 4014XF, APC 12x12, 6S2P 5000 mAh). The post does not say how the gains
  were obtained.
