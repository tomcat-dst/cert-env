#!/usr/bin/env bash
# Run AFTER `sudo ./install-deps.sh`. Builds the parts that were blocked on
# system packages: Gazebo Harmonic (all 16 packages) and the ardupilot_gazebo plugin.
# gz-common5 is rebuilt from clean because its first build silently skipped
# the graphics/av/geospatial components when their libraries were missing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/venv/bin/activate"

cd "$ROOT/src/gz-harmonic"
# Ubuntu's libogre-next 2.3.3 is built in OGRE debug mode; see the patch header.
PATCH="$ROOT/patches/gz-rendering8-ubuntu-ogre-next-debug-abi.patch"
if git -C src/gz-rendering apply --check "$PATCH" 2>/dev/null; then
  git -C src/gz-rendering apply "$PATCH"
fi
rm -rf build log "$ROOT/install/gz"
colcon build --merge-install --install-base "$ROOT/install/gz" \
  --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release \
  2>&1 | tee "$ROOT/logs/gz-colcon-2.log"

set +u  # colcon's setup.bash reads unset variables
source "$ROOT/install/gz/setup.bash"
set -u
cd "$ROOT/src/ardupilot_gazebo"
rm -rf build
cmake -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_PREFIX_PATH="$ROOT/install/gz"
cmake --build build -j"$(nproc)" 2>&1 | tee "$ROOT/logs/apgz-build.log"
