#!/usr/bin/env bash
# Week 2: run OpenVINS (shipped tum_vi config, unmodified) RUNS times on TUM VI room1 and room2, one run at a time,
# then check every run, score the valid ones and summarise mean/spread per sequence (eval/score_week2_vio.sh).
#
# Usage (fresh shell, from the repo root):  eval/run_week2_vio.sh [RUNS]   (default 3)
# Needs: ~/data/tumvi/dataset-room{1,2}_512_16_ros2 (see data/README.md), ~/ws_deps built, ~/venvs/trn.
# Output: eval/results/vio/ (vio_scores.csv, vio_runs_summary.csv, vio_run_health.csv, vio_invalid_runs.csv,
#         plots, per-run TUM files and status files).
# Plays each bag at real-time speed (~2.5 min per run). Close heavy programs first: lag would distort the results.
set -euo pipefail
cd "$(dirname "$0")/.."
RUNS=${1:-3}
OUT=eval/results/vio
mkdir -p "$OUT"
for seq in room1 room2; do
  for i in $(seq 1 "$RUNS"); do
    run="${seq}_run${i}"
    echo "[week2] $(date '+%F %T') start $run | load: $(cut -d' ' -f1-3 /proc/loadavg)"
    eval/run_openvins.sh tum_vi "$run" ~/data/tumvi/dataset-${seq}_512_16_ros2 "$OUT"
  done
done
echo "[week2] $(date '+%F %T') checking and scoring"
eval/score_week2_vio.sh "$OUT"
echo "[week2] $(date '+%F %T') done"
