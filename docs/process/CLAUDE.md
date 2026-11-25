# trn-belief: terrain-relative navigation with calibrated confidence

## Goal
Build, in simulation and on public recorded data, a navigation system that estimates
position from aerial images plus terrain maps (DEM and orthoimage tiles) and publishes
its position together with an honest uncertainty and a validity state. The system must
refuse to publish a position it cannot back up. This is a portfolio project for an
application to a GPS-denied navigation company. No real drone is involved.

## Environment
- Windows host, WSL2 Ubuntu 24.04 (distro disk on the G: drive).
- ROS 2 Jazzy, PX4 SITL with Gazebo, QGroundControl, OpenVINS, GTSAM, evo.
- Python venv: `~/venvs/trn`. PX4 lives in `~/PX4-Autopilot`. OpenVINS lives in `~/ws_deps`.
  Both stay OUTSIDE this repo.
- Datasets live in `~/data/`. Never commit data.

## Repo layout (this repo root is the colcon workspace)
```
README.md
CLAUDE.md
docs/            plan, log.md, write-up, plots
src/
  trn_msgs/        NavBelief message
  trn_vio/         wrapper around the open VIO system
  trn_matcher/     tile store, matching, absolute fix with diagnostics
  trn_calibration/ covariance model, validity state machine
  trn_fusion/      GTSAM factor graph, belief publisher
  trn_consumer/    planner stub that waits when confidence is low
eval/            metric and degradation-test scripts, results in eval/results/
launch/          replay and SITL launch files
data/README.md   how to download datasets (no data committed)
```

## NavBelief message (trn_msgs/msg/NavBelief.msg)
```
std_msgs/Header header
geometry_msgs/PoseWithCovariance pose
builtin_interfaces/Duration fix_age     # time since the last accepted absolute fix
uint8 validity
uint8 STRONG=0
uint8 AGING=1
uint8 UNCERTAIN=2
uint8 DO_NOT_PUBLISH=3
string reason                           # short human-readable cause of the state
```
Consumers must check `validity` before using `pose`. Weak evidence must never be
published as a confident position.

## Rules for the assistant
1. Never report a metric that was not computed by a script in `eval/`. Save the script,
   the command, and the output file path together.
2. Test splits are whole flights or whole regions, never random frames from one flight.
3. Append every decision, command run, and result to `docs/log.md` with the date.
4. Before any `sudo`, any delete, any change outside this repo, or any download over
   1 GB: show the command and wait for the user to confirm.
5. Never modify Windows files, system settings, or anything under /mnt/c.
6. If a command fails, show the last 30 lines of output and stop. Do not guess fixes
   in a loop. Do not use --force flags or disable checks to make something pass.
7. The user writes the core algorithms (matcher, covariance model, fusion factors).
   The assistant may scaffold, wrap, plot, test, and review, and must explain any
   code the user asks about in plain words.
8. Do not claim real-world or flight-ready results. State plainly that this is
   simulation and public data, and list failure cases.
9. Check dataset licences. UAV-VisLoc and VPAIR are academic use only: no redistribution.

## Conventions
- Python 3.12, type hints, small functions, tests with pytest for anything with logic.
- ROS 2 packages built with `colcon build --symlink-install` from the repo root.
- Frames: ENU for the local map frame, WGS84 for geodetic input, state the frame of
  every published message in its header.
- Commit small and often; messages say what changed and why.