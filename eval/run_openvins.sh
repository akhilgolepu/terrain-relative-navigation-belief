#!/usr/bin/env bash
# Run OpenVINS (config shipped in its repo for the given dataset, no parameter changes) on one ROS 2 bag
# and save its pose estimate as a TUM file for eval/score_vio.py.
#
# Usage: eval/run_openvins.sh DATASET SEQ_NAME ROS2_BAG_DIR OUT_DIR
#   DATASET is an OpenVINS config folder name (ov_msckf/config/<DATASET>), e.g. tum_vi or euroc_mav.
#   e.g. eval/run_openvins.sh tum_vi room1 ~/data/tumvi/dataset-room1_512_16_ros2 eval/results/vio
#   SMOKE_PLAY_S=20 plays only the first 20 s (shutdown smoke test; never used for scored runs).
# Writes: OUT_DIR/SEQ_NAME_openvins.tum, OUT_DIR/SEQ_NAME_run_status.txt, OUT_DIR/SEQ_NAME_openvins.log,
#         OUT_DIR/SEQ_NAME_poseimu_bag/ (logs and the pose bag are not committed)
# The status file ends with valid=yes|no and a reason; a run with valid=no has no TUM file and must not be scored.
# A run is invalid if any program needed SIGKILL, an OpenVINS process outlived the launch, or the pose bag
# does not open with `ros2 bag info` (or has no poses). Exit code 3 for an invalid run.
# Needs: ROS 2 Jazzy, ~/ws_deps (OpenVINS) built, ~/venvs/trn (evo). Plays the bag at real-time speed.
set -euo pipefail

