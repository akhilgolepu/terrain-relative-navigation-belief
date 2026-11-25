# Week 1 brief: environment, simulated flight, recorded bag

## Goal
A working toolchain, and one simulated flight recorded as a ROS 2 bag that can be
replayed. Nothing about navigation algorithms yet.

## Context
Read CLAUDE.md first. The environment is WSL2 Ubuntu 24.04. The user is a beginner at
ROS 2, ground control tooling, and VIO, so explain each step briefly as you go.

## Tasks
1. Verify the base system: Ubuntu version, WSL version, free disk space, GPU access for
   Gazebo through WSLg.
2. Install the software listed in the install prompt (ROS 2 Jazzy, PX4 SITL with Gazebo,
   QGroundControl, OpenVINS, Python tools).
3. Create the repo skeleton from CLAUDE.md with empty packages that build.
4. Fly a simulated mission in PX4 SITL with Gazebo and QGroundControl.
5. Record the flight with `ros2 bag record`, then replay it.
6. Write what was done, and what failed, into docs/log.md.

## Acceptance checks (all must be shown with real output)
- [ ] `lsb_release -a` shows Ubuntu 24.04; `wsl -l -v` (run by the user) shows VERSION 2.
- [ ] ROS 2 talker and listener demo: the listener prints the talker's messages.
- [ ] `colcon build --symlink-install` in the repo root finishes with no errors.
- [ ] `make px4_sitl gz_x500` opens Gazebo with a drone and PX4 reports it is ready.
- [ ] QGroundControl shows the same simulated vehicle and a mission flies to the end.
- [ ] A bag in `~/data/bags/week1_flight/` exists, `ros2 bag info` lists its topics and
      duration, and `ros2 bag play` replays it.
- [ ] OpenVINS builds, OR the log records the failure, the last 30 lines of output, and
      a proposed fallback (Ubuntu 22.04 container or a Humble distro) for the user to approve.
- [ ] `evo_traj --help` and `python -c "import gtsam, cv2"` succeed inside `~/venvs/trn`.

## Out of scope
VIO tuning, map tiles, matching, any metrics. Do not start week 2 work.

## Time limit
If any single step takes more than about two hours, stop, log what you tried, and ask.

## Report back (paste into the planning chat)
- The acceptance checklist with each box ticked or not, and the proof for each.
- docs/log.md contents.
- Anything surprising, any workaround used, and any step skipped.
