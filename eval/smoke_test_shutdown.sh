#!/usr/bin/env bash
# Smoke test of the OpenVINS run shutdown path (~45 s). Passes only if:
#   A. run_openvins.sh on the first 20 s of a bag: the recorder and OpenVINS both exit after SIGINT (no SIGTERM, no
#      SIGKILL), no OpenVINS process is left over, and the pose bag opens with `ros2 bag info` and has poses;
#   B. SIGTERM fallback: OpenVINS and the recorder started the same way, stopped with SIGTERM only, both exit
#      without SIGKILL and the bag opens.
# Usage: eval/smoke_test_shutdown.sh BAG_DIR WORK_DIR   (WORK_DIR must not exist; outputs are throwaway)
set -euo pipefail
BAG=$1; WORK=$2
[[ -e "$WORK" ]] && { echo "refusing to reuse $WORK"; exit 1; }
mkdir -p "$WORK"
HERE=$(cd "$(dirname "$0")" && pwd)
set +u; source /opt/ros/jazzy/setup.bash; source ~/ws_deps/install/setup.bash; set -u
source "$HERE/lib_proc.sh"
fail=0
check() { if [[ $2 == "$3" ]]; then echo "  PASS $1: $2"; else echo "  FAIL $1: got '$2', want '$3'"; fail=1; fi; }

echo "[smoke] A: run_openvins.sh with SMOKE_PLAY_S=20 (SIGINT path)"
SMOKE_PLAY_S=20 "$HERE/run_openvins.sh" tum_vi smokeA "$BAG" "$WORK" || true
st() { grep "^$1=" "$WORK/smokeA_run_status.txt" | cut -d= -f2-; }
check "recorder" "$(st recorder_end)" "exited after SIGINT"
check "OpenVINS" "$(st openvins_end)" "exited after SIGINT"
check "leftover OpenVINS processes" "$(st leftover_openvins_processes)" "0"
check "valid" "$(st valid)" "yes"
echo "  pose bag messages: $(st pose_bag_messages)"

echo "[smoke] B: SIGTERM fallback (no SIGINT sent)"
start_bg "$WORK/smokeB_openvins.log" ros2 launch ov_msckf subscribe.launch.py config:=tum_vi
launch=$BG_PID
sleep 5
start_bg "$WORK/smokeB_record.log" ros2 bag record -o "$WORK/smokeB_poseimu_bag" --topics /ov_msckf/poseimu
rec=$BG_PID
sleep 3
timeout --signal=INT 10 ros2 bag play "$BAG" > "$WORK/smokeB_play.log" 2>&1 || true
stop_proc "$rec" 0 30;    check "recorder on SIGTERM" "$STOP_RESULT" "exited after SIGTERM"
stop_proc "$launch" 0 15; check "OpenVINS on SIGTERM" "$STOP_RESULT" "exited after SIGTERM"
left=$(pgrep -fc ov_msckf/run_subscribe_msckf || true)
check "leftover OpenVINS processes" "$left" "0"
(( left == 0 )) || for p in $(pgrep -f ov_msckf/run_subscribe_msckf); do stop_proc "$p" 10 10; done
if n=$(pose_bag_messages "$WORK/smokeB_poseimu_bag" /ov_msckf/poseimu); then
  check "SIGTERM-closed bag opens" "yes" "yes"; echo "  pose bag messages: $n"
else
  check "SIGTERM-closed bag opens" "no" "yes"
fi

if (( fail == 0 )); then echo "[smoke] PASSED"; else echo "[smoke] FAILED"; exit 1; fi
