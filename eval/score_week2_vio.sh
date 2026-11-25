#!/usr/bin/env bash
# Week 2 scoring: check every OpenVINS run in OUT, score only the valid ones, summarise them.
#
# A run is valid when: its pose bag opens with `ros2 bag info` and has /ov_msckf/poseimu messages (checked again here,
# not only by run_openvins.sh), neither the recorder nor OpenVINS needed SIGKILL, no OpenVINS process was left over,
# the status file does not say valid=no, and the TUM file exists.
# Invalid runs are listed in OUT/vio_invalid_runs.csv with the reason and are left out of all scores.
#
# Usage: eval/score_week2_vio.sh [OUT]   (default eval/results/vio)
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-eval/results/vio}
GT_DIR=~/ws_deps/src/open_vins/ov_data/tum_vi

set +u; source /opt/ros/jazzy/setup.bash; source ~/ws_deps/install/setup.bash; set -u

seq_args=()
echo "run,reason" > "$OUT/vio_invalid_runs.csv"
for status in "$OUT"/*_run*_run_status.txt; do
  run=$(basename "$status" _run_status.txt)
  seq=${run%_run*}
  reasons=()
  grep -qx 'valid=no' "$status" && reasons+=("run script marked it invalid: $(grep '^reason=' "$status" | cut -d= -f2-)")
  if info=$(ros2 bag info "$OUT/${run}_poseimu_bag" 2>&1); then
    n=$(grep -oP 'Topic: /ov_msckf/poseimu .*Count: \K[0-9]+' <<< "$info" || echo 0)
    [[ $n -gt 0 ]] || reasons+=("pose bag has no /ov_msckf/poseimu messages")
  else
    reasons+=("pose bag does not open with ros2 bag info")
  fi
  for key in recorder_end openvins_end; do
    val=$(grep "^$key=" "$status" | cut -d= -f2- || true)
    [[ -n $val ]] || reasons+=("status file has no $key")
    [[ $val != SIGKILL ]] || reasons+=("$key=SIGKILL")
  done
  left=$(grep '^leftover_openvins_processes=' "$status" | cut -d= -f2- || true)
  [[ ${left:-0} == 0 ]] || reasons+=("$left leftover OpenVINS process(es)")
  [[ -s "$OUT/${run}_openvins.tum" ]] || reasons+=("no TUM file")
  if [[ ${#reasons[@]} -eq 0 ]]; then
    echo "[score] valid:   $run"
    seq_args+=(--seq "$run" "$OUT/${run}_openvins.tum" "$GT_DIR/dataset-${seq}_512_16.txt")
  else
    joined=$(IFS='; '; echo "${reasons[*]}")
    echo "[score] INVALID: $run ($joined)"
    printf '%s,"%s"\n' "$run" "$joined" >> "$OUT/vio_invalid_runs.csv"
  fi
done
[[ ${#seq_args[@]} -gt 0 ]] || { echo "[score] no valid runs"; exit 1; }
env -u PYTHONPATH ~/venvs/trn/bin/python eval/score_vio.py --out "$OUT" "${seq_args[@]}"
/usr/bin/python3 eval/summarize_vio_runs.py "$OUT"
echo "[score] invalid runs: $(($(wc -l < "$OUT/vio_invalid_runs.csv") - 1)) (see $OUT/vio_invalid_runs.csv)"
