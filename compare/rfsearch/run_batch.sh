#!/bin/bash
# Headless RFSEARCH batch: 5 layouts (ellipse plan multi_b/multi/single, QGC route multi_b/multi) x the given seeds,
# all in parallel on SITL instances FIRST..; logs in compare/rfsearch/OUTDIR/<plan>_<scenario>_s<seed>.log.
# usage: compare/rfsearch/run_batch.sh OUTDIR FIRST_INSTANCE PARM_FILE|- SEED...
cd "$(dirname "$0")/../.." && source venv/bin/activate
out=compare/rfsearch/$1 first=$2 parm=$3; shift 3
mkdir -p "$out"
extra=(); [ "$parm" != "-" ] && extra=("$parm")
i=$first
for seed in "$@"; do
  for c in E:tsuniv_rf_ellipse.plan:multi_b E:tsuniv_rf_ellipse.plan:multi E:tsuniv_rf_ellipse.plan:single \
           U:tsuniv_rf_sweep.plan:multi_b U:tsuniv_rf_sweep.plan:multi; do
    IFS=: read p plan sc <<< "$c"
    python compare/mission.py --instance $i --plan sim/missions/$plan \
      --params sim/params/believer_mission_long.parm "${extra[@]}" --rf --rf-scenario $sc --rf-seed $seed \
      --rc-fail-km 0 --mode RFSEARCH --upload --speedup 20 > "$out/${p}_${sc}_s$seed.log" 2>&1 &
    i=$((i + 1)); sleep 3
  done
done
wait
