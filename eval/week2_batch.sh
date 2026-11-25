#!/usr/bin/env bash
# Week 2 batch, meant to run detached so it survives a closed terminal or editor:
#   setsid nohup eval/week2_batch.sh > eval/results/vio/week2_batch.log 2>&1 < /dev/null &
# 1. Writes its PID to eval/results/vio/week2_batch.pid (removed again when it ends).
# 2. Waits until the 1-minute load average stays below 0.7 for a full minute (checked every 10 s);
#    gives up after 30 minutes without starting any run.
# 3. Runs eval/run_week2_vio.sh 3 (3 runs per room, one at a time, stops at the first invalid run, then scores).
# A WSL shutdown still kills it; nothing survives that.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=eval/results/vio
PIDFILE=$OUT/week2_batch.pid
mkdir -p "$OUT"
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

echo "[batch] $(date '+%F %T') pid $$ started; waiting for load1 < 0.7 for 60 s (max 30 min)"
quiet=0
for (( i = 0; i < 180; i++ )); do
  load1=$(cut -d' ' -f1 /proc/loadavg)
  if awk -v l="$load1" 'BEGIN { exit !(l < 0.7) }'; then quiet=$((quiet + 1)); else quiet=0; fi
  (( i % 6 == 0 )) && echo "[batch] $(date '+%T') load1=$load1 quiet_checks=$quiet/6"
  (( quiet >= 6 )) && break
  sleep 10
done
if (( quiet < 6 )); then
  echo "[batch] $(date '+%F %T') machine never quiet within 30 min; NO runs started"
  exit 1
fi
echo "[batch] $(date '+%F %T') quiet (load $(cut -d' ' -f1-3 /proc/loadavg)); starting runs"
eval/run_week2_vio.sh 3
rc=$?
echo "[batch] $(date '+%F %T') finished, run_week2_vio.sh exit code $rc"
exit $rc