[[ $# -eq 4 ]] || { echo "usage: $0 DATASET SEQ_NAME ROS2_BAG_DIR OUT_DIR"; exit 2; }
DATASET=$1; SEQ=$2; BAG=$3; OUT=$4
CONFIG_DIR=~/ws_deps/src/open_vins/config/$DATASET
[[ -f "$CONFIG_DIR/estimator_config.yaml" ]] || { echo "no OpenVINS config at $CONFIG_DIR"; exit 1; }
[[ -d "$BAG" ]] || { echo "bag directory $BAG not found"; exit 1; }
mkdir -p "$OUT"
EST_BAG="$OUT/${SEQ}_poseimu_bag"
LOG="$OUT/${SEQ}_openvins.log"
STATUS="$OUT/${SEQ}_run_status.txt"
[[ -e "$EST_BAG" ]] && { echo "refusing to overwrite $EST_BAG"; exit 1; }
pgrep -f ov_msckf/run_subscribe_msckf > /dev/null && { echo "an OpenVINS process is already running; stop it first"; exit 1; }

set +u
source /opt/ros/jazzy/setup.bash
source ~/ws_deps/install/setup.bash
set -u
source "$(dirname "$0")/lib_proc.sh"

launch_pid=""; rec_pid=""; recorder_end="not started"; openvins_end="not started"; orphans=0

# Shutdown order: the recorder first (SIGINT, 60 s to close its bag; SIGTERM only if SIGINT fails), so a stuck
# OpenVINS can never cost the recorded poses; then OpenVINS (SIGINT 15 s, SIGTERM 15 s); SIGKILL only as a last resort.
finish() {
  if [[ -n $rec_pid ]]; then stop_proc "$rec_pid" 60 30; recorder_end=$STOP_RESULT; rec_pid=""; fi
  if [[ -n $launch_pid ]]; then stop_proc "$launch_pid" 15 15; openvins_end=$STOP_RESULT; launch_pid=""; fi
  orphans=$(pgrep -fc ov_msckf/run_subscribe_msckf || true)
  if (( orphans > 0 )); then
    for p in $(pgrep -f ov_msckf/run_subscribe_msckf); do stop_proc "$p" 10 10; done
  fi
  echo "[run] recorder: $recorder_end | OpenVINS: $openvins_end | leftover OpenVINS processes: $orphans"
}
trap finish EXIT

echo "[run] OpenVINS subscribe.launch.py config:=$DATASET (other launch defaults) -> $LOG"
start_bg "$LOG" ros2 launch ov_msckf subscribe.launch.py config:="$DATASET"
launch_pid=$BG_PID
sleep 5

echo "[run] recording /ov_msckf/poseimu -> $EST_BAG"
start_bg "$OUT/${SEQ}_record.log" ros2 bag record -o "$EST_BAG" --topics /ov_msckf/poseimu
rec_pid=$BG_PID
sleep 3

# `ros2 bag play` once failed to exit after the bag ended (2026-11-14, cause not found), so it runs under
# a timeout of bag duration + 30 s. Whether it exited by itself or was cut off is written to the status file.
BAG_S=$(/usr/bin/python3 -c "import sys, yaml; print(yaml.safe_load(open(sys.argv[1]))['rosbag2_bagfile_information']['duration']['nanoseconds'] / 1e9)" "$BAG/metadata.yaml")
LIMIT_S=${SMOKE_PLAY_S:-$(/usr/bin/python3 -c "import math, sys; print(math.ceil(float(sys.argv[1])) + 30)" "$BAG_S")}
echo "[run] playing $BAG at 1x (bag ${BAG_S} s, limit ${LIMIT_S} s${SMOKE_PLAY_S:+, SMOKE TEST})"
t0=$(date +%s.%N)
play_rc=0
timeout --signal=INT --kill-after=10 "$LIMIT_S" ros2 bag play "$BAG" > "$OUT/${SEQ}_play.log" 2>&1 || play_rc=$?
play_s=$(/usr/bin/python3 -c "import sys; print(round(float(sys.argv[2]) - float(sys.argv[1]), 1))" "$t0" "$(date +%s.%N)")
if [[ $play_rc -eq 0 ]]; then play_end="exited by itself"
elif [[ -n ${SMOKE_PLAY_S:-} && $play_rc -eq 124 ]]; then play_end="stopped at smoke-test limit (expected)"
else play_end="cut off by timeout or failed (exit $play_rc)"; fi
echo "[run] ros2 bag play: $play_end after ${play_s} s"
sleep 3

finish
trap - EXIT

valid=yes; reasons=()
[[ $recorder_end == SIGKILL ]] && reasons+=("recorder needed SIGKILL")
[[ $openvins_end == SIGKILL ]] && reasons+=("OpenVINS needed SIGKILL")
(( orphans > 0 )) && reasons+=("$orphans OpenVINS process(es) outlived the launch")
if pose_messages=$(pose_bag_messages "$EST_BAG" /ov_msckf/poseimu); then
  (( pose_messages > 0 )) || reasons+=("pose bag has no /ov_msckf/poseimu messages")
else
  pose_messages=0; reasons+=("pose bag does not open with ros2 bag info")
fi
(( ${#reasons[@]} == 0 )) || valid=no
reason=$(IFS='; '; echo "${reasons[*]:-}")

if [[ $valid == yes ]]; then
  echo "[run] converting to TUM"
  ( cd "$OUT" && ~/venvs/trn/bin/evo_traj bag2 "${SEQ}_poseimu_bag" /ov_msckf/poseimu --save_as_tum > /dev/null )
  mv "$OUT/ov_msckf_poseimu.tum" "$OUT/${SEQ}_openvins.tum"
fi

printf '%s\n' "dataset=$DATASET" "sequence=$SEQ" "bag=$BAG" "bag_duration_s=$BAG_S" "play_limit_s=$LIMIT_S" \
  "play_wall_s=$play_s" "play_exit_code=$play_rc" "play_end=$play_end" "recorder_end=$recorder_end" \
  "openvins_end=$openvins_end" "leftover_openvins_processes=$orphans" "pose_bag_messages=$pose_messages" \
  "valid=$valid" "reason=$reason" > "$STATUS"

if [[ $valid == yes ]]; then
  echo "[run] done: $OUT/${SEQ}_openvins.tum ($(wc -l < "$OUT/${SEQ}_openvins.tum") poses)"
else
  echo "[run] INVALID run $SEQ: $reason (no TUM file written)"
  exit 3
fi
