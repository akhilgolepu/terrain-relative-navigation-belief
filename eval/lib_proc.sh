# Start and stop background programs from bash scripts so that signals actually reach them.
# Source this file; used by run_openvins.sh and smoke_test_shutdown.sh.
#
# Why: in a non-interactive bash script, a command started with `&` inherits SIGINT and SIGQUIT as IGNORED
# (/proc/<pid>/status shows SigIgn 0x6), so `kill -INT` does nothing and programs end up SIGKILLed
# (room1_run1, 2026-11-15). start_bg restores the default handling in the child before exec.

# start_bg OUTFILE CMD...  -> starts CMD in the background with SIGINT/SIGQUIT restored; sets BG_PID.
start_bg() {
  local out=$1; shift
  ( trap - INT QUIT; exec "$@" ) > "$out" 2>&1 &
  BG_PID=$!
}

# wait_gone PID SECONDS  -> 0 once PID has exited, 1 if it is still running after SECONDS.
wait_gone() {
  local p=$1 n
  for (( n = 0; n < $2 * 2; n++ )); do kill -0 "$p" 2>/dev/null || return 0; sleep 0.5; done
  kill -0 "$p" 2>/dev/null && return 1 || return 0
}

# stop_proc PID INT_WAIT TERM_WAIT  -> SIGINT and wait INT_WAIT s; only if still running, SIGTERM and wait TERM_WAIT s;
# only if still running, SIGKILL. INT_WAIT=0 skips SIGINT (used to test the SIGTERM fallback).
# Sets STOP_RESULT to one of: "had already exited", "exited after SIGINT", "exited after SIGTERM",
# "SIGKILL" (any SIGKILL makes a run invalid).
stop_proc() {
  local p=$1 int_wait=$2 term_wait=$3
  if ! kill -0 "$p" 2>/dev/null; then STOP_RESULT="had already exited"; return; fi
  if (( int_wait > 0 )); then
    kill -INT "$p" 2>/dev/null
    if wait_gone "$p" "$int_wait"; then STOP_RESULT="exited after SIGINT"; return; fi
  fi
  if (( term_wait > 0 )); then
    kill -TERM "$p" 2>/dev/null
    if wait_gone "$p" "$term_wait"; then STOP_RESULT="exited after SIGTERM"; return; fi
  fi
  kill -KILL "$p" 2>/dev/null
  wait_gone "$p" 5 || true
  STOP_RESULT="SIGKILL"
}

# pose_bag_messages BAG_DIR TOPIC  -> prints the message count if `ros2 bag info` opens the bag, else returns 1.
pose_bag_messages() {
  local info
  info=$(ros2 bag info "$1" 2>&1) || return 1
  grep -oP "Topic: $2 .*Count: \K[0-9]+" <<< "$info" || echo 0
}
