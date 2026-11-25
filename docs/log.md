# Project log

## 2026-10-27 — Week 1: environment install

### Base system check (WEEK1_BRIEF task 1)
Commands: `lsb_release -a`, `uname -r`, `df -h`, `free -h`, `nproc`, `ls /mnt/wslg /dev/dxg /usr/lib/wsl/lib`, `dpkg-query`.

| Check | Result |
|---|---|
| Ubuntu | 24.04.5 LTS (noble) |
| Kernel | 6.6.87.2-microsoft-standard-WSL2 |
| Disk free on `/` | 872 GB of 1007 GB |
| RAM / swap / CPUs | 19 GiB / 24 GiB / 16 |
| GPU passthrough | `/dev/dxg` present; `/usr/lib/wsl/lib` has NVIDIA `libcuda`, `libd3d12` |
| WSLg | **NOT running**: `/mnt/wslg` has only `run/`, no `.X11-unix`, no Wayland socket; `/tmp/.X11-unix` empty; `DISPLAY` and `WAYLAND_DISPLAY` unset. Blocks Gazebo/QGC GUIs. |
| systemd | off (PID 1 is WSL `init`) |
| Python | `python3` resolves to Miniconda 3.13.12 (conda `base` auto-activates in `~/.bashrc`). System `/usr/bin/python3` is 3.12.3. |
| Pre-installed | git, curl, wget, build-essential, cmake 3.28.3; `ros-jazzy-desktop` 0.11.0 (294 ros-jazzy pkgs, apt history shows `apt install ros-jazzy-desktop` done earlier); ROS apt source `/etc/apt/sources.list.d/ros2.sources` present |
| Missing | python3-pip, python3-venv, ros-dev-tools |

Risk noted: conda's Python on PATH conflicts with ROS 2 Jazzy (built for system Python 3.12) and with colcon builds.

### Step 1 + 2: base tools and ROS 2 dev tools
Docs checked: https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html (2026-10-27).
- `grep Suites /etc/apt/sources.list.d/ubuntu.sources` → `noble noble-updates noble-backports` (docs warning about missing suites does not apply).
- `apt-get -s install python3-pip python3-venv ros-dev-tools` → 72 packages, no conflicts (simulation only).
- Decision (user): disable conda base auto-activate so ROS shells use system Python 3.12.
  `conda config --set auto_activate_base false` → `~/.condarc` now `auto_activate: false`.
- `~/.bashrc` backed up to `~/.bashrc.bak-2026-10-27`; appended `source /opt/ros/jazzy/setup.bash`.
- Fresh-shell check (`env -i ... bash -ic`): `python3` → `/usr/bin/python3` 3.12.3, `ROS_DISTRO=jazzy`, no conda env.
- `ros-jazzy-desktop` was already installed; not reinstalled.
- Talker/listener test (ran both for ~8 s in clean shells):
  ```
  [talker]: Publishing: 'Hello World: 6'
  [listener]: I heard: [Hello World: 6]
  ```
  PASS: Python listener receives C++ talker messages.
- Pending: user to run `sudo apt update && sudo apt install -y python3-pip python3-venv ros-dev-tools`.
- Pending: WSLg not running; user asked to check `wsl --version` and `%USERPROFILE%\.wslconfig` (guiApplications).
- User ran the apt install. Verified with `dpkg-query`: python3-pip 24.0, python3-venv 3.12.3, ros-dev-tools 1.0.3, python3-colcon-common-extensions 0.3.0, python3-rosdep 0.27.0 all `install ok installed`. Steps 1 and 2 DONE.

### WSLg diagnosis
User output from PowerShell: `wsl --version` → WSL 2.6.3.0, kernel 6.6.87.2-1, WSLg 1.0.71.
`.wslconfig` contains `guiApplications=false`, which is the cause of WSLg not running.
Fix (user, on Windows): change it to `guiApplications=true`, then `wsl --shutdown`. The assistant does not edit Windows files.

### Step 3 prep: PX4 SITL + Gazebo
Docs checked (2026-10-27): https://docs.px4.io/main/en/dev_setup/dev_env_linux_ubuntu.html, https://docs.px4.io/main/en/sim_gazebo_gz/index.html
- Docs: `git clone https://github.com/PX4/PX4-Autopilot.git --recursive`, then `bash ./PX4-Autopilot/Tools/setup/ubuntu.sh` (options `--no-nuttx`, `--no-sim-tools`), then restart.
  Gazebo Harmonic/Ionic/Jetty supported on 24.04. Docs warn the script targets clean installs (ROS already present here).
- Size estimate via GitHub API: main repo 581 MB + 35 top-level submodules ~859 MB → clone ≈ 1.4 GB+ (nested submodules extra).
  ubuntu.sh additionally downloads Gazebo + Python deps (and the NuttX ARM toolchain unless `--no-nuttx`). Over 1 GB → asked user.
- ubuntu.sh runs sudo internally → user must run it.
- User approved PX4 download, chose `ubuntu.sh --no-nuttx` (no real hardware; NuttX toolchain not needed).
- Started `git clone https://github.com/PX4/PX4-Autopilot.git --recursive` in `~` (background).

### Step 6: Python tools (done while PX4 clones)
- `/usr/bin/python3 -m venv ~/venvs/trn` (Python 3.12.3, system, not conda); `pip install --upgrade pip` → 26.2.2.
- `~/venvs/trn/bin/pip install numpy scipy matplotlib opencv-python evo gtsam` → EXIT 0.
  Versions: numpy 2.5.4, scipy 1.18.1, matplotlib 3.11.2, opencv-python 5.0.0.93, evo 1.38.1, gtsam 4.3.0.
- Acceptance check in clean shell with venv activated:
  `python -c "import gtsam, cv2"` → IMPORT_OK; `gtsam.Pose3()` rotation det = 1.0; `evo_traj --help` → exit 0, shows `usage: evo_traj [-h] {kitti,tum,euroc,bag,bag2,mcap}`.
  PASS. (evo created `~/.evo/settings.json` on first run.)

### Step 4 prep: QGroundControl
Docs checked (2026-10-27): https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html
- Note: master docs link to the **daily build** AppImage (stable v5.1 docs exist separately). Used the daily build per the given URL.
- Docs library command: `sudo apt install -y libfuse2 libxcb-xinerama0 libxkbcommon-x11-0 libxcb-cursor0`.
  `apt-get -s` shows on 24.04 it resolves `libfuse2` → `libfuse2t64`; only libfuse2t64 and libxcb-cursor0 are new. Command works unchanged.
- Skipped (docs pre-steps for USB serial hardware, not needed for SITL in WSL): `usermod -aG dialout`, masking ModemManager
  (also `systemctl` unusable, systemd is off). modemmanager package is installed but not running as a service.
- Downloaded (203 MB, under 1 GB limit) via python urllib to `~/tools/QGroundControl-x86_64.AppImage`, `chmod +x`.
  sha256 `18adfc84653d85b269ee9d0754f9ca35693bbaccd175e6e79cde32777834f20c`, ELF 64-bit x86-64. Build dated 2026-10-27 02:46 GMT.
- Pending: user runs the library apt command; GUI test needs WSLg (after `.wslconfig` fix + `wsl --shutdown`).

### Step 3: PX4 clone
- `git clone https://github.com/PX4/PX4-Autopilot.git --recursive` in `~` → EXIT 0, 0 fatal/error lines, 45 submodules all checked out, 2.9 GB.
  HEAD `77aaa2f6da` (2026-10-27), `git describe` = `v1.18.0-beta1-1297-g77aaa2f6da` (main branch, pre-release).
- Read `Tools/setup/ubuntu.sh` (257 lines) before handing to user:
  - apt base deps; pip installs `Tools/setup/requirements.txt` with `python3 -m pip install --break-system-packages` (upstream script behaviour, python >= 3.11).
    Runs as non-root so pip falls back to `~/.local` (currently empty). Requirements (numpy>=1.13, empy>=3.3,<4, ...) are already satisfied
    by apt numpy 1.26.4 / empy 3.3.4, so these should not be upgraded. New packages (pymavlink, pyulog, matplotlib, pandas, ...) go to `~/.local`.
    Risk: `~/.local` packages shadow apt Python packages for ROS. Will re-check ROS demo + numpy version afterwards.
  - Adds OSRF apt repo `/etc/apt/sources.list.d/gazebo-stable.list` + key, installs `gz-harmonic libunwind-dev cppzmq-dev` (24.04).
  - NuttX block (incl. `usermod -aG dialout`) skipped by `--no-nuttx`.
  - Must run in a shell where `python3` is `/usr/bin/python3` (not conda), otherwise PX4 deps go into conda.

## 2026-10-31 — after user ran ubuntu.sh and restarted WSL

### State check
- WSL restarted (uptime since 2026-10-31 05:11). **WSLg still not running**: `/mnt/wslg` has only `run/`, `/tmp/.X11-unix` empty, DISPLAY/WAYLAND_DISPLAY unset.
- apt history shows ubuntu.sh's two apt-get installs ran (base deps; `gz-harmonic libunwind-dev cppzmq-dev gstreamer... libopencv-dev ...`).
  `/etc/apt/sources.list.d/gazebo-stable.list` added. `gz-harmonic 1.0.0-1~noble` installed; `gz sim --versions` → 8.15.0.
- QGC libs installed: libfuse2t64 2.9.9, libxcb-cursor0 0.1.4.
- `python3` on PATH → `/usr/bin/python3`, no conda env (conda change working).

### FAILURE: PX4 pip step shadowed system numpy
- `pip list --user` (63 entries in `~/.local/lib/python3.12/site-packages`) includes numpy 2.5.4, pandas 3.1.0, pymavlink 2.4.50, pyulog 1.3.0, mavsdk 4.0.6, ...
- Cause: PX4 `requirements.txt` lists `pandas>=0.21`; pip chose pandas 3.1.0 which has `Requires-Dist: numpy>=2.0.2`, so pip installed numpy 2.5.4 into `~/.local`.
  This overrides apt numpy 1.26.4 for every system-Python program, including ROS 2. My earlier log note ("these should not be upgraded") was wrong.
- Import test in a clean shell (system python3, ROS sourced):
  ```
  numpy                          OK /home/akhil/.local/lib/python3.12/site-packages/numpy/__init__.py
  cv2                            ImportError: numpy.core.multiarray failed to import
  cv_bridge                      OK (import), but CvBridge() → ImportError: numpy.core.multiarray failed to import
  scipy                          OK /usr/lib/python3/dist-packages/scipy/__init__.py
  matplotlib.pyplot              ImportError: numpy.core.multiarray failed to import
  sensor_msgs_py.point_cloud2    OK
  rclpy                          OK
  ```
  Effect: ROS image conversion (cv_bridge), apt OpenCV Python, and apt matplotlib (rqt_plot) are broken in system Python.
  `~/venvs/trn` is not affected (own numpy 2.5.4 + opencv-python built for it).
- Stopped. Proposed fix given to user; not applied.
- Decision (user): remove numpy+pandas from `~/.local`, install apt `python3-pandas` (2.1.4, built for numpy 1.26).
  Checked first: PX4 uses pandas only in test/plot scripts (ekf2 sensor_simulator, tflite tools), not in the SITL build.
- Ran `/usr/bin/python3 -m pip uninstall -y --break-system-packages numpy pandas` (pip on 24.04 needs the flag even to uninstall user-site packages;
  used only to revert what ubuntu.sh installed). → numpy-2.5.4 and pandas-3.1.0 uninstalled.
- Re-test in clean shell: numpy 1.26.4 (apt), cv2 4.6.0 OK, matplotlib.pyplot OK, scipy 1.11.4 OK, pymavlink 2.4.50 OK, pyulog OK, rclpy OK,
  `CvBridge` roundtrip shape (4, 4, 3) OK. `~/venvs/trn` unaffected (numpy 2.5.4, gtsam, cv2 import OK). FIXED.
- Pending (user): `sudo apt install -y python3-pandas`; edit `.wslconfig` `guiApplications=true` then `wsl --shutdown`.
- Note for later: re-running ubuntu.sh (or `pip install -r requirements.txt`) would bring numpy 2 back.

## 2026-10-31 — after .wslconfig fix and second `wsl --shutdown`
- Uptime since 05:55. WSLg UP: `DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0`, `XDG_RUNTIME_DIR=/mnt/wslg/runtime-dir`, `/tmp/.X11-unix/X0` socket, weston.log present.
- `python3-pandas` not yet installed (user pending; not needed for SITL build). System numpy still 1.26.4.

### Step 3: PX4 SITL build
- `make px4_sitl` (in `~/PX4-Autopilot`) → **FAILED** at CMake configure after 2 s, EXIT 2. Last lines:
  ```
  -- Found Python3: /home/akhil/.local/bin/python3.11 (found version "3.11.15") found components: Interpreter
  -- PX4 config file: /home/akhil/PX4-Autopilot/boards/px4/sitl/default.px4board
  ModuleNotFoundError: No module named 'menuconfig'
  CMake Error at cmake/kconfig.cmake:13 (message):
    kconfiglib is not installed or not in PATH
  -- Configuring incomplete, errors occurred!
  make: *** [Makefile:250: px4_sitl] Error 1
  ```
- Diagnosis (read-only): `~/.local/bin/python3.11` is a symlink created by **uv** (2026-07-29) to
  `~/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3.11`. `~/.local/bin` is first on PATH, and CMake's FindPython3
  (`Python3_FIND_STRATEGY LOCATION`) picks it. PX4 pip deps (kconfiglib etc.) are installed for 3.12 in `~/.local/lib/python3.12`, so 3.11 can't see them.
  `/usr/bin/python3 -c "import kconfiglib, menuconfig"` works.
- PX4 Makefile (lines 166-174) supports `PYTHON_EXECUTABLE=...` → passed to CMake ("Pick up specific Python path if set").
  Proposed fix: `make px4_sitl gz_x500 PYTHON_EXECUTABLE=/usr/bin/python3`. Not applied; asked user.
- Also noted: WSL PATH includes Windows dirs (`/mnt/c/...`, `/mnt/g/miniconda/...`) via appendWindowsPath. Not changed.

### Step 5 prep: OpenVINS
- `git clone https://github.com/rpng/open_vins/` into `~/ws_deps/src` → HEAD `6948812` (2025-11-30, "Merge pull request #530 from rpng/android"), 567 MB.
  Dockerfiles only up to `Dockerfile_ros2_22_04` (as the user warned).
- Docs (https://docs.openvins.com/gs-installing.html): ROS 2 build = `colcon build --event-handlers console_cohesion+ --packages-select ov_core ov_init ov_msckf ov_eval`;
  deps OpenCV (contrib for aruco), Eigen3, Ceres (`sudo apt-get install libceres-dev` first, source build only if that fails).
- package.xml deps include libceres-dev, libopencv-contrib-dev, cv_bridge, image_transport, tf2_geometry_msgs.
  Installed: Eigen 3.4.0, OpenCV 4.6.0 dev, Boost 1.83. Missing: libceres-dev (and contrib check below).
- Check: libopencv-contrib-dev 4.6.0, ros-jazzy-cv-bridge, image-transport, tf2-geometry-msgs installed. Only libceres-dev missing; `apt-get -s install libceres-dev` → 25 packages, no errors.
- Decision (user): pin Python per build with `PYTHON_EXECUTABLE=/usr/bin/python3` (uv shim left untouched). Every PX4 make command needs it.
- `make px4_sitl PYTHON_EXECUTABLE=/usr/bin/python3` → EXIT 0, `[1200/1200]` targets, 0 `error:`/`FAILED:` lines, real 1m15s.
  `build/px4_sitl_default/bin/px4` built (59 MB). CMakeCache: `PYTHON_EXECUTABLE:FILEPATH=/usr/bin/python3` (kconfig.cmake uses this).
  The configure log still prints "Found Python3: ~/.local/bin/python3.11" (discovery only; build steps use PYTHON_EXECUTABLE).
- Launched `make px4_sitl gz_x500 PYTHON_EXECUTABLE=/usr/bin/python3` (background, stdin held open with `tail -f /dev/null |`). Log lines:
  ```
  INFO  [init] Gazebo simulator 8.15.0
  INFO  [init] Starting gazebo with world: .../Tools/simulation/gz/worlds/default.sdf
  INFO  [init] Starting gz gui
  INFO  [init] Gazebo world is ready
  INFO  [init] Spawning Gazebo model
  INFO  [gz_bridge] world: default, model: x500_0
  INFO  [gz_bridge] Subscribed to IMU[0..2], Magnetometer[0..1], GPS[0..1], Barometer[0..1]
  INFO  [px4] Startup script returned successfully
  pxh> INFO  [tone_alarm] home set
  WARN  [health_and_arming_checks] Preflight Fail: No connection to the GCS
  ```
  No "Ready for takeoff" yet: this PX4 version blocks arming until a GCS connects (expected; QGC is next).
  Processes: `bin/px4`, `gz sim -s` (server), `gz sim -g` (GUI, ~220% CPU).
- Rendering: GUI maps `libgallium-25.2.8` (Mesa) but not `/usr/lib/wsl/lib/libd3d12.so` → most likely software rendering (llvmpipe), not GPU.
  Works, but slow. Not changed. (`glxinfo -B` from `mesa-utils` would confirm; not installed.)

### Step 4: QGroundControl test
- `/dev/fuse` present (AppImage needs FUSE). Before QGC: PX4 listening on UDP 18570/14580, GCS port 14550 free.
- Launched `~/tools/QGroundControl-x86_64.AppImage` (background) with SITL running. QGC bound UDP 0.0.0.0:14550.
- PX4 log right after:
  ```
  INFO  [mavlink] partner IP: 127.0.0.1
  INFO  [commander] Ready for takeoff!
  ```
- `build/px4_sitl_default/bin/px4-listener vehicle_status -n 1` → `gcs_connection_lost: False`, `pre_flight_checks_pass: True`, `arming_state: 1` (disarmed), `nav_state: 4`.
  PASS: QGC connects to the running simulation.
- QGC stderr: `libEGL warning: failed to get driver name`, `MESA: error: ZINK: failed to choose pdev`, `egl: failed to create dri2 screen`
  (falls back to software GL, same as Gazebo), and no text-to-speech engine (`speechd` plug-in missing). Neither blocks use.
- `make px4_sitl gz_x500` acceptance: Gazebo opened with the x500 and PX4 reported "Ready for takeoff!" (after GCS connected).
- Stopped QGC and PX4 tasks; leftover `gz sim -s`/`gz sim -g` (orphaned after PX4 stop) sent SIGTERM → stopped.

### Step 5: OpenVINS build
- User installed `libceres-dev 2.2.0+dfsg-4.1ubuntu2` and `python3-pandas 2.1.4+dfsg-7`. System numpy still 1.26.4; pandas from `/usr/lib/python3/dist-packages`.
- Build command (docs, ROS 2): `colcon build --event-handlers console_cohesion+ --packages-select ov_core ov_init ov_msckf ov_eval`
  in `~/ws_deps`, ROS Jazzy sourced, `MAKEFLAGS=-j8` (limit RAM use; 13 GiB free). Time-box: ~2 h. Started 2026-10-31 07:32.
- Build → **FAILED** after 7 s (colcon exit 1; ov_core failed at CMake configure, 3 packages not processed). Last 30 lines of the log:
  ```
  
  Traceback (most recent call last):
    File "/opt/ros/jazzy/share/ament_cmake_core/cmake/core/package_xml_2_cmake.py", line 22, in <module>
      from catkin_pkg.package import parse_package_string
  ModuleNotFoundError: No module named 'catkin_pkg'
  CMake Error at /opt/ros/jazzy/share/ament_cmake_core/cmake/core/ament_package_xml.cmake:95 (message):
    execute_process(/home/akhil/.local/bin/python3.11
    /opt/ros/jazzy/share/ament_cmake_core/cmake/core/package_xml_2_cmake.py
    /home/akhil/ws_deps/src/open_vins/ov_core/package.xml
    /home/akhil/ws_deps/build/ov_core/ament_cmake_core/package.cmake) returned
    error code 1
  Call Stack (most recent call first):
    /opt/ros/jazzy/share/ament_cmake_core/cmake/core/ament_package_xml.cmake:49 (_ament_package_xml)
    /opt/ros/jazzy/share/ament_cmake_core/cmake/core/ament_package.cmake:63 (ament_package_xml)
    cmake/ROS2.cmake:86 (ament_package)
    CMakeLists.txt:62 (include)
  
  
  ---
  Failed   <<< ov_core [7.02s, exited with code 1]
  
  Summary: 0 packages finished [7.24s]
    1 package failed: ov_core
    1 package had stderr output: ov_core
    3 packages not processed
  
  real	0m7.585s
  user	0m0.984s
  sys	0m0.646s
  EXIT=1
  ```
- Earlier in the log (configure got this far): `Found OpenCV 4.6.0`, `Found Boost 1.83.0`, `ROS *2* version found`, `Found rclcpp 28.1.22`, `Found cv_bridge 4.1.0`,
  then `Found Python3: /home/akhil/.local/bin/python3.11 (3.11.15)` → `package_xml_2_cmake.py` → `ModuleNotFoundError: No module named 'catkin_pkg'`
  at `/opt/ros/jazzy/share/ament_cmake_core/cmake/core/ament_package_xml.cmake:95`.
- Diagnosis: same root cause as the first PX4 failure. ament_cmake's FindPython3 picks uv's `~/.local/bin/python3.11` (first on PATH);
  ROS's Python modules (catkin_pkg, ...) exist only for system Python 3.12. This is NOT an OpenVINS/Ubuntu-24.04 incompatibility
  (C++ compile not reached yet). Time used of the 2 h box: ~10 min.
- Proposed (not applied, per user rule): retry with `--cmake-args -DPython3_EXECUTABLE=/usr/bin/python3`;
  if the real C++ compile then fails, fall back to an Ubuntu 22.04 + ROS 2 Humble container (`Dockerfile_ros2_22_04`). Asked user.
- Note: the same issue will hit `colcon build` in this repo (trn-belief) for every ament package.
- Decision (user): set a colcon default for all builds. Created `~/.colcon/defaults.yaml`:
  `build: cmake-args: [-DPython3_EXECUTABLE=/usr/bin/python3]`. Retrying the same docs command (MAKEFLAGS=-j8). Started 2026-10-31.
- Retry → configure OK (`Found Python3: /usr/bin/python3 (3.12.3)`). Result: ov_core OK (1m6s), ov_init OK (1m41s), ov_eval OK (24s),
  **ov_msckf FAILED** (exit 2), colcon exit 2, total 3m59s. 2 `error:` lines (same error twice), 34 warnings. Last 30 lines of the log:
  ```
  CMake Deprecation Warning at cmake/ROS2.cmake:1 (cmake_minimum_required):
    Compatibility with CMake < 3.5 will be removed from a future version of
    CMake.
  
    Update the VERSION argument <min> value or use a ...<max> suffix to tell
    CMake that the project does not need compatibility with older versions.
  Call Stack (most recent call first):
    CMakeLists.txt:49 (include)
  
  
  In file included from /home/akhil/ws_deps/src/open_vins/ov_msckf/src/ros/ROS2Visualizer.cpp:22:
  /home/akhil/ws_deps/src/open_vins/ov_msckf/src/ros/ROS2Visualizer.h:28:10: fatal error: image_transport/image_transport.h: No such file or directory
     28 | #include <image_transport/image_transport.h>
        |          ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  compilation terminated.
  gmake[2]: *** [CMakeFiles/ov_msckf_lib.dir/build.make:230: CMakeFiles/ov_msckf_lib.dir/src/ros/ROS2Visualizer.cpp.o] Error 1
  gmake[2]: *** Waiting for unfinished jobs....
  gmake[1]: *** [CMakeFiles/Makefile2:145: CMakeFiles/ov_msckf_lib.dir/all] Error 2
  gmake: *** [Makefile:146: all] Error 2
  ---
  Failed   <<< ov_msckf [1min 12s, exited with code 2]
  
  Summary: 3 packages finished [3min 59s]
    1 package failed: ov_msckf
    4 packages had stderr output: ov_core ov_eval ov_init ov_msckf
  
  real	3m59.654s
  user	11m49.660s
  sys	1m5.920s
  COLCON_EXIT=2
  ```
- Error: `ov_msckf/src/ros/ROS2Visualizer.h:28:10: fatal error: image_transport/image_transport.h: No such file or directory`.
- Diagnosis (read-only): Jazzy ships only `/opt/ros/jazzy/include/image_transport/image_transport/image_transport.hpp` and
  `.../cv_bridge/cv_bridge/cv_bridge.hpp`; the old `.h` names (deprecated in Humble) are gone. OpenVINS still includes the `.h` names in
  `ov_msckf/src/ros/ROS2Visualizer.h` lines 28 and 56 (and ROS1Visualizer.h / ov_core test_tracking.cpp, not built for ROS 2 here).
  This is a genuine 24.04/Jazzy incompatibility (OpenVINS Dockerfiles stop at 22.04). Time used of 2 h box: ~25 min.
- Proposed fallbacks (NOT applied, waiting for user):
  A. Small local patch: change the two includes in ROS2Visualizer.h to `.hpp`, rebuild; stop again if further Jazzy API errors appear.
     Keep it as a patch file in this repo so the change is recorded; OpenVINS source otherwise untouched.
  B. Ubuntu 22.04 + ROS 2 Humble Docker container from `Dockerfile_ros2_22_04` (officially supported combination; heavier; needs Docker in WSL, currently
     only Docker Desktop's Windows binary is on PATH, WSL integration off).
  Recommendation: A first (one-line header renames, keeps everything native on Jazzy), B if A hits deeper API changes.
- Stopped. ov_core/ov_init/ov_eval installed in `~/ws_deps/install`; ov_msckf (the VIO node) not built.

### Session end 2026-10-31
- User asked to close all apps and shut down the PC. All processes started in this session (PX4, gz sim server+GUI, QGC, colcon) are stopped
  (`pgrep` finds none). PC shutdown and `wsl --shutdown` are Windows actions → left to the user.
- Not done this session (outside the install task, still open in WEEK1_BRIEF): repo skeleton + `colcon build` in repo root, mission flight in QGC,
  `ros2 bag record/play` to `~/data/bags/week1_flight/`, `wsl -l -v` output from user.
- Standing environment notes: PX4 make needs `PYTHON_EXECUTABLE=/usr/bin/python3`; colcon pinned via `~/.colcon/defaults.yaml`;
  do not re-run PX4 `ubuntu.sh` / `pip install -r requirements.txt` (brings numpy 2 into `~/.local` again).

## 2026-11-11 — new planning docs, week 1 continued
- User added `docs/WEEK2_8_BRIEFS.md` (weeks 2-8 briefs; one week at a time) and `docs/Terrain-Relative Navigation Project Plan.docx`
  (overall plan dated 2026-10-26: four nodes, 8-week build plan, synthetic odometry decision, cut order, Karta note after week 6).
  `docs/plan.md` is still empty (plan lives in the .docx). Read both; no week-2 work started (week 1 still open).
- Week 1 still open: repo skeleton + colcon build, mission flight + bag, OpenVINS fallback A/B decision (user), `wsl -l -v` (user).

### Week 1 task 3: repo skeleton
- `ros2 pkg create` (in `src/`): `trn_msgs` (ament_cmake; deps std_msgs geometry_msgs builtin_interfaces) and five ament_python packages
  `trn_vio trn_matcher trn_calibration trn_fusion trn_consumer` (dep rclpy). All empty; licence left as the generator's `TODO`.
- `trn_msgs`: added `msg/NavBelief.msg` exactly as in CLAUDE.md, `rosidl_generate_interfaces` in CMakeLists.txt,
  `rosidl_default_generators`/`rosidl_default_runtime`/`rosidl_interface_packages` in package.xml. Removed the generator's empty
  `include/` and `src/` dirs (rmdir, empty only).
- Added `.gitignore` (build/ install/ log/, data/* except README, bags, *:Zone.Identifier), stub `README.md`, `data/README.md`,
  `eval/results/.gitkeep`, `launch/.gitkeep`.
- Acceptance: clean shell (`env -i`, PATH incl. `~/.local/bin`), `colcon build --symlink-install` in repo root →
  `Summary: 6 packages finished [6.75s]`, COLCON_EXIT=0, no stderr output. (Python pinned via `~/.colcon/defaults.yaml`.)
- Check: `ros2 interface show trn_msgs/msg/NavBelief` shows the message; Python `from trn_msgs.msg import NavBelief` →
  `DO_NOT_PUBLISH = 3`, covariance length 36. `ros2 pkg list` shows all 6 trn_ packages. PASS.
- Not run: `colcon test` (generated copyright linter will fail until a licence is chosen).
- Note for week 6: GTSAM is pip-installed in `~/venvs/trn`, while ROS nodes run on system Python; decide then how trn_fusion gets GTSAM.
- Committed skeleton on branch `main` (renamed from unborn `master`, user approved): 1b2daa1 Add repo skeleton, NavBelief message and week 1 docs. `.vscode/` left out. No push.

### OpenVINS fallback A (user chose A)
- Read-only check of all old-style includes in `ov_msckf/src/ros/ROS2Visualizer.h` against `/opt/ros/jazzy/include`: MISSING on Jazzy are
  `image_transport/image_transport.h`, `cv_bridge/cv_bridge.h`, **and** `tf2_geometry_msgs/tf2_geometry_msgs.h` (third one not reached by the
  compiler before it stopped). All three `.hpp` versions exist. message_filters/*.h, tf2/*.h, tf2_ros/transform_broadcaster.h still exist.
- Changed the three includes `.h` → `.hpp` (same kind of change as approved; the third is flagged to the user). Saved as
  `src/trn_vio/patches/open_vins_jazzy_headers.patch` (git diff against OpenVINS `6948812`). Apply to a fresh clone with
  `git -C ~/ws_deps/src/open_vins apply ~/trn-belief/src/trn_vio/patches/open_vins_jazzy_headers.patch`.
- Rebuild: same docs command, `MAKEFLAGS=-j8`, Python pinned via `~/.colcon/defaults.yaml`.
- Rebuild → **FAILED** again (colcon exit 2, 3.5 s). ov_core/ov_init/ov_eval OK; ov_msckf: last 30 lines:
  ```
  gmake[1]: *** [CMakeFiles/Makefile2:145: CMakeFiles/ov_msckf_lib.dir/all] Error 2
  gmake: *** [Makefile:146: all] Error 2
  ---
  --- stderr: ov_msckf
  In file included from /home/akhil/ws_deps/src/open_vins/ov_msckf/src/ros/ROSVisualizerHelper.cpp:22:
  /home/akhil/ws_deps/src/open_vins/ov_msckf/src/ros/ROSVisualizerHelper.h:37:10: fatal error: tf2_geometry_msgs/tf2_geometry_msgs.h: No such file or directory
     37 | #include <tf2_geometry_msgs/tf2_geometry_msgs.h>
        |          ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  compilation terminated.
  gmake[2]: *** [CMakeFiles/ov_msckf_lib.dir/build.make:244: CMakeFiles/ov_msckf_lib.dir/src/ros/ROSVisualizerHelper.cpp.o] Error 1
  gmake[2]: *** Waiting for unfinished jobs....
  In file included from /home/akhil/ws_deps/src/open_vins/ov_msckf/src/ros/ROS2Visualizer.cpp:25:
  /home/akhil/ws_deps/src/open_vins/ov_msckf/src/ros/ROSVisualizerHelper.h:37:10: fatal error: tf2_geometry_msgs/tf2_geometry_msgs.h: No such file or directory
     37 | #include <tf2_geometry_msgs/tf2_geometry_msgs.h>
        |          ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  compilation terminated.
  gmake[2]: *** [CMakeFiles/ov_msckf_lib.dir/build.make:230: CMakeFiles/ov_msckf_lib.dir/src/ros/ROS2Visualizer.cpp.o] Error 1
  gmake[1]: *** [CMakeFiles/Makefile2:145: CMakeFiles/ov_msckf_lib.dir/all] Error 2
  gmake: *** [Makefile:146: all] Error 2
  ---
  Failed   <<< ov_msckf [1.93s, exited with code 2]
  
  Summary: 3 packages finished [2.91s]
    1 package failed: ov_msckf
    1 package had stderr output: ov_msckf
  
  real	0m3.549s
  user	0m2.155s
  sys	0m1.054s
  COLCON_EXIT=2
  ```
- Cause: same missing header `tf2_geometry_msgs/tf2_geometry_msgs.h`, in a second file `ov_msckf/src/ros/ROSVisualizerHelper.h:37`
  (inside its `#elif ROS_AVAILABLE == 2` block). My earlier scope check only scanned ROS2Visualizer.h — incomplete.
- Full read-only scan of every `#include <ros-pkg/...>` in ov_core/ov_init/ov_msckf/ov_eval src against `/opt/ros/jazzy/include`:
  all other missing headers are ROS 1 (`ros/ros.h`, `sensor_msgs/Image.h`, `rosbag/bag.h`, ...) in ROS1-only files/blocks
  (`ROS_AVAILABLE=2` is set by ov_msckf/cmake/ROS2.cmake). So the complete ROS 2 fix = the 3 renames done + this 1. Stopped; asked user.
- User approved the 4th rename. Changed ROSVisualizerHelper.h:37 to `tf2_geometry_msgs.hpp`; regenerated
  `src/trn_vio/patches/open_vins_jazzy_headers.patch` (2 files, 4 includes). Rebuilding with the same command.

### Week 1 task 5 prep: PX4 → ROS 2 bridge (user chose uXRCE-DDS + px4_msgs)
Docs checked (2026-11-11): https://docs.px4.io/main/en/ros2/user_guide.html (source `~/PX4-Autopilot/docs/en/ros2/user_guide.md`).
- Docs: workspace with `px4_msgs` (branch matching the PX4 version; `main` for PX4 main) + `Micro-XRCE-DDS-Agent` built in it with colcon;
  agent version per distro tab: **jazzy → v2.4.3** (humble → v2.4.2). Run `MicroXRCEAgent udp4 -p 8888`; SITL's uxrce_dds_client connects to it.
- Location: docs use `~/ros2_px4_ws`; placed both in `~/ws_deps/src` instead (CLAUDE.md: third-party deps live in ~/ws_deps; week 7 consumer needs px4_msgs).
- Cloned `Micro-XRCE-DDS-Agent` v2.4.3 (11 MB) and `px4_msgs` (2.6 MB, main = 50805c6, 2026-11-10).
- Message match check (docs: px4_msgs must have the same definitions as the firmware): px4_msgs main vs PX4 clone 77aaa2f6da (2026-10-27)
  → 6 differ + 9 extra. Scanned every px4_msgs commit 2026-10-02..11-04: none matches exactly. Closest `83cd992` (2026-10-30):
  only `RoverPositionSetpoint.msg` differs and `SurfaceVehicleCourseSetpoint.msg` is extra (rover/boat only, not used by x500).
  Pinned `px4_msgs` to `83cd992` (detached HEAD). Alternative not taken: docs' manual sync (rm + copy PX4/msg into px4_msgs).
- Rebuild with 4 renames → `Summary: 4 packages finished [1min 44s]`, COLCON_EXIT=0, 0 `error:`, 0 `warning:` lines.
  `~/ws_deps/install/ov_msckf/lib/ov_msckf/`: run_simulation, run_subscribe_msckf, test_sim_meas, test_sim_repeat. **OpenVINS BUILDS** (with patch).
- Smoke test: `cd ~/ws_deps && timeout 25 ros2 run ov_msckf run_simulation src/open_vins/config/rpng_sim/estimator_config.yaml`
  (first try from `~` failed only because `sim_traj_path` in the config is relative to the workspace root). Ran until the timeout (exit 124),
  printing state estimates (`p_IinG ... | dist = 138.41 (meters)`). Error-like lines: 1466 are OpenVINS's own "error to gt" status lines,
  14 are rcl publisher-destruction messages caused by the SIGINT at timeout. No accuracy numbers reported here (rule 1: metrics only from eval/).
- Building: `cd ~/ws_deps && MAKEFLAGS=-j8 colcon build --packages-select px4_msgs microxrcedds_agent` (docs: plain `colcon build`; limited to the two new packages).
- Build → `Summary: 2 packages finished [3min 30s]` (microxrcedds_agent 52.7s, px4_msgs 3m30s), COLCON_EXIT=0, 0 errors.
  Agent stderr only: CMake "Python3_EXECUTABLE not used" (from ~/.colcon/defaults.yaml; harmless) and git clone notes for its bundled
  microxrcedds_client v2.4.3 / microcdr v2.0.1 / spdlog. Binary: `~/ws_deps/install/microxrcedds_agent/bin/MicroXRCEAgent`.

### Week 1 tasks 4+5: scripted mission + bag (user chose: script flies, user watches in QGC)
- `launch/fly_mission.py` (pymavlink, system Python): connects to PX4 SITL API link `udpin:0.0.0.0:14540`, sends GCS heartbeat,
  reads HOME_POSITION, uploads takeoff + 4-corner square (80 m side, 20 m above home) + RTL, arms (retries until accepted, max 90 s),
  MISSION_START, then waits until the last corner is reached and the vehicle has disarmed. Exit 0 = complete.
- `launch/test_fly_mission.py`: `/usr/bin/python3 -m pytest -q` → 3 passed (offset maths, mission structure).
- Bring-up: `MicroXRCEAgent udp4 -p 8888` (session + participant created), `make px4_sitl gz_x500 PYTHON_EXECUTABLE=/usr/bin/python3`
  (`[uxrce_dds_client] init UDP agent IP:127.0.0.1, port:8888`, data writers created), QGC (`partner IP: 127.0.0.1`, `Ready for takeoff!`).
- `ros2 topic list --no-daemon` → 31 `/fmu/out/*` topics (the daemon's cached list first showed 0; stale cache). `vehicle_odometry` ≈ 100 Hz,
  `ros2 topic echo --once` decodes with px4_msgs 83cd992 (`pose_frame: 1` = NED).
- `cd ~/data/bags && ros2 bag record -e '/fmu/out/.*' -o week1_flight` → subscribed to 31 topics, "Recording...".
- `/usr/bin/python3 launch/fly_mission.py` → **FAILED** after 1 s, exit 1. Full output:
  ```
  [09:31:26] waiting for PX4 heartbeat on udpin:0.0.0.0:14540
  [09:31:27] PX4 system 1 component 0
  [09:31:27] home 47.3979706, 8.5461638 (WGS84)
  [09:31:27] MISSION FAILED: mission rejected, MAV_MISSION_RESULT=10
  ```
  PX4 console: `WARN  [mavlink] IGN MISSION_ITEM: Invalid item`. 10 = MAV_MISSION_INVALID_PARAM5_X ("x / param5 has an invalid value").
- Diagnosis (read-only, PX4 source): `mavlink_mission.cpp:1524` validates each global-frame item with `check_params_int_for_vehicle`;
  `mavlink_command_params.hpp:86` lists `NAV_RETURN_TO_LAUNCH` with mask 0x00 ("no params"). My RTL item is sent in
  MAV_FRAME_GLOBAL_RELATIVE_ALT_INT with x=0, y=0 → x counts as a supplied param → rejected. (Spec: unused int x/y = INT32_MAX, float = NaN.)
  TAKEOFF (0x78) and WAYPOINT (0x7B) items are within their masks.
- Stopped the bag recorder with SIGINT (clean close: "Recording stopped"). `~/data/bags/week1_flight/` now holds ~64 s of the vehicle
  idle on the ground (5.0 MB mcap) — not the flight. Proposed fix not applied; asked user.
- User approved: fix RTL encoding and re-fly; rename idle bag. `mv ~/data/bags/week1_flight ~/data/bags/week1_idle_test` (kept, not deleted).
- Script fix: RTL now sent in `MAV_FRAME_MISSION` with x=y=INT32_MAX, z=NaN, params NaN; unsupported params NaN on other items
  (`encode_item()`); 2 new tests → `pytest -q launch/test_fly_mission.py` 5 passed.
- Re-record: `ros2 bag record -e '/fmu/out/.*' -o week1_flight` (31 topics), then `/usr/bin/python3 launch/fly_mission.py`:
  ```
  [09:57:19] mission uploaded: 6 items (takeoff, 4 waypoints, RTL)
  [09:57:19] armed / mission started / PX4: Executing Mission / Climb to 20.0 meters above home
  [09:57:21] PX4: Takeoff detected
  [09:57:38..09:58:24] reached mission item 0, 1, 2, 3
  [09:58:39] PX4: Mission finished, loitering / reached mission item 5 / Switching to Return
  [09:59:05] PX4: Landing detected
  [09:59:07] PX4: Disarmed by landing
  [10:07:19] MISSION FAILED: mission not finished in 600 s (reached items: [0, 1, 2, 3, 5])
  ```
  The FLIGHT completed; the script's own end check is wrong: it waits for MISSION_ITEM_REACHED seq 4 (last corner), but PX4 sent 0,1,2,3,5.
  Script exit 1 after its 600 s timeout. Known bug, NOT fixed yet (proposal: finish on landed+disarmed after the mission was started
  and any item >= last waypoint, or on PX4 "Mission finished"). Asked user in report.
- Stopped recorder with SIGINT after the timeout → bag runs ~8 min past landing.
- `ros2 bag info ~/data/bags/week1_flight`: mcap, 45.0 MiB, Duration 617.13 s, 335683 messages, 31 topics
  (e.g. vehicle_odometry 61704, vehicle_global_position 30852, sensor_combined 154227, vehicle_status_v5 1227, vehicle_land_detected 621).
- Replay: stopped PX4 SITL (SIGINT) so live data can't mix in, then `ros2 bag play ~/data/bags/week1_flight --rate 5`:
  `ros2 topic hz /fmu/out/vehicle_global_position` → 250 Hz (= 5 × recorded 50 Hz); echo shows lat [coordinate removed], lon 8.54722, alt 508.2 (in flight). PASS.
- Flight check from the bag: `python3 eval/check_flight_bag.py ~/data/bags/week1_flight eval/results/week1_flight_check.json`
  (PX4's own topics: vehicle_local_position_v1, vehicle_land_detected, vehicle_status_v5; bag receive time):
  armed 7.59 s → AUTO_MISSION 7.62 s → takeoff 9.32 s → AUTO_RTL 87.73 s → landed 113.08 s → disarmed 115.10 s; airborne 103.76 s;
  max altitude 20.06 m; max horizontal distance from home 109.67 m (80 m square diagonal = 113 m); final distance 0.04 m;
  `ended_landed_and_disarmed: true`. Mission flew to the end (simulation).
- Cleanup: stopped QGC, Agent, PX4 task, gz sim server/GUI. Nothing left running.

## 2026-11-13 — pre-week-2 fixes (user request)
- User ran `wsl -l -v`: `* Ubuntu-24.04  Running  2` (also `docker-desktop  Stopped  2`). Week 1 check 1 now complete: VERSION 2.
- px4_msgs location check: it lives in `~/ws_deps/src/px4_msgs`, NOT in this repo's `src/`. No package in `src/` depends on it
  (grep of package.xml/CMakeLists/setup.py), and repo `build/`/`install/` have no px4_msgs. Nothing to move; repo builds without it.
- Exact dependency commits (all clean except the OpenVINS header patch):
  | Repo | Path | Commit | Describe | Date |
  |---|---|---|---|---|
  | PX4-Autopilot | `~/PX4-Autopilot` | `77aaa2f6da311e05a3bb455841b68aa0948cdf7c` | v1.18.0-beta1-1297-g77aaa2f6da | 2026-10-27 |
  | px4_msgs | `~/ws_deps/src/px4_msgs` | `83cd9920d697e6c73026df1b36b21465dcbe8abd` | (detached) "Update to PX4 d02e110e97bb" | 2026-10-30 |
  | Micro-XRCE-DDS-Agent | `~/ws_deps/src/Micro-XRCE-DDS-Agent` | `73622810d984349b80bbac0ef55fc0b694d62222` | v2.4.3 | 2024-03-20 |
  | OpenVINS | `~/ws_deps/src/open_vins` | `69488123ed9362dd44b6f28e7f4680abbff1442b` | v2.7-20-g6948812 (+ `src/trn_vio/patches/open_vins_jazzy_headers.patch`) | 2025-11-30 |
  Note: px4_msgs 83cd992 is generated from PX4 `d02e110e97bb`, not our `77aaa2f6da`; differences are rover/boat messages only (see 2026-11-11).

### Mission script end condition (user spec)
- Success = PX4 reported mission finished, OR landed and disarmed after the mission started. Timeout stays the failure path.
- Recording stops ~5 s after disarm (script now starts/stops `ros2 bag record` itself with `--record-bag`).
- Re-record time box (45 min) started 2026-11-13 23:32. Old bag kept: `mv ~/data/bags/week1_flight ~/data/bags/week1_flight_run1`.
- Script change (`launch/fly_mission.py`): `MissionTracker` (pure logic) replaces the last-waypoint check; success =
  STATUSTEXT "Mission finished" after start OR (armed after start, now disarmed, EXTENDED_SYS_STATE landed_state ON_GROUND);
  timeout without either = failure. Requests EXTENDED_SYS_STATE at 2 Hz (MAV_CMD_SET_MESSAGE_INTERVAL). New `--record-bag DIR`:
  `BagRecorder` starts `ros2 bag record -e '/fmu/out/.*' -o DIR` just before arming (waits for "Recording..."), stops it with SIGINT
  `RECORD_TAIL_S` = 5 s after disarm; refuses an existing DIR. `pytest -q launch/test_fly_mission.py` → 10 passed (5 new tracker tests).
- Bring-up: Agent (`session established`), `make px4_sitl gz_x500 PYTHON_EXECUTABLE=/usr/bin/python3` (`Ready for takeoff!`), QGC.
- `source /opt/ros/jazzy/setup.bash && source ~/ws_deps/install/setup.bash && /usr/bin/python3 launch/fly_mission.py --record-bag ~/data/bags/week1_flight`
  → SCRIPT_EXIT=0, real 1m55s:
  ```
  [23:33:00] recording /fmu/out/.* to /home/akhil/data/bags/week1_flight
  [23:33:00] armed / mission started / PX4: Executing Mission
  [23:33:02] PX4: Takeoff detected
  [23:33:18..23:34:05] reached mission item 0, 1, 2, 3
  [23:34:20] PX4: Mission finished, loitering / reached mission item 5 / PX4: Switching to Return
  [23:34:46] PX4: Landing detected
  [23:34:48] PX4: Disarmed by landing / disarmed; recording 5 s more
  [23:34:53] MISSION COMPLETE: PX4 reported mission finished; landed and disarmed
  [23:34:53] recording stopped (exit 0)
  ```
  (PX4 again sent MISSION_ITEM_REACHED 0,1,2,3,5 — no 4 — confirming the old check could never pass.)
- `ros2 bag info ~/data/bags/week1_flight`: mcap, 8.2 MiB, Duration 113.10 s (23:33:00.29 → 23:34:53.38), 61148 messages, 31 topics
  (vehicle_odometry 11308, vehicle_global_position 5655, vehicle_local_position_v1 5655, sensor_combined 28266, vehicle_status_v5 229,
  vehicle_land_detected 118; 12 topics with 0 messages, e.g. airspeed/vtol/rc, not used by an x500 in SITL).
- `python3 eval/check_flight_bag.py ~/data/bags/week1_flight eval/results/week1_flight_check.json` (overwrites run1's result):
  armed 0.14 s → AUTO_MISSION 0.34 s → takeoff 1.88 s → AUTO_RTL 80.32 s → landed 105.71 s → disarmed 107.72 s; bag ends 113.10 s
  (5.4 s after disarm). Airborne 103.83 s, max altitude 20.09 m, max horizontal 109.72 m, final 0.04 m, ended_landed_and_disarmed true.
- Stopped PX4/QGC/Agent/gz, then `ros2 bag play ~/data/bags/week1_flight --rate 5`: vehicle_global_position at 250 Hz (= 5 × 50 Hz),
  sample lat [coordinate removed], lon 8.54722, alt 508.27; 0 errors in player log. PASS.
- Old bags kept: `~/data/bags/week1_flight_run1` (617 s, 2026-11-11), `~/data/bags/week1_idle_test` (64 s ground only).
- Time box: started 23:32, flight + checks done by ~23:38 (well inside 45 min).

### Commit prep (user approved commit with two changes)
- Change 1: `MissionTracker.completion_message()` — if PX4 reported "Mission finished" but the vehicle did not disarm before the
  timeout, the script now prints `MISSION FINISHED, NOT DISARMED (warning): PX4 reported mission finished, but the vehicle did not
  disarm before the timeout` instead of `MISSION COMPLETE: ...` (still exit 0, per the success rule). 2 new tests;
  `/usr/bin/python3 -m pytest -q launch/test_fly_mission.py` → 12 passed. The recorded flight is unaffected (it disarmed normally).
- Change 2 — provenance of `eval/results/week1_flight_check.json`:
  - Script: `eval/check_flight_bag.py` (reads PX4's /fmu/out/vehicle_local_position_v1, vehicle_land_detected, vehicle_status_v5).
  - Command (from repo root, system Python):
    `source /opt/ros/jazzy/setup.bash && source ~/ws_deps/install/setup.bash && /usr/bin/python3 eval/check_flight_bag.py ~/data/bags/week1_flight eval/results/week1_flight_check.json`
  - Input: `~/data/bags/week1_flight/week1_flight_0.mcap` (the 2026-11-13 re-record, 113.10 s; sha256 prefix 231a88d175623af2).
  - Re-ran 2026-11-13 before commit: EXIT 0, output byte-identical to the run right after recording. Committed values: duration 113.1 s,
    airborne 103.83 s, max altitude 20.09 m, max horizontal 109.72 m, final 0.04 m, ended_landed_and_disarmed true.
- QGC error-tagged output (QGroundControl daily build 2026-10-27, from `~/tools/QGroundControl-x86_64.AppImage` stderr; same in all 3 runs):
  ```
  libEGL warning: failed to get driver name for fd -1
  libEGL warning: MESA-LOADER: failed to retrieve device information
  MESA: error: ZINK: failed to choose pdev
  libEGL warning: egl: failed to create dri2 screen
  2.200 Critical: Error loading text-to-speech plug-in "speechd" - default - (unknown:0)
  12.590 Warning: No usable QTextToSpeech engine available. Engine: "" State: QTextToSpeech::Error Reason: QTextToSpeech::ErrorReason::Initialization "Text to speech engine not initialized" - Utilities.AudioOutput - (unknown:0)
  28.789 Warning: QGCSensors::QGCPressure::QGCPressure(QObject*) Error Initializing Pressure Sensor - Utilities.QGCSensors - (unknown:0)
  ```
  Meaning: no GPU GL driver in WSLg (software rendering), no speech engine (no voice alerts), no host pressure sensor (QGC's own
  phone/tablet barometer feature). None affected the vehicle link or the mission. Not changed.
- Week 1 complete: all 8 WEEK1_BRIEF checks pass. Commit tagged `week1-done`. Week 2 not started (waiting for user).

## 2026-11-13 — Week 2: VIO baseline and drift model (user started week 2)
Brief: docs/WEEK2_8_BRIEFS.md "Week 2". User notes: check EuRoC formats/sizes on the ETH Research Collection page first, ask if > 1 GB;
if ROS 1 bags, propose a ROS 2 conversion before installing anything; use OpenVINS's shipped EuRoC config, no tuning; stop on first-run failure.
User writes `eval/fit_drift_model.py` (core); assistant scaffolds data, runs, `eval/score_vio.py`, plots.

### Task 1: EuRoC data — check before download
- https://doi.org/10.3929/ethz-b-000690084 → Research Collection item `bcaf173e-5dac-484b-bc37-faf97a594f1f`, "The EuRoC micro aerial vehicle
  datasets" (2024-09-27). **Licence: "In Copyright - Non-Commercial Use Permitted"** (no redistribution of the data in this repo).
- Files are per environment, NOT per sequence (DSpace REST API `/server/api/core/items/<id>/bundles`, sizes in bytes, MD5 given):
  | File | Size | MD5 |
  |---|---|---|
  | machine_hall.zip (MH_01..MH_05) | 12.684 GB | 363f5c2502b469cdd97ef85997714806 |
  | vicon_room1.zip (V1_01..V1_03) | 6.042 GB | 5ce06b405827e453a82523d3ca9c2fd0 |
  | vicon_room2.zip | 6.013 GB | c6347f4e0476aaa9a43a919c163c49c5 |
  | calibration_datasets.zip | 4.416 GB | be0b53d38df53cfab699a795f31dbc7b |
  | euroc_mav_dataset.pdf | 0.37 MB | f755ebbee9b8e052feaccf602934458b |
  MH_01 + V1_01 need machine_hall.zip + vicon_room1.zip = **18.7 GB** if downloaded whole. Over 1 GB → must ask user.
- Server supports HTTP range requests (206, `accept-ranges: bytes`), so reading the ZIP index remotely and fetching only the two
  sequences is possible. Tried to read machine_hall.zip's central directory with Python zipfile over range requests: **HTTP 429 Too Many
  Requests** after a quick burst of requests; retried 6 times with backoff 20..120 s (~7 min): still 429. Stopped (no more requests).
  Format inside the ZIPs (ROS 1 bag vs ASL folders) therefore NOT yet confirmed. Nothing downloaded.
- Decisions (user): (1) partial download after a pause: wait ~1 h, re-read ZIP indexes gently, report contents/format/sizes, then
  download only MH_01 and V1_01 after the user approves the size; stop if still 429. (2) If ROS 1 bags: convert with `rosbags-convert`
  (already in ~/venvs/trn via evo; no install), keep /cam0/image_raw, /cam1/image_raw, /imu0; show `ros2 bag info` before running OpenVINS.
- OpenVINS shipped config: `~/ws_deps/src/open_vins/config/euroc_mav/{estimator_config,kalibr_imucam_chain,kalibr_imu_chain}.yaml`;
  topics `/cam0/image_raw`, `/cam1/image_raw`, `/imu0` (EuRoC names). Will be used unchanged.
- Index re-read scheduled 23:53 + 60 min (one ZIP at a time, 30 s apart, stops at first 429).
- Prepared while waiting (not yet run on data):
  - `eval/score_vio.py` (evo 1.38.1 API, ~/venvs/trn): ATE translation RMSE/max after SE(3) Umeyama over all matched poses
    (no scale; VIO is metric); RPE translation RMSE at 1 m and 10 m travelled; per-pose error vs distance with SE(3) alignment on the
    first `--start-align-m` = 5 m travelled (distance not time: a quiet start makes a time-window alignment ill-conditioned).
    Writes `vio_scores.csv`, `<seq>_error_vs_distance.csv` (input for the user's fit_drift_model.py), plots, `vio_scores_settings.json`.
  - `eval/test_score_vio.py`: `~/venvs/trn/bin/python -m pytest -q eval/test_score_vio.py` → 3 passed (helix with known 2 cm/m drift
    recovered from the start-aligned error slope). Two test-only fixes on the way: a straight-line ground truth is degenerate for Umeyama
    (switched to a helix), and a tolerance tighter than the CSV's 2 decimals.
  - `eval/run_openvins_euroc.sh SEQ BAG OUT`: `ros2 launch ov_msckf subscribe.launch.py` with its defaults (config euroc_mav,
    use_stereo true, max_cameras 2; config files untouched), records `/ov_msckf/poseimu`, plays the bag at 1x,
    converts with `evo_traj bag2 ... --save_as_tum`.
  - Ground truth: prefer the dataset's own `state_groundtruth_estimate0/data.csv`; fallback OpenVINS `ov_data/euroc_mav/*.csv`
    (note: ov_data has both `V1_01_easy.csv` and `V1_01_easy_original.csv` — will log which is used).

## 2026-11-14 — Week 2 continued
- Confirmed on request: `git log --oneline` → bee6578, c4af75e, 38f7aa4, 1b2daa1; `git tag` → `week1-done` (annotated, → bee6578).
- User limits: one retry of the index read only, scheduled job must not download data; download cap 5 GB total for MH_01 + V1_01
  (ask if more); if ASL plain files, do NOT start a converter: report format, propose options (converter script vs TUM VI), wait.
- Scheduled job (started 2026-11-13 ~23:54, fires ~00:54): `euroc_index.py` reads only the ZIP central directories of machine_hall.zip
  and vicon_room1.zip via range requests, writes a JSON listing to the scratchpad, single attempt, stops at first 429. No data download.
- `eval/score_vio.py` change (user spec): drift curve now uses **4-DoF alignment (yaw about z + translation)** over the first 5 m
  travelled (`align_yaw_translation`, closed-form least squares; assumes z along gravity in both frames). ATE/RPE keep the standard
  SE(3) alignment over all poses. Method + window are written to `vio_scores_settings.json` under `drift_curve_alignment`
  (`method: 4dof_yaw_translation`, `window_m: 5.0`) for the user's `fit_drift_model.py` to copy into `drift_params.json`.
  `~/venvs/trn/bin/python -m pytest -q eval/test_score_vio.py` → 5 passed (known yaw+shift recovered; tilt is not removed).
- `eval/score_vio.py` (user request, before the index read): drift-curve CSV columns are now `t_rel_s, distance_m,
  horiz_err_start_aligned_m` (norm of x,y error), `vert_err_start_aligned_m` (signed z error, est - gt), `horiz_err_whole_aligned_m`
  (horizontal error with the same 4-DoF yaw+translation alignment over ALL poses; chosen over SE(3) so that only the window differs).
  Per sequence, `vio_scores.csv` gains `horiz_rmse_start_aligned_m, horiz_rmse_whole_aligned_m, horiz_mean_abs_diff_m,
  horiz_max_abs_diff_m, vert_rmse_start_aligned_m`, and the script prints one line with the two RMSEs and the mean/max difference
  between the curves. Plot: horizontal solid, |vertical| dashed. `pytest -q eval/test_score_vio.py` → 5 passed (synthetic helix with
  2 cm/m horizontal + 1 cm/m vertical drift: both slopes recovered; reported differences match the CSV). No real-data numbers yet.
- Committed `37bc6ea` "Add VIO scoring and OpenVINS EuRoC run scripts (not yet run on real data)".
- `eval/score_vio.py` tilt cross-check (user request): the whole-trajectory cross-check curve now uses **SE(3)** alignment
  (`horiz_err_whole_se3_aligned_m`); the whole-trajectory yaw+translation curve is kept as `horiz_err_whole_yaw_aligned_m`.
  `horiz_mean_abs_diff_m` / `horiz_max_abs_diff_m` now compare the start-aligned curve with the SE(3) curve.
  New per-sequence columns in `vio_scores.csv` and a printed line: `se3_align_roll_deg`, `se3_align_pitch_deg` (ZYX Euler angles of
  the rotation evo's SE(3) alignment applies to the estimate) and `se3_align_tilt_deg` (angle between z axes).
  New test: estimate = ground truth rolled by 1 deg about x → reported tilt 1.0 deg, roll -1.0 deg (the rotation that undoes it),
  pitch 0; ATE ~0 while the yaw+translation vertical error stays > 5 cm. `pytest -q eval/test_score_vio.py` → 6 passed.
- Committed `fbe2dd7` "Add tilt cross-check to VIO scoring".
- 2026-11-14 14:46 status check (user): the scheduled EuRoC index read **never ran**. Its task output is `[killed]` with nothing else,
  the output folder `euroc_meta/` was never created (the script creates it only after the 1 h wait), and no process is left.
  WSL was restarted (uptime since 14:42), and the job was killed during its wait when the previous session ended.
  So: no request was sent to the ETH server by that job (no new 429), format and per-sequence sizes still unknown, nothing downloaded
  (`~/data` holds only the week 1 bags, 59 MB). Not retrying until the user confirms.
- 2026-11-14 14:52 index read (user approved: foreground, single attempt, >= 2 s between requests, stop at first 429, no data download):
  `python3 -I euroc_index.py euroc_meta/euroc_index.json` (scratchpad script; 2.5 s pause added between requests) →
  `{"machine_hall.zip": "HTTP 429"}` on the **very first request** (`Range: bytes=0-0`), no `Retry-After` header. Stopped after that one
  request; vicon_room1.zip not contacted. Nothing downloaded. Format, file names and per-sequence sizes still unknown.
- Observation (not a conclusion): ~15 h after the last contact a 429 on request #1 is unlikely to be a short burst limit.
  Every request made with Python urllib has returned 429 (2026-11-13 with the default `Python-urllib` User-Agent, later and today with
  `trn-belief-dataset-check/0.1 (python urllib)`), while the 2026-11-13 range requests made with the sandbox's JS `fetch` returned 206 for
  all five files. Possible causes: the server refuses script-like User-Agents on file content, or a longer per-IP block from the
  2026-11-13 burst. Untested; no further requests until the user decides.
- Committed `34cb4fa` "Log EuRoC index read".

### Week 2 switched to TUM VI (user decision, 2026-11-14)
- User: do not try other clients/user agents against the ETH server; leave EuRoC. Use TUM VI 512x512 ROS bags, room1 + room2 only;
  limit 6 GB total; one file at a time with wget into `~/data/tumvi/`, gentle pace, verify MD5, stop at first 429/403; convert with
  `rosbags-convert`; use OpenVINS's shipped TUM VI config unmodified and report findings before running.
- Dataset page https://cvg.cit.tum.de/data/datasets/vi-dataset (→ .../visual-inertial-dataset), checked 2026-11-14:
  - "room: Sequences in the room with Motion Capture system, where ground truth poses are available for the entire trajectory."
    (corridor/magistrale/outdoors/slides: ground truth only at start and end.) → room sequences have full ground truth. CONFIRMED.
  - Licence: "All data in the Visual Inertial Dataset is licensed under a Creative Commons 4.0 Attribution License (CC BY 4.0)".
  - Cameras 20 Hz, IMU 200 Hz, motion capture 120 Hz.
  - Citation: Schubert, Goll, Demmel, Usenko, Stueckler, Cremers, "The TUM VI Benchmark for Evaluating Visual-Inertial Odometry", IROS 2018.
- Files (directory listing https://vision.in.tum.de/tumvi/calibrated/512_16/, sizes from `wget --spider`, MD5 from the `.md5` files):
  | File | Bytes | MD5 |
  |---|---|---|
  | dataset-room1_512_16.bag | 2,971,525,053 | 8aa20cf81bedac03e45c78239ce156c0 |
  | dataset-room2_512_16.bag | 3,035,570,964 | a70ce1fc5585042af812427e9ab85752 |
  Total 6,007,096,017 bytes = 6.007 GB decimal (5.59 GiB): ~7 MB over a decimal 6 GB limit. Downloading room1 only; asked user about room2.
- room1: `wget --tries=1 --limit-rate=20m -nv -O dataset-room1_512_16.bag <url>` then `md5sum -c dataset-room1_512_16.bag.md5` (background).
- OpenVINS TUM VI config (found, shipped, will be used unmodified): `~/ws_deps/src/open_vins/config/tum_vi/`
  {estimator_config.yaml, kalibr_imucam_chain.yaml, kalibr_imu_chain.yaml, mask_tumvi0.png, mask_tumvi1.png}.
  - Topics `/cam0/image_raw`, `/cam1/image_raw`, `/imu0`; resolution [512, 512], pinhole + equidistant (fisheye): matches the 512_16 bags.
  - Stereo (`use_stereo: true`, `max_cameras: 2`), `use_mask: true` (the two mask PNGs), `num_pts: 200`, `track_frequency: 21.0`,
    online calibration of camera extrinsics/intrinsics/time offset on, `init_imu_thresh: 0.45` with the config's own comment
    "room1-5:0.45, room6:0.25" (so the shipped value is the authors' setting for room1/room2).
  - The launch file reads the INSTALLED copy (`~/ws_deps/install/ov_msckf/share/ov_msckf/config/tum_vi`); `diff -rq` → identical to source;
    `git status config/` clean (the only OpenVINS modifications are the two header files of our patch).
  - Ground truth shipped by OpenVINS: `ov_data/tum_vi/dataset-room{1,2}_512_16.{txt,csv}` (TUM format / EuRoC-style CSV, 16542 and 15478
    poses, last changed 2020-03-19). To decide with the user: use these or the mocap topic inside the bag.
- `eval/run_openvins_euroc.sh` now takes the dataset name first: `DATASET SEQ_NAME ROS2_BAG_DIR OUT_DIR`; passes `config:=<DATASET>`
  to `subscribe.launch.py`, checks the config folder and bag exist. File name kept (noted as historical in its header).
- User decisions 2026-11-14: room2 download approved (same way, `wget -c`, after room1 since one file at a time); ground truth = the files
  shipped with OpenVINS (`ov_data/tum_vi/`); run OpenVINS once on room1 at 1x with the unmodified config, score, then stop (no room2 run,
  no parameter change).
- `git mv eval/run_openvins_euroc.sh eval/run_openvins.sh` (usage text updated; arguments unchanged: `DATASET SEQ_NAME ROS2_BAG_DIR OUT_DIR`).
- User (2026-11-14): do not run OpenVINS while a download or MD5 check runs; quiet machine. Room1 report must state camera frame count in the bag, number of OpenVINS poses, and any dropped-message/queue-overflow reports; rerun before scoring if the run lagged. Plan: room1 MD5 → room2 download + MD5 → only then the OpenVINS run (conversion of room1 may overlap the room2 download).
- room1 download finished 15:10: `[2971525053/2971525053]`, WGET_EXIT=0, `md5sum -c` → `dataset-room1_512_16.bag: OK`. No 429/403.
- room2 started 15:10: `wget -c --tries=1 --limit-rate=20m -nv -O dataset-room2_512_16.bag <url>`, then `md5sum -c` (background).
- Convert: `~/venvs/trn/bin/rosbags-convert --src dataset-room1_512_16.bag --dst dataset-room1_512_16_ros2 --dst-storage mcap` (7 s)
  → `~/data/tumvi/dataset-room1_512_16_ros2/` (2.97 GB mcap + metadata.yaml).
- `ros2 bag info ~/data/tumvi/dataset-room1_512_16_ros2`: Duration 141.05 s (1520530308.18 → 1520530449.23), 50305 messages:
  | Topic | Type | Count | Rate |
  |---|---|---|---|
  | /cam0/image_raw | sensor_msgs/msg/Image | 2821 | 20.0 Hz |
  | /cam1/image_raw | sensor_msgs/msg/Image | 2821 | 20.0 Hz |
  | /imu0 | sensor_msgs/msg/Imu | 28122 | 199.4 Hz |
  | /vrpn_client/raw_transform | geometry_msgs/msg/TransformStamped | 16541 | 117.3 Hz |
  Matches the dataset page (cameras 20 Hz, IMU 200 Hz, mocap ~120 Hz) and the OpenVINS config topics. Looks right.
- Ground truth for room1: `~/ws_deps/src/open_vins/ov_data/tum_vi/dataset-room1_512_16.txt` (shipped with OpenVINS 6948812, file last
  changed 2020-03-19, md5 ac288b68dca8c420f64ffe705a09d939; TUM format `t x y z qx qy qz qw`; derived by the OpenVINS authors from
  TUM VI's motion capture, CC BY 4.0). 16541 poses (= mocap message count in the bag), time 1520530308.190 → 1520530449.215:
  inside the bag's range (starts 8 ms after, ends 18 ms before). Overlap CONFIRMED.
- OpenVINS run on room1 is waiting for the room2 download + MD5 to finish (user rule: quiet machine).
- room2 download finished 15:24: `[3035570964/3035570964]`, WGET_EXIT=0, `md5sum -c` → OK. No 429/403. `~/data/tumvi` now holds both
  ROS 1 bags (6.007 GB) + room1 converted (2.97 GB). room2 not converted, not run.

### First OpenVINS run: TUM VI room1 (2026-11-14 15:25, quiet machine: load avg 0.35, no download/MD5/sim/QGC running)
- Command: `eval/run_openvins.sh tum_vi room1 ~/data/tumvi/dataset-room1_512_16_ros2 eval/results/vio`
  (= `ros2 launch ov_msckf subscribe.launch.py config:=tum_vi`, shipped config unmodified, `ros2 bag play` at 1x, record `/ov_msckf/poseimu`).
- **Wrapper script problem (not a VIO failure):** `ros2 bag play` did not exit after playback ended (~15:27:26), so the script hung at
  that step; my 420 s command timeout moved it to the background and it was killed when the session ended (15:35). The exit trap sent
  SIGINT to the recorder, which closed the bag cleanly ("Recording stopped"). The script's last step (TUM conversion) never ran; done by
  hand: `cd eval/results/vio && ~/venvs/trn/bin/evo_traj bag2 room1_poseimu_bag /ov_msckf/poseimu --save_as_tum && mv ov_msckf_poseimu.tum room1_openvins.tum`.
  Cause of the hang NOT diagnosed (play.log ends after "Playback until timestamp: -1"; week 1 only ever ran play under `timeout`).
  Proposed, not applied: run play under `timeout <bag duration + 30 s>` and treat that as normal end. Asked user.
- Last 30 lines of `room1_openvins.log`: normal per-frame state prints up to the end of the bag, e.g.
  `[TIME]: 0.0101 seconds total (98.7 hz, 0.33 ms behind)`, `p_IinG = 0.075,0.757,-0.023 | dist = 146.47 (meters)`.
- Run health (from the logs):
  - Camera frames in the bag: 2821 per camera (stereo pairs). OpenVINS update prints (`[TIME]` lines): 2815.
  - Poses output on `/ov_msckf/poseimu` and recorded: **2689** (134.40 s, bag time 1520530314.80 → 1520530449.20). The first ~6.6 s
    have no pose: initialisation (102 × `[init]: failed static init: no accel jerk detected` while the sensor is still at rest).
  - Lag: processing rate median 97 Hz (min 14.7 Hz; 7 of 2815 updates slower than the 20 Hz camera rate); "ms behind" median 0.29,
    max 11.38 ms. No lag → no rerun.
  - Dropped messages / queue overflow: 0 lines matching drop|overflow|queue|lost|skip in the OpenVINS log; none in record/play logs.
- Scoring: `~/venvs/trn/bin/python eval/score_vio.py --out eval/results/vio --seq room1 eval/results/vio/room1_openvins.tum ~/ws_deps/src/open_vins/ov_data/tum_vi/dataset-room1_512_16.txt`
  → `eval/results/vio/vio_scores.csv` (+ `room1_error_vs_distance.csv`, `room1_trajectory.png`, `error_vs_distance.png`, `vio_scores_settings.json`):
  - matched poses 2632 of 2689 (max time gap 10 ms; 57 estimate poses have no ground-truth pose that close), duration 134.41 s,
    ground-truth path length 145.94 m.
  - ATE RMSE 0.0660 m, max 0.1098 m (SE(3) alignment, all poses). RPE translation RMSE 0.0131 m per 1 m (140 pairs), 0.0317 m per 10 m (14 pairs).
  - Horizontal error RMSE: 0.0526 m (yaw+translation on first 5 m) vs 0.0421 m (whole-trajectory SE(3)) / 0.0421 m (whole yaw+translation);
    start vs SE(3) curves differ by mean 0.0186 m, max 0.0576 m. Vertical error RMSE (start-aligned) 0.0838 m; final values at 145.9 m:
    horizontal 0.086 m, vertical +0.151 m.
  - SE(3) alignment rotation: roll -0.131 deg, pitch +0.470 deg (tilt 0.488 deg).
  - Simulation/public-data result on one sequence, one run; single run, not averaged.
- Not verified: that the shipped ground-truth file is expressed in the IMU frame OpenVINS estimates (assumed, as OpenVINS's own
  evaluation uses it). Note for the drift model: room1 is 146 m of motion inside a ~3.5 x 2.5 m area, revisiting the same scene, so
  error growth with distance here may understate drift on a long one-way flight.
- Stopped as instructed: room2 not run, no parameter changed. `eval/results/vio/` not committed yet.

## 2026-11-14/15 — fixed run script, repeat runs (user request)
- User: wrap `ros2 bag play` in a timeout of bag duration + 30 s and log whether it exited or was cut off; diagnose the hang max 15 min;
  rerun room1 x3 end-to-end, then room2 x3 (convert first), quiet machine; report mean/spread of ATE, RPE, tilt, final horizontal and
  vertical errors, and a dropped-message check per run; commit CSVs/plots/settings/TUM files but not pose bags or logs. No parameter changes.
- Hang diagnosis (2026-11-14 20:03–20:07, ~4 min of the 15-min box): `ros2 bag play` exited by itself every time:
  week1_idle_test at 8x (8.8 s), room1 at 10x (14.7 s), room1 at 10x with stdin from /dev/null (14.7 s), room1 at 1x with no subscriber
  (141.7 s, exit 0). **Not reproduced; cause still unknown.** Differences from the hung run: OpenVINS + recorder were subscribed, and that
  run was the first after WSL start. Not pursued further; the timeout guards against it.
- `eval/run_openvins.sh`: play now runs under `timeout --signal=INT --kill-after=10 <ceil(bag duration)+30 s>` (duration read from the
  bag's metadata.yaml); writes `<run>_run_status.txt` (bag, duration, timeout, wall time, exit code, "exited by itself" or "cut off by
  timeout or failed"); children are stopped with SIGINT, then SIGKILL after 15 s, so the script cannot hang on shutdown.
- `eval/score_vio.py`: adds `final_horiz_err_start_aligned_m` and `final_vert_err_start_aligned_m` (errors at the last matched pose).
  `env -u PYTHONPATH ~/venvs/trn/bin/python -m pytest -q eval/test_score_vio.py` → 6 passed. (Note: with ROS sourced, ROS's PYTHONPATH
  breaks the venv's pytest — `No module named 'lark'` — hence `env -u PYTHONPATH`.)
- New `eval/summarize_vio_runs.py` (system Python): per sequence mean, sample std, min, max of ATE, RPE 1 m/10 m, roll/pitch/tilt,
  final and RMSE horizontal/vertical errors → `vio_runs_summary.csv`; per run health (camera frames in bag, OpenVINS updates, poses,
  max ms behind, updates slower than 20 Hz, lines matching drop|overflow|queue|lost|skip in the OpenVINS/play/record logs, how play
  ended) → `vio_run_health.csv`. `pytest -q eval/test_summarize_vio_runs.py` → 3 passed.
- New `eval/run_week2_vio.sh [RUNS]` = the one documented command: RUNS (default 3) runs per sequence, one at a time, then
  score_vio.py on all runs, then summarize_vio_runs.py.
- First room1 run (hand-finished) moved, not deleted, to `eval/results/vio/manual_room1_2026-11-14/`.
- room2 converted: `rosbags-convert --src dataset-room2_512_16.bag --dst dataset-room2_512_16_ros2 --dst-storage mcap`; `ros2 bag info`:
  144.11 s, 49973 messages; /cam0 and /cam1 2882 each (20 Hz), /imu0 28732 (199 Hz), /vrpn_client/raw_transform 15477.
  Ground truth `ov_data/tum_vi/dataset-room2_512_16.txt` (md5 35a87e586e628dc8bca2e1e5b8df1956): 15477 poses, 1520530731.383 →
  1520530875.449, inside the bag (1520530731.372 → 1520530875.480). Overlap CONFIRMED.
- Started `eval/run_week2_vio.sh 3` at 2026-11-15 10:44:08, load average 0.52, no download/MD5/sim/QGC running.
- User (2026-11-15): commit `*_run_status.txt`; in run_openvins.sh the recorder must get SIGINT and close before any force-stop of
  other programs; check each pose bag opens with `ros2 bag info` before scoring; invalid runs excluded from the summary and listed
  separately; report whether any of the six runs needed it.
- Implemented while room1_run1 was playing (new files swapped in by `mv`, so the running copies kept their old content):
  `eval/run_openvins.sh` stops the recorder first (SIGINT, up to 60 s to close, SIGKILL only after that), then OpenVINS (SIGINT, 15 s,
  SIGKILL); then `ros2 bag info` on the pose bag; status file gains `recorder_end`, `pose_bag_messages`, `valid`, `reason`; no TUM file
  for an invalid run. New `eval/score_week2_vio.sh`: checks every run (status, `ros2 bag info`, recorder closed, TUM present), writes
  `vio_invalid_runs.csv`, scores only valid runs, then summarises. `eval/run_week2_vio.sh` calls it. `summarize_vio_runs.py` health
  gains `recorder_end`.
- **FAILURE, room1_run1 (old script version)**: play exited by itself after 141.7 s; then `pid 5700 ignored SIGINT, sending SIGKILL`
  (ros2 launch / OpenVINS) and `pid 5758 ignored SIGINT, sending SIGKILL` (ros2 bag record); TUM conversion failed, `set -e` ended the
  script, driver ended DRIVER_EXIT=1 after run 1. Runs 2-6 never started. Driver log (all 11 lines):
  ```
  [week2] 2026-11-15 10:44:08 start room1_run1 | load: 0.44 0.55 0.27
  [run] OpenVINS subscribe.launch.py config:=tum_vi (other launch defaults) -> eval/results/vio/room1_run1_openvins.log
  [run] recording /ov_msckf/poseimu -> eval/results/vio/room1_run1_poseimu_bag
  [run] playing /home/akhil/data/tumvi/dataset-room1_512_16_ros2 at 1x (bag 141.050428 s, timeout 172 s)
  [run] ros2 bag play: exited by itself after 141.7 s
  [run] pid 5700 ignored SIGINT, sending SIGKILL
  eval/run_openvins.sh: line 33:  5700 Killed                  ros2 launch ov_msckf subscribe.launch.py config:="$DATASET" > "$LOG" 2>&1
  [run] pid 5758 ignored SIGINT, sending SIGKILL
  [run] converting to TUM
  eval/run_openvins.sh: line 70:  5758 Killed                  ros2 bag record -o "$EST_BAG" /ov_msckf/poseimu > "$OUT/${SEQ}_record.log" 2>&1
  DRIVER_EXIT=1
  ```
  room1_run1 pose bag: only `room1_run1_poseimu_bag_0.mcap` (815 KB), no metadata.yaml; `ros2 bag info` exit 1 → INVALID.
  Orphan: the SIGKILLed `ros2 launch` left `run_subscribe_msckf` (pid 5704) running at ~28% CPU; stopped with SIGTERM.
- Diagnosis (confirmed by test): in a non-interactive bash script, commands started with `&` inherit SIGINT and SIGQUIT as IGNORED:
  `bash -c 'sleep 30 & grep SigIgn /proc/$!/status'` → `SigIgn: 0000000000000006` (bits for SIGINT 2, SIGQUIT 3). So every SIGINT
  the script sent to OpenVINS and the recorder was ignored. `(trap - INT; exec sleep 30) &` → `SigIgn: 0000000000000000`.
  This also explains 2026-11-14: that recorder only closed when the session teardown signalled it, and week 1's recorder worked
  because Python `subprocess.Popen` does not ignore SIGINT. The new recorder-first order alone would NOT have fixed it (the recorder
  would just be force-killed after 60 s and every run marked invalid).
- Proposed, NOT applied: start OpenVINS and the recorder as `(trap - INT; exec ros2 ...) &` so SIGINT reaches them; keep the
  recorder-first shutdown and bag check; move the failed run1 files to `eval/results/vio/failed_2026-11-15/`; restart all 6 runs.

## 2026-11-17 — signal handling fix and shutdown smoke test (user approved the fix)
- Moved the failed run 1 files (not deleted) to `eval/results/vio/failed_2026-11-15/`.
- New `eval/lib_proc.sh` (sourced by run_openvins.sh and the smoke test): `start_bg` starts a program as `( trap - INT QUIT; exec ... ) &`
  so SIGINT is not ignored; `stop_proc PID INT_WAIT TERM_WAIT` = SIGINT and wait, SIGTERM only if SIGINT failed, SIGKILL only if
  both failed, reporting which one worked; `pose_bag_messages` = `ros2 bag info` check.
- `eval/run_openvins.sh` rewritten on top of it: recorder stopped first (SIGINT 60 s, then SIGTERM 30 s), then OpenVINS (SIGINT 15 s,
  then SIGTERM 15 s); leftover `run_subscribe_msckf` processes are counted and stopped. **Invalid** (exit code 3, no TUM file) if any
  program needed SIGKILL, any OpenVINS process outlived the launch, or the pose bag does not open / has no poses. Refuses to start if
  an OpenVINS process is already running. Status adds `openvins_end`, `leftover_openvins_processes`. `SMOKE_PLAY_S` plays only N seconds.
  Recorder now uses `--topics` (the positional form was deprecated).
- `eval/score_week2_vio.sh` re-checks every run (bag opens, no SIGKILL, no leftovers, valid, TUM present); `summarize_vio_runs.py`
  health gains `openvins_end`, `leftover_openvins_processes`.
- New `eval/smoke_test_shutdown.sh BAG WORK_DIR` (~55 s). Run: `eval/smoke_test_shutdown.sh ~/data/tumvi/dataset-room1_512_16_ros2
  <scratchpad>/smoke_112505` at 11:25, load 0.32. Result **FAILED** (1 of 8 checks):
  ```
  [run] ros2 bag play: stopped at smoke-test limit (expected) after 20.2 s
  [run] recorder: exited after SIGINT | OpenVINS: exited after SIGINT | leftover OpenVINS processes: 0
    PASS recorder: exited after SIGINT
    PASS OpenVINS: exited after SIGINT
    PASS leftover OpenVINS processes: 0
    PASS valid: yes                         (pose bag messages: 260)
  [smoke] B: SIGTERM fallback (no SIGINT sent)
    PASS recorder on SIGTERM: exited after SIGTERM
    PASS OpenVINS on SIGTERM: exited after SIGTERM
    FAIL leftover OpenVINS processes: got '1', want '0'
    PASS SIGTERM-closed bag opens: yes      (pose bag messages: 60)
  [smoke] FAILED
  ```
  The SIGINT path (the one runs use) passes completely. With SIGTERM, `ros2 launch` exits but leaves its `run_subscribe_msckf`
  node running; the test's cleanup stopped it (nothing left running afterwards). run_openvins.sh already treats that case as invalid
  and stops the leftover, so a SIGTERM-fallback run could not be scored silently — but the fallback itself is incomplete.
- Stopped per rule: not committed, six runs not restarted. Proposed: when the launch needed SIGTERM, also send SIGTERM to its
  `run_subscribe_msckf` child before counting leftovers, then rerun the smoke test.
- User decision 2026-11-17: do NOT extend the SIGTERM fallback; the SIGINT path passed, so commit and run.
  **Known limitation:** if OpenVINS ever needs the SIGTERM fallback, `ros2 launch` exits but leaves its `run_subscribe_msckf` node
  running. run_openvins.sh then finds it in the leftover check, stops it, and marks the run INVALID (`leftover_openvins_processes` > 0),
  so such a run is never scored. Smoke-test check B3 is expected to fail for this reason.
- 2026-11-17: first batch attempt (in-session background job with load gate) was lost when WSL restarted (~17:01–17:09; /tmp log
  gone). It had completed room1_run1 (status: play exited by itself 141.7 s, recorder and OpenVINS "exited after SIGINT", 0 leftovers,
  2689 poses, valid=yes — first real run on the fixed SIGINT path) and was cut off in room1_run2 (0-byte pose bag, no status).
  Both moved (not deleted) to `eval/results/vio/interrupted_2026-11-17/`; starting load of run1 unknown, so the six runs start fresh.
- VS Code C++ extension (cpptools) was indexing all of `/opt/ros/jazzy/include/**` and `/usr/include/**` (ROS extension's
  `.vscode/c_cpp_properties.json`, `limitSymbolsToIncludedHeaders: false`), up to ~150% CPU. Per user: paused for this workspace only:
  `.vscode/settings.json` += `"C_Cpp.intelliSenseEngine": "disabled"`, `"C_Cpp.workspaceParsingPriority": "low"`
  (backup `.vscode/settings.json.bak-2026-11-17`; `.vscode/` is untracked). Afterwards cpptools no longer among the top CPU users.
  To re-enable later: remove those two keys.
- New `eval/week2_batch.sh`: writes `eval/results/vio/week2_batch.pid`, waits until load1 < 0.7 for 60 s (10 s checks, give up after
  30 min with no runs), then `eval/run_week2_vio.sh 3`. `.gitignore` += `eval/results/**/*.pid`.
- Started 2026-11-17 17:22:54 with `setsid nohup eval/week2_batch.sh > eval/results/vio/week2_batch.log 2>&1 < /dev/null &`
  → PID 5782, own session (SID = PGID = 5782), so it survives a closed terminal/editor (not a WSL shutdown). Load at start 1.33.

### 2026-11-17 — week 2 six-run batch: results
- Batch (PID 5782): load gate passed 17:24:24 (load 0.29 0.48 0.23), runs 17:24:24–17:40:07, scoring done 17:40:13,
  `run_week2_vio.sh` exit code 0. Start load of every run between 0.18 and 0.34 (1-min). Log: `eval/results/vio/week2_batch.log` (not committed).
- All 6 runs VALID (`eval/results/vio/vio_invalid_runs.csv` has no rows). Every run: `ros2 bag play` exited by itself
  (141.6 s room1, 144.6–144.7 s room2), recorder and OpenVINS "exited after SIGINT", 0 leftover OpenVINS processes.
  No run needed SIGTERM, SIGKILL or the timeout.
- Dropped-message check (`vio_run_health.csv`): 0 problem lines (drop/overflow/queue/lost/skip) in the OpenVINS, play and record logs
  of all 6 runs; 0 updates slower than 20 Hz. Poses: 2689/run room1 (2821 camera frames), 2778/run room2 (2882 frames).
  OpenVINS updates 2808–2815 room1, 2876–2882 room2. Max ms behind: 46.5–46.6 room1, 1.6–6.5 room2.
- Scores: `eval/score_week2_vio.sh` (calls `eval/score_vio.py --out eval/results/vio --seq ...` then `eval/summarize_vio_runs.py`)
  → `eval/results/vio/vio_scores.csv`, `vio_scores_settings.json`, `vio_runs_summary.csv`, `*_error_vs_distance.csv`, plots.
  Per sequence, mean ± sample std (min–max), n = 3 (from `vio_runs_summary.csv`):

  | metric | room1 | room2 |
  |---|---|---|
  | ATE RMSE (m) | 0.0651 ± 0.0015 (0.0634–0.0660) | 0.0845 ± 0.0078 (0.0755–0.0890) |
  | RPE 1 m (m) | 0.0129 ± 0.0003 (0.0125–0.0131) | 0.0284 ± 0.0000 (0.0284–0.0284) |
  | RPE 10 m (m) | 0.0329 ± 0.0020 (0.0317–0.0352) | 0.0887 ± 0.0052 (0.0827–0.0917) |
  | SE(3) roll (°) | −0.140 ± 0.016 | −0.081 ± 0.104 |
  | SE(3) pitch (°) | 0.457 ± 0.022 | 0.045 ± 0.131 |
  | SE(3) tilt (°) | 0.478 ± 0.016 (0.460–0.488) | 0.162 ± 0.042 (0.113–0.186) |
  | final horiz err, start-aligned (m) | 0.094 ± 0.014 (0.086–0.111) | 0.149 ± 0.066 (0.072–0.187) |
  | final vert err, start-aligned (m) | 0.137 ± 0.025 (0.107–0.151) | 0.004 ± 0.029 (−0.013–0.038) |

- Caveats: three runs of the same bag measure run-to-run nondeterminism of OpenVINS at 1x replay, not variation across flights;
  room1/room2 are small indoor loops (tens of metres of extent), so drift over distance may be understated; GT frame assumed to be IMU.
  Simulation/public data only, nothing flight-tested.
- Committed: CSVs, plots, settings JSON, TUM files and `*_run_status.txt` of the six runs, plus `eval/week2_batch.sh`, `.gitignore`
  and this log. Not committed: pose bags, logs, and the set-aside folders `manual_room1_2026-11-14/`, `failed_2026-11-15/`,
  `interrupted_2026-11-17/` (kept on disk). No parameter changed.

### 2026-11-17 — RPE vs segment length; room1 "46.5 ms" lag
- `eval/score_vio.py`: new `--rpe-curve-deltas` (default 1 2 5 10 20 50 m) → per run `eval/results/vio/<run>_rpe_vs_delta.csv`
  (delta_m, n_segments, rpe_trans_rmse/mean/median/max in m); `--rpe-deltas` default now 1 10 50, so `vio_scores.csv` gains
  `rpe_trans_rmse_50m` and `rpe_pairs_50m`. A segment longer than the path gives 0 segments and empty values.
  New test `test_rpe_vs_delta_grows_with_segment_length` (known linear drift); `env -u PYTHONPATH ~/venvs/trn/bin/python -m pytest -q eval/test_score_vio.py` → 7 passed.
- **Found while testing:** evo 1.38.1 `RPE` defaults to `pairs_from_reference=False`, so segment lengths are measured along the
  ESTIMATE's path, not the ground truth's. This was already true for the committed 1 m / 10 m values. Kept unchanged (so earlier
  numbers stay comparable) and now documented in the docstring and in `vio_scores_settings.json` (`rpe_segments`).
  Not decided: whether to switch to ground-truth path lengths (`pairs_from_reference=True`); that would change all RPE values.
- Rescored the six existing runs, no OpenVINS rerun: `eval/score_week2_vio.sh` (re-checks each pose bag with `ros2 bag info`, scores
  the TUM files converted from them). All 6 valid. Every earlier column of `vio_scores.csv` is unchanged against HEAD; only the
  50 m columns are new. `vio_runs_summary.csv` is unchanged (its metric list does not include 50 m).
- RPE at 50 m (`vio_scores.csv`): room1 0.0843 / 0.0825 / 0.0825 m, room2 0.2077 / 0.2153 / 0.2077 m — each from only **2**
  non-overlapping segments (paths 145.9 m and 140.6 m), so a very weak statistic.
  Room2's per-segment max is 0.27–0.33 m at every length from 1 m upward (median 0.010–0.011 m at 1 m): one short
  stretch with a large error, not steady growth. Not investigated.
- Room1 "max 46.5 ms behind" (`vio_run_health.csv`): it is the FIRST `[TIME]` line of each room1 log (line 1 of 2808/2815/2815;
  46.60, 46.49, 46.49), printed before initialisation (followed by `[init]: not enough feats`). The next lines fall by 5.0 per
  line (41.6, 36.6, … 0.1) and stay around 0.1–1 for the rest of the run.
  What the number is (`ov_msckf/src/ros/ROS2Visualizer.cpp` line ~474): `update_dt = 100.0 * (imu_time - camera_frame_time)`,
  printed as "ms behind". So it is (a) BAG time — how far the newest IMU sample is ahead of the camera frame being processed,
  not wall-clock processing delay — and (b) scaled by 100, not 1000: 46.6 means ≈ 0.466 s, and the 5.0 steps are 50 ms = one
  camera frame at 20 Hz. At start-up about 10 camera frames sat in OpenVINS's queue before the first IMU sample after them arrived,
  and were then processed in about 0.03 s of wall time (sum of the printed `seconds total`).
  The input bags are not the cause: in room1 `/imu0` starts 0.018 s before `/cam0`, with no IMU gap over 5.0 ms or camera gap over
  50.1 ms in the first 3 s (room2: 0.028 s, same gaps). Why OpenVINS saw the IMU about 0.47 s late in room1, and repeatably, is not determined.
  Verdict: start-up only, and the "ms" value is a mislabelled measurement (bag-time queue depth in units of 10 ms), not ongoing lag.
  The `max_ms_behind` column in `vio_run_health.csv` inherits the mislabel; not changed here.
  Room2's maxima (1.59 / 6.47 / 6.39) are single mid-run lines (lines 344, 2676, 2003), i.e. ≈ 16–65 ms of bag time.

### 2026-11-17 — distinct outcomes, room2 worst RPE segment, path lengths, health column relabel
Commands (no OpenVINS rerun): `eval/score_week2_vio.sh` (rescore of the six existing runs; all 6 valid), then
`env -u PYTHONPATH ~/venvs/trn/bin/python eval/check_rpe_segments.py eval/results/vio --runs room2_run1 room2_run2 room2_run3`.
Tests: `eval/test_score_vio.py` 8 passed, `eval/test_check_rpe_segments.py` 3 passed (venv, `env -u PYTHONPATH`),
`eval/test_summarize_vio_runs.py` 4 passed (system python3). All earlier values in `vio_scores.csv`, `vio_runs_summary.csv`
and `*_rpe_vs_delta.csv` unchanged against HEAD; only new columns/rows.
- (1) Byte-identical pose files (`eval/summarize_vio_runs.py` → `eval/results/vio/vio_run_identity.csv`, SHA-256 of
  `<run>_openvins.tum`): room1: run2 = run3, run1 differs; room2: run1 = run3, run2 differs. So 2 distinct outcomes per
  sequence. New `vio_runs_summary_distinct.csv`: mean/std/min/max over one run per outcome (n = 2), e.g. ATE RMSE room1
  0.0647 ± 0.0018 m, room2 0.0822 ± 0.0095 m. Byte-identical outputs still had different health logs (room2_run1 vs run3
  max IMU–camera gap 0.0159 vs 0.0639 s), so callback timing varies between replays without changing the estimate.
- (2) Room2 worst RPE segment (`<run>_rpe_vs_delta.csv` now has `max_seg_*` columns; checked by `eval/check_rpe_segments.py`
  → `eval/results/vio/rpe_max_segment_check.csv`): at EVERY segment length (1–50 m) and in all three runs the worst segment
  is the FIRST one, starting at the first matched pose, stamp 1520530736.6008 (run2: .6003), bag +5.23 s, t_rel 0.001 s.
  The ESTIMATE jumps there: its first step is 0.233 m (run1/3) / 0.307 m (run2) in 0.05 s (4.9 / 6.4 m/s; the estimate's
  whole-run 99.9th percentile is 0.088 m / 1.75 m/s); the next steps are 0.02–0.06 m. This is the first pose after
  OpenVINS initialises. The GROUND TRUTH is clean in that window (no gap: max interval 0.0083 s; max step 0.0094 m).
  Not the cause of the max, but found: room2's ground truth has 25 gaps longer than 5× its median interval, 14.72 s in total
  (estimate: 0), e.g. 2.48 s at stamp 1520530773.50 with a 2.15 m jump across it (from `rpe_max_segment_check.csv`).
  Estimate poses inside those gaps have no ground-truth match (max 0.01 s) and are left out of all scores. Room1's ground
  truth not checked.
  Median RPE added beside RMSE: `vio_scores.csv` `rpe_trans_median_{1,10,50}m`; summaries have median 1 m and 10 m.
  Room2 1 m: RMSE 0.0284 m vs median 0.0101–0.0113 m (the start jump dominates the RMSE).
- (3) Path lengths (matched poses; `vio_scores.csv` `est_length_m`, `gt_length_m`; printed by score_vio.py):
  room1 estimate 145.79 / 145.70 / 145.70 m vs ground truth 145.94 m (0.999, 0.998); room2 141.60 / 141.56 / 141.60 m vs
  140.59 m (1.007). Since RPE segments are measured on the estimate's path, the two lengths differ by under 1 %.
- (4) `vio_run_health.csv`: `max_ms_behind` renamed `max_imu_cam_gap_data_time_s` = printed value / 100, seconds of data
  time (see the OpenVINS formula in the previous entry). room1 0.4660 / 0.4649 / 0.4649 s, room2 0.0159 / 0.0647 / 0.0639 s.

### 2026-11-17 — start-up skip option (--skip-start-s, default 2.0 s)
- `eval/score_vio.py --skip-start-s S` (default 2.0): matched poses earlier than the first ESTIMATED pose (first line of the
  TUM file, before matching) + S are left out of RPE (`vio_scores.csv` RPE columns, `<run>_rpe_vs_delta.csv`) and of the
  start-aligned 4-DoF window (now the first 5 m travelled after the skip). ATE, the SE(3) cross-check and the per-pose
  error-vs-distance rows still cover all matched poses; distance still counts from the first matched pose.
  `vio_scores.csv` gains `skip_start_s`, `skipped_poses`; the settings JSON's `drift_curve_alignment` block gains
  `skip_start_s` (fit_drift_model.py copies that block). `--skip-start-s 0` = earlier behaviour: verified that
  `skip_start_0/vio_scores.csv` matches the previous commit in every old column and `*_rpe_vs_delta.csv` byte for byte.
  Tests: `eval/test_score_vio.py` 10 passed (new: `first_kept_index`, synthetic 0.3 m start jump removed from RPE and
  alignment with skip 2, present with skip 0); `eval/test_check_rpe_segments.py` 4 passed.
- Commands (no OpenVINS rerun): `eval/score_week2_vio.sh` (skip 2.0 → `eval/results/vio/`, all 6 valid, 41 matched poses
  skipped per run), `env -u PYTHONPATH ~/venvs/trn/bin/python eval/compare_skip_start.py eval/results/vio` (skip 0 →
  `eval/results/vio/skip_start_0/`, table → `eval/results/vio/skip_start_comparison.csv`),
  `env -u PYTHONPATH ~/venvs/trn/bin/python eval/check_rpe_segments.py eval/results/vio` → `rpe_max_segment_check.csv`
  (now has the first step of each trajectory).
- Comparison (skip 2 s / skip 0, metres; from `skip_start_comparison.csv`):

  | run | RPE 1 m RMSE | 1 m median | 10 m RMSE | 10 m median | 50 m RMSE | 50 m median | final horiz (start-aligned) |
  |---|---|---|---|---|---|---|---|
  | room1_run1 | 0.0121 / 0.0125 | 0.0100 / 0.0100 | 0.0330 / 0.0352 | 0.0302 / 0.0260 | 0.0880 / 0.0843 | 0.0878 / 0.0843 | 0.1134 / 0.1108 |
  | room1_run2 = run3 | 0.0132 / 0.0131 | 0.0105 / 0.0107 | 0.0319 / 0.0317 | 0.0319 / 0.0310 | 0.0856 / 0.0825 | 0.0855 / 0.0820 | 0.0830 / 0.0862 |
  | room2_run1 = run3 | 0.0158 / 0.0284 | 0.0112 / 0.0113 | 0.0345 / 0.0917 | 0.0284 / 0.0251 | 0.1355 / 0.2077 | 0.1343 / 0.1724 | 0.1707 / 0.1867 |
  | room2_run2 | 0.0147 / 0.0284 | 0.0101 / 0.0101 | 0.0326 / 0.0827 | 0.0320 / 0.0326 | 0.1201 / 0.2153 | 0.1131 / 0.1895 | 0.0659 / 0.0721 |

  Room2: the skip removes the start jump; RPE RMSE drops by about half at 1 m and by over half at 10 m, while medians barely
  move. Room1: changes are small and go both ways (shifting the start moves the segment boundaries; 50 m has only 2 segments).
- Room1 first step after initialisation (estimate pose 1 → 2; `rpe_max_segment_check.csv`): run1 0.0415 m in 0.049 s
  (0.85 m/s, 1.54°), run2/run3 0.0303 m in 0.050 s (0.61 m/s, 2.21°), at stamp 1520530314.80 (bag +6.6 s). The estimate's
  whole-run 99.9th percentile is 0.123 m / 2.46 m/s / 10.5°, so room1 has NO start jump (room2: 0.23–0.31 m, 4.9–6.4 m/s).
- Room1 ground truth: 14 gaps longer than 5× its median interval (0.0083 s), 2.99 s in total (room2: 25 gaps, 14.72 s).
  Estimate poses inside the gaps have no ground-truth match and are left out of all scores.

### 2026-11-18 — drift model, step 1: look at the data (plot only; the fit is the user's)
- Guidance received for `eval/fit_drift_model.py` (log-log look, two candidate models, curve_fit on δ ≤ 20 m, compare residuals,
  drift_params.json + plot). Per CLAUDE.md rule 7 / Week 2 brief the user writes the fit (models, curve_fit, model choice);
  the assistant did the plot and input/output scaffolding only. `eval/fit_drift_model.py` NOT created.
- New `eval/drift_data.py` (helpers: `distinct_runs`, `load_rpe_points(max_delta_m=...)`, `scoring_settings` (alignment
  block incl. skip_start_s, RPE segment definition), `local_loglog_slopes`, `plot_rpe_vs_delta(fits=...)`); tests
  `eval/test_drift_data.py` 5 passed. New `eval/plot_rpe_vs_delta.py`.
- Command: `env -u PYTHONPATH ~/venvs/trn/bin/python eval/plot_rpe_vs_delta.py eval/results/vio` →
  `eval/results/vio/rpe_vs_delta_loglog.png`, `eval/results/vio/rpe_vs_delta_local_slopes.csv`. Inputs: the 4 distinct runs
  (room1_run1, room1_run2, room2_run1, room2_run2), `*_rpe_vs_delta.csv` scored with skip_start_s = 2.0.
- Local log-log slopes of RMSE (1-2, 2-5, 5-10, 10-20, 20-50 m): room1_run1 0.52 0.47 0.32 0.56 0.65; room1_run2 0.53 0.33
  0.32 0.67 0.57; room2_run1 0.76 0.17 0.14 0.71 0.96; room2_run2 0.80 0.25 0.01 0.38 1.14. Not a single straight line:
  flattens between 2 and 10 m (strongly in room2), steepens again above 10 m. The 50 m points rest on 2 segments each.

### 2026-11-18 — drift model fit (`eval/fit_drift_model.py`)
- User decision 2026-11-18: "write the fit_drift_model.py yourself" — the assistant wrote the fit script (explicit
  exception to CLAUDE.md rule 7 for this script only).
- Method: distinct runs (room1_run1, room1_run2, room2_run1, room2_run2), segment lengths <= 20 m (1, 2, 5, 10, 20), pooled,
  20 points, RPE scored with skip_start_s = 2.0. Models: power e = c·δ^p; three-term e = sqrt(a² + b·δ + (c·δ)²).
  `scipy.optimize.curve_fit` on e, all parameters >= 0 (p <= 2), weights sigma = e / sqrt(2 n_segments) (relative).
  Compared by weighted chi2, AICc, RMS log residual, and leave-one-sequence-out RMS log residual (fit on one room, test
  on the other). Rule: keep the power law unless three-term AICc is lower by > 2 AND its held-out residual is lower.
  Tests: `eval/test_fit_drift_model.py` 5 passed (synthetic power law recovered and kept; floor + linear growth picks
  three-term; bounds; held-out output; AICc), `eval/test_drift_data.py` 5 passed.
- Command: `env -u PYTHONPATH ~/venvs/trn/bin/python eval/fit_drift_model.py eval/results/vio` →
  `eval/results/vio/drift_params.json`, `eval/results/vio/drift_fit.png`.
- Result: power c = 0.01401 ± 0.00056 m^(1-p), p = 0.4214 ± 0.040; chi2 38.54, AICc 17.82, RMS log residual 0.144,
  held-out room1 0.177 / room2 0.232 / pooled 0.207.
  Three-term a = 0.00719 ± 0.0036 m, b = 0.000143 ± 0.000047 m, c = 0 (at its lower bound; standard error not meaningful,
  flagged in the JSON): it reduces to a noise floor plus random-walk growth; chi2 42.27, AICc 22.47, RMS log residual 0.161,
  held-out pooled 0.220.
  Chosen: power ("AICc difference -4.6 (power minus three-term; needs > 2); held-out-sequence RMS log residual 0.220
  three-term vs 0.207 power").
- Caveats: two indoor sequences, < 150 m each; δ is path length along the estimate's path; the 50 m points (2 segments each,
  not fitted) lie above both curves, especially room2 (0.12–0.14 m vs about 0.07 m from the power law), so extrapolating
  past 20 m is untested and likely optimistic; the 2–10 m flattening (possibly loop geometry) is not modelled.

### 2026-11-18 — noise-plus-random-walk refit and fit sensitivity
- `eval/fit_drift_model.py`: new model `floorwalk` e = sqrt(a² + b·δ) (three-term with c fixed at 0; a [m], b [m]).
  All models fitted to the same n = 20 points (asserted), so AICc is comparable; drift_params.json gains `n_points` and
  `aicc_minus_power` per model, a `note` (the power law describes the indoor data and is not the generator for week 6),
  and `sensitivity_power`. Selection generalised: power unless another model has AICc lower by > 2 AND a lower held-out
  residual. AICc now returns -inf for an exact fit (chi2 = 0, synthetic tests only) instead of a log(0) warning.
  Tests: `eval/test_fit_drift_model.py` 9 passed; all eval tests: 28 (venv) + 4 (system python) passed.
- Command: `env -u PYTHONPATH ~/venvs/trn/bin/python eval/fit_drift_model.py eval/results/vio` →
  `eval/results/vio/drift_params.json`, `eval/results/vio/drift_fit.png`.
- floorwalk: a = 0.00719 ± 0.0023 m, b = 0.000143 ± 0.000024 m (identical values to the three-term fit, whose c was at 0;
  the curves coincide on the plot). n = 20, chi2 42.27, AICc 19.67 vs power 17.82 (+1.85; three-term +4.64).
  Held-out RMS log residual 0.220 vs power 0.207. Power law kept (floorwalk worse on both, not just "not clearly better").
- Power-law sensitivity (`sensitivity_power` in drift_params.json):

  | variant | n | c [m^(1-p)] | p |
  |---|---|---|---|
  | baseline (segment weights, all runs) | 20 | 0.01401 ± 0.00056 | 0.421 ± 0.040 |
  | equal weights per point | 20 | 0.01510 ± 0.00125 | 0.385 ± 0.034 |
  | without room1_run1 | 15 | 0.01492 ± 0.00067 | 0.403 ± 0.045 |
  | without room1_run2 | 15 | 0.01425 ± 0.00076 | 0.424 ± 0.053 |
  | without room2_run1 | 15 | 0.01346 ± 0.00053 | 0.426 ± 0.039 |
  | without room2_run2 | 15 | 0.01361 ± 0.00061 | 0.430 ± 0.045 |

  p stays within 0.385–0.430 and c within 0.0135–0.0151 across variants, i.e. inside about one standard error of the
  baseline for p; equal weights move p most (lower slope, the short-segment points lose weight).

## Week 3 — map side and data loader

### 2026-11-18 — start; UAV-VisLoc record and README
- Tagged `week2-done` on a041131.
- Zenodo record 19603534 (API read, a few KB): "UAV-VisLoc: A Large-scale UAV Dataset with Continuous Trajectories for
  Visual Geo-localization", v1.0, published 2026-05-18, DOI 10.5281/zenodo.19603534. 30 flight zips 01–30 (16 MB to
  86.8 GB, 196.8 GB in total), gt.json (7 MB), README.md, processing scripts, model code. 21 real flights in China and
  9 synthetic flights built from OpenAerialMap imagery outside China (record description).
- README (fetched, 7,096 bytes, MD5 f051069e03feb4299a7d4a6e51fda1f2, matches the record):
  - Map imagery IS included: each flight has `satellite-tile/` (JPG chips cut from Google Earth Pro imagery) and
    `XX-satellite-tile-coordinates.csv`. The original large maps/GeoTIFFs are not included. So no other map source needed.
  - `XX-UAV-coordinates.csv`: "acquisition time, geographic coordinates, flight altitude, and camera shooting angle".
  - Licence: the record's licence field is EMPTY (API `license`: none) and the README defers to it; the satellite chips are
    also subject to Google Earth/Maps terms and attribution. Treated as academic use only, no redistribution (as CLAUDE.md).
- Which zip covers which region is not in the README; it is in each zip's coordinate CSV. New
  `eval/visloc_remote_index.py` reads only each zip's central directory, the two CSVs and the first bytes of one image of
  each kind via HTTP range requests (checked: HTTP 206 supported), 1 s pause, stop on 429/403; saves the CSVs and
  `flight_index.csv` to `~/data/visloc/index/` (not committed). About 4–7 requests and 1–3.5 MB per flight.
- Flights 01–17 indexed (from `~/data/visloc/index/flight_index.csv` and the CSVs):
  UAV CSV columns for 01–06 and 08–17: filename, num, date, lat, lon, height, Omega, Kappa, Phi1, Phi2, attr_1..3;
  flight 07 has only filename, lat, lon, date, time, height (no orientation). Satellite CSV: patchname (row_col in pixels
  of the original map), latitude, longitude — one point per chip; whether it is the chip's corner or centre is not stated.
  Flight 07: 270 px chips at a 135 px stride (50 % overlap).
  Mean positions: 01/02 29.74–29.77 N 116.0 E; 03/04 32.2–32.3 N 119.9 E; 05 24.66 N 102.35 E (height ~2,310 m);
  06 32.36 N 109.65 E; 07/10 40.34 N 115.79 E; 08/09/16/17 30.9 N 120.1–120.2 E; 11 38.83 N 101.05 E (height
  1,971–2,575 m); 12–15 30.2 N 116.9 E.
- FAILED at flight 18 (`/usr/bin/python3 eval/visloc_remote_index.py`): `http.client.IncompleteRead(253148 bytes read,
  8996 more expected)` while reading the first bytes of a satellite chip — the server closed one range response early.
  Not an HTTP 429/403. Stopped per instruction (a step failed); no retry, nothing downloaded beyond the index reads.

### 2026-11-18 — all 30 flights indexed; licence and terms (quoted exactly)
- `eval/visloc_remote_index.py` now retries transient errors (IncompleteRead, timeouts, dropped connections) up to
  3 tries with 5 s / 10 s pauses, still stops at once on HTTP 429/403. Resumed with
  `/usr/bin/python3 eval/visloc_remote_index.py --flights 18 19 ... 30`: all 13 indexed, 0 retries needed;
  `~/data/visloc/index/flight_index.csv` now has all 30 flights.
- Zenodo record 19603534 licence field (API `metadata.license`): absent. `access_right`: open.
- README.md (MD5 f051069e03feb4299a7d4a6e51fda1f2), section "Imagery Source and Terms of Use", verbatim:

```text
## Imagery Source and Terms of Use

The satellite reference image chips in this dataset were generated from
high-resolution satellite imagery obtained from Google Earth Pro.

The released satellite reference images are cropped JPG image chips for UAV
visual localization benchmarking. The original large satellite maps / GeoTIFF
files are not redistributed in this dataset.

The satellite reference image chips are provided for academic research on UAV
visual localization. They are not intended to be used as a map service, tile
service, navigation product, or substitute for Google Earth, Google Maps, or
other original imagery services.

Users are responsible for ensuring that their use of the satellite imagery
complies with the applicable third-party terms, licenses, and attribution
requirements. The use of imagery obtained from Google Earth Pro should comply
with the Google Earth / Google Maps terms and conditions.

If required, users should provide appropriate attribution to Google Earth and
the relevant third-party imagery providers.
```

- Same README, section "License", verbatim:

```text
## License

Please refer to the license information provided on the Zenodo dataset page.

Unless otherwise stated, the annotations, metadata, ground-truth files,
preprocessing scripts, and model code are provided under the license selected
on the Zenodo dataset page.

The satellite reference image chips were generated from high-resolution
satellite imagery obtained from Google Earth Pro. These image chips may contain
content from Google Earth / Google Maps and third-party imagery providers.
Their use may be subject to Google Earth / Google Maps terms and conditions,
attribution requirements, and applicable third-party imagery provider terms.

The license selected for this Zenodo record does not grant additional rights to
Google Earth / Google Maps imagery or third-party imagery beyond those
applicable terms. Users are responsible for ensuring that their use of the
satellite reference image chips complies with the relevant third-party terms,
licenses, and attribution requirements.
```

- Reading: no licence is selected on the record, so the record grants no explicit licence; the satellite chips are
  additionally under Google Earth/Maps terms. Handling: academic research use only, nothing redistributed (no images,
  chips, overlays or samples in git: .gitignore), attribute Google Earth and the dataset authors (DOI
  10.5281/zenodo.19603534) in anything shown.

### 2026-11-18 — region choice, downloads started, what is in the data
- Regions (user rule: an easy plains/urban area, a mountainous one, an arid one; whole regions per split; ≤ 5 GB):
  | role | region | flights | zip size |
  |---|---|---|---|
  | tune (week 4 matcher) | jiangsu_wuxi, Jiangyin–Wuxi, 31.96 N 120.38 E | 18, 19, 20 | 0.199 + 0.265 + 0.248 GB |
  | calibrate (week 5) | yunnan, 24.66 N 102.35 E | 05 | 0.601 GB |
  | test (final, untouched) | gansu, Zhangye area, 38.83 N 101.05 E | 11 | 3.491 GB |
  Total 4.80 GB (limit 5 GB). All real flights (not the synthetic 22–30). Terrain labels are what the location suggests;
  checked against the images below.
- `eval/visloc_download.py 05 18 19 20 11` (detached, log `~/data/visloc/download.log`): refuses > 5 GB, one file at a
  time, ≤ 20 MB/s, resumes partial files, ≤ 3 tries on transient errors, stops on 429/403, checks MD5 against the record,
  extracts with a path-traversal check to `~/data/visloc/flights/XX/`. Server speed varied 0.25–3 MB/s.
- Processing scripts zip (9,816 bytes, MD5 67ee5a87a73d98f8514d52da4e43d42a; read, not run) settles two questions:
  - Chip coordinates (`satellite_tile_generation.py`): the CSV lat/lon is the chip CENTRE, computed linearly in lat/lon
    from the map's top-left and bottom-right corners; chip names are `<row>_<col>` = top-left pixel in the full map
    (stride = half the chip size). So the chips can be put back together into a georeferenced map exactly.
  - Their ground truth (`groundtruth_generation.py`) is only "chip centre within a distance threshold"; no footprint.
- What the real files look like (found while running the loader; both handled in code, with tests):
  - Chip files have a prefix the CSV lacks: CSV `0_620.jpg`, file `satellite05_0_620.jpg` → match by (row, col).
  - UAV image names differ in case: CSV `18_0001.JPG`, file `18_0001.jpg` → match ignoring case.
  - UAV images have NO EXIF (no camera model, focal length) and are square (05: 1414 px; 18: 1876 px).
  - Heading column differs by flight: 05 and 11 have Omega/Kappa/Phi1/Phi2; Phi2 follows the direction of travel
    (median difference 0.8° / 0.7°); 18–20 have only Phi1 (others '-'), which follows travel within 0.2–0.5°. Degrees
    clockwise from north. The loader takes Phi2 if complete, else Phi1.
  - The STORED IMAGES ARE ALREADY NORTH-UP (the authors rotated them): flight 05 images match the north-up map as stored,
    and rotating them by the heading breaks the match (checked visually on 05_0002 and 05_0101); the consecutive-image
    check below gives a rotation near 0 whichever way the drone flies. So the heading is NOT applied to footprints.
  - `height` is not documented as above sea level or above ground: 05 reads ~2,310 m on a ~1,900 m plateau, 18–20 read
    ~167 m near sea level. Not used for positions.

### 2026-11-18 — frames and units (week 3 acceptance item)
- Geodetic input: WGS84 latitude/longitude in degrees (dataset CSVs; satellite map corners).
- Map pixels: the dataset's satellite maps are plain lat/lon grids. Pixel coordinates (row down, col right) are continuous
  with integer values on pixel EDGES; lat = lat0 + dlat_drow·row, lon = lon0 + dlon_dcol·col (fitted per map).
- Local frame: one ENU frame per region, tangent to WGS84 at the region's `enu_origin` in `eval/splits.json` (centre of
  the bounding box of its chip centres, rounded to 1e-5°). x = east, y = north, z = up, metres. Exact conversion via ECEF
  (`trn_matcher/geo.py`). All loader positions (true, prior, patch centre) are (east, north) in metres in this frame.
- Map patches: north-up squares, row 0 = north, column 0 = west, side `size_m` metres, `px` pixels.
- Heading: degrees clockwise from north (dataset Phi2/Phi1). Prior error: metres, per axis (east, north).

### 2026-11-18 — tile store and loader, function by function (assistant wrote them at the user's request)
`src/trn_matcher/trn_matcher/geo.py` — converting between lat/lon and metres.
- `geodetic_to_ecef(lat, lon, h)`: turns a lat/lon/height on the WGS84 ellipsoid into a 3-D point (x, y, z) in metres
  measured from the Earth's centre. Uses the standard ellipsoid formulas; works on single values or whole arrays.
- `ecef_to_geodetic(x, y, z)`: the reverse. Longitude comes straight from atan2(y, x); latitude and height need a few
  rounds of refinement because the Earth is not a sphere; five rounds is far more than enough (sub-millimetre).
- `LocalENU(origin_lat, origin_lon)`: a flat "local map" laid on the Earth at the origin point, with x pointing east,
  y north, z up, in metres. The constructor stores the origin's 3-D point and the three direction vectors (east, north,
  up) at that spot.
- `LocalENU.to_enu(lat, lon, h)`: converts lat/lon to the 3-D point, subtracts the origin, and measures how far that
  offset goes along east, north and up. Result: metres east and north of the origin.
- `LocalENU.to_geodetic(e, n, u)`: the reverse: builds the 3-D point from the east/north/up offsets and converts it back
  to lat/lon. Round trip is exact to well below a millimetre (tested).

`src/trn_matcher/trn_matcher/tile_store.py` — the map, rebuilt from the dataset's overlapping chips.
- `Georef`: the rule linking map pixels to lat/lon for one map: latitude changes by a fixed amount per pixel row,
  longitude by a fixed amount per pixel column. `pixel_to_latlon` and `latlon_to_pixel` apply that rule in each direction.
- `Chip`: one chip file, where its top-left corner sits in the full map (row0, col0), and its centre lat/lon from the CSV.
- `fit_georef(chips, chip_h, chip_w)`: works out the Georef rule from the chips themselves: for every chip it knows the
  pixel position of the chip's centre and that centre's lat/lon, and fits a straight line through them (one for rows vs
  latitude, one for columns vs longitude). The largest leftover error is kept as a check (1.5e-13° for flight 05, i.e.
  only rounding).
- `read_chip_csv(csv, chip_dir)`: reads the chip list. Names in the CSV and on disk can differ by a prefix, so it pairs
  them by the two numbers in the name (row, col), and stops with an error if a listed chip has no file.
- `TileStore(...)`: one flight's map. Keeps the chips indexed by their top-left pixel, fits the Georef, and notes how far
  the chips reach (the far right/bottom edge of the original map may have no chip).
- `TileStore.from_flight_dir(dir)`: builds the above from a flight folder; reads the first chip only to learn the size.
- `TileStore._chip_pixels(key)`: opens and decodes one chip, keeping the 64 most recently used in memory so neighbouring
  requests do not re-read the same files.
- `TileStore.read_window(row0, col0, h, w)`: cuts a rectangle of the full map: starts from a black image, and for every
  chip that overlaps the rectangle copies the overlapping part in. A second array marks which pixels a chip actually
  covered, so "no map here" is never mistaken for black ground.
- `TileStore.coverage_fraction(rows, cols)`: what share of a set of pixel positions lies inside the area the chips cover;
  used to pick between maps.
- `TileStore.sample(rows, cols)`: reads the map at arbitrary (fractional) pixel positions: fetches the small window that
  contains them, then mixes the four surrounding pixels in proportion to how close each is (bilinear interpolation). A
  position is valid only if all four pixels exist.
- `MapPatch`: what `map_patch` returns: the image, the valid mask, its centre (east, north), side length, metres per
  pixel, and which flight's map it came from.
- `RegionMap(stores, frame)`: all maps of one region plus the region's ENU frame.
- `RegionMap._pixel_grid(...)`: lays a square grid of points over the ground (north at the top), converts each point
  from metres to lat/lon to map pixel position.
- `RegionMap.map_patch(position, size_m, px)`: the function the brief asks for. For every map in the region it computes
  that grid and how much of it the map covers, takes the map that covers most, and samples it. Result: a north-up square
  of `size_m` metres centred on `position`, `px` × `px` pixels.

`src/trn_matcher/trn_matcher/loader.py` — the samples.
- `UavRecord`: one aerial image: flight, file, lat, lon, height, heading and which column the heading came from.
- `_num(value)`: turns a CSV cell into a number, or "missing" for '-' or blank.
- `read_uav_records(flight_dir)`: reads the flight's UAV CSV; picks the heading column (Phi2 if every row has a number,
  else Phi1, else error); matches CSV names to files ignoring upper/lower case; stops with an error if any image is missing.
- `LoaderConfig`: the knobs: prior error (sigma, metres per axis), map patch size (metres) and resolution, aerial image
  size, random seed, and whether the patch is centred on the prior (default) or on the truth.
- `Sample`: one item: image, true position, map patch, prior position, plus the record and region. `as_tuple()` gives
  exactly (image, true_position, map_patch, prior_position).
- `load_splits(path)`: reads splits.json.
- `VisLocDataset(root, splits, split, config)`: for each region in the chosen split, makes the region's ENU frame from
  splits.json, builds a TileStore per flight, and lists every aerial image. It never opens flights of other splits.
- `__len__`: number of aerial images in the split.
- `true_position(i)`: the image's lat/lon from the CSV converted to (east, north) metres in its region's frame.
- `prior_position(i)`: true position plus a random error drawn from a normal distribution with the configured sigma on
  each axis. The random generator is seeded from (seed, flight, file name), so an image always gets the same prior for a
  given seed, and changing the seed gives a new set.
- `load_image(i)`: opens the aerial image as RGB and shrinks it to the configured size (long side).
- `__getitem__(i)`: puts it together: true and prior positions, the map patch around the prior (or the truth if
  configured), the image, and the prior error in metres as extra information.

### 2026-11-18 — first overlays; tune region is thermal infrared → stopped to ask
- Downloads so far (`~/data/visloc/download.log`): 05 600,568,121 B MD5 12346ad958df3bb372e98916b68d1ea6; 18 199,351,774 B
  MD5 cd024e2929612015e1f0d0f0e125b9d4; 19 264,849,047 B MD5 f499e866cc2832b6b4971ed7ae05dfeb; 20 248,240,985 B
  MD5 2978179cebb0e7e22633e7ffff0dd695 — all match the record, extracted. 11 (3.49 GB) still downloading (~0.85 MB/s).
- Footprint size: no camera data and no EXIF. `eval/estimate_uav_scale.py` (phase correlation of consecutive UAV images +
  GPS displacement, no map involved) works only on some pairs (consecutive frames shift ~40 % of the image, relief):
  `/usr/bin/python3 eval/estimate_uav_scale.py ~/data/visloc/flights 05 18` → `eval/results/week3/uav_scale.csv`:
  05 0.137 m/px (p10–p90 0.103–0.193, 30/60 pairs), rotation −5.5° median; 18 0.0208 m/px (5/60 pairs), rotation −3.8°.
  Where it works it agrees with the satellite chip ground size (18: 39.0 vs 38.8 m; 05: ~190 vs ~180 m), i.e. the
  authors sized chips to the image footprint. Overlays use the chip ground size (mean of N–S and E–W sides, since map
  pixels are 0.299 m N–S × 0.253 m E–W at 32° N) as the footprint; the image-pair estimate is printed as a cross-check.
  Rotation stays near 0 regardless of heading (18: −3 to −6° at headings 153° and 333°) → images stored north-up.
- `/usr/bin/python3 eval/make_overlays.py --split tune --split calibrate` → 8 overlays (git-ignored), checked by eye:
  - 05 (Yunnan, RGB): road, slope and forest edge line up between image and map at the same scale. Looks right.
  - 18/19/20 (Jiangsu): the UAV images are THERMAL INFRARED (false-colour palette), not RGB. The dataset README says
    "RGB and Infrared UAV imagery" but the metadata does not mark which flights. Geometry is plausible where features
    are clear (18_0204: canal direction and width ~23–25 m agree, offset ~8 m; 19_0118: diagonal road and roof rows
    agree), but harder to confirm in 18_0102, 19_0235, 20_0234 (possible offset 10–15 m).
  - This breaks the region choice: Jiangsu was picked as the EASY region for tuning the matcher, but thermal-to-RGB-map
    matching is a hard cross-modal problem, while calibrate (05) and test (11) are RGB.
- Candidates checked for modality (one mid-flight image each via range reads, ~1–2 MB per flight, nothing downloaded):
  06, 10, 07, 22, 23, 27 and 11 are all RGB. 11 is visibly arid (dry ground, grid fields) — confirms the test label.
  10 (40.35 N 115.79 E, near Beijing) is flat RGB farmland, 144 images, 0.144 GB: total would be 4.94 GB (≤ 5 GB, no
  deletion needed). 07 (RGB village, same area) is unusable here: its chip grid is a single row (map height 170 px), so
  the map cannot be georeferenced from chip centres.
- Stopped per instruction ("something looks wrong in the overlays"); asked the user which tune region to use.

### 2026-11-18/19 — user decision: flight 10 as tune region; Jiangsu excluded
- User decision 2026-11-18: tune = flight 10 (option 1). Downloaded `/usr/bin/python3 -u eval/visloc_download.py 10`:
  143,528,824 B, MD5 be11691d0993ab6db537b6aa8d674fee = record, extracted. Ran alongside the flight 11 download (one extra
  connection for 107 s; noted because the downloader's own rule is one file at a time). Total on disk with 11: 4.95 GB.
- Modality check BEFORE building the split (trial split in the scratchpad, `make_overlays.py --split tune`): flight 10
  overlays 10_0049 and 10_0097 are RGB (natural-colour farmland, roads, a hut) — not thermal. Geometry plausible: in
  10_0097 the road junction, hut and diagonal road appear in image and map at the same scale, image shifted ~15–20 m.
- `eval/splits.json` rebuilt (`/usr/bin/python3 eval/make_splits.py`): tune = hebei_huailai (flight 10, ENU origin
  [coordinate removed] N [coordinate removed] E), calibrate = yunnan (05, [coordinate removed] N [coordinate removed] E), test = gansu (11, [coordinate removed] N [coordinate removed] E).
  Whole regions only. `/usr/bin/python3 eval/check_splits.py --data ~/data/visloc/index` → "no leakage: tune 1,
  calibrate 1, test 1 flights per split (geographic check included)": no flight in two splits, maps of different splits
  do not overlap, closest UAV positions of different splits ≥ 10 km apart.
- **Jiangsu flights 18, 19, 20: thermal infrared, excluded from tune/calibrate/test, reserved as a cross-modal stress
  test.** Kept on disk (`~/data/visloc/flights/18..20`), listed under `excluded_regions` in splits.json; the leakage check
  now also fails if any excluded flight appears in a split. The modality was found from the overlays (2026-11-18); the
  dataset metadata does not say which flights are thermal (README only: "RGB and Infrared UAV imagery").
- **Tune set is small: 144 images (one flight).** The week 4 matcher should therefore have only a few tunable settings
  (e.g. a handful of thresholds/sizes), otherwise it will overfit flight 10 and the calibration/test numbers will not
  transfer.
- 2026-11-19 17:28: WSL had restarted (uptime 0 min), killing the detached flight 11 download at 2,881,957,888 of
  3,491,364,359 bytes (.part file intact). Resumed with the same script (`eval/visloc_download.py 11`, HTTP Range resume, MD5
  checked on the whole file) — designed behaviour, not a fix.

### 2026-11-19 — flight 11 done, final overlays, landmark offsets, tests, data table
- Flight 11 finished 17:34: 3,491,364,359 B in 319 s after the resume, `11: MD5 ok (97da09cc7aef00c35fa086425b4d2ac5),
  extracted 1745 members` (`~/data/visloc/download.log`). 590 images, 1150 chips in `~/data/visloc/flights/11/`.
- Split-test fix (before the final run): `test_check_splits.py::test_flight_in_two_regions` still added flight 18, which
  is now excluded; changed it to add flight 10 to gansu, and added `test_excluded_flight_in_a_split_is_caught` (adds 19).
- Earlier overlays moved (not deleted) to `eval/results/week3/overlays/excluded_jiangsu_thermal/` (18/19/20) and
  `overlays/earlier_trial/` (05_0158, 10_0049, 10_0097), so the top folder holds only the final 10.
- Footprint cross-check rerun: `/usr/bin/python3 eval/estimate_uav_scale.py ~/data/visloc/flights 05 10 11 18` →
  `eval/results/week3/uav_scale.csv` (+ `uav_scale_pairs.csv`). Image-pair footprint estimate vs chip ground size
  (printed by make_overlays): 05 193.5 vs 177 m (30/60 pairs), 10 146.3 vs 124 m (12/60), 11 346.8 vs 329 m (52/60),
  18 39.0 vs 38.8 m (5/60). For the three RGB flights the estimate is 5–18 % larger than the chip size, always in the same
  direction. Open question for week 4: either the chips are a little smaller than the image footprint, or the estimate is
  biased high. Overlays keep using the chip ground size.
- Final overlays: `/usr/bin/python3 eval/make_overlays.py --count 10=4 --count 05=3 --count 11=3` → 10 PNGs in
  `eval/results/week3/overlays/` (git-ignored) + `eval/results/week3/overlay_index.csv`. Footprints 124 m (10), 177 m
  (05), 329 m (11). Map valid fraction 1.00 except 05_0355 (0.84: crop runs past the east edge of flight 05's map).
- Checked by eye:
  - Modality: flights 10, 05 and 11 are all RGB (11: arid valley with highway, irrigated plots, dry riverbed).
  - Every image lands in the right area of the map: same roads, fields and buildings, same scale.
  - Maps from another date or season: flight 10's maps are hazy winter imagery; in 05_0237 the map shows a bare patch
    that the image does not; in 11_0296 the crop plots changed. Flight 11's map has a visible seam between two source
    images (11_0148).
  - Small rotation: in 10_0058, 10_0087, 10_0116 and 05_0119, roads and field edges run at a slightly different angle in
    the image than on the map (a few degrees; not measured). It fits the noisy rotation in uav_scale.csv (10: median −7.9°,
    p10–p90 −21° to +15°). The images are north-up only to within a few degrees, so the week 4 matcher must tolerate
    that.
  - Not treated as a stop: none of this is a georeferencing error in the tile store or loader, and the offsets below are
    well inside the loader's 50 m prior sigma.
- Overlay offsets (how far the image centre's true ground position is from the dataset position, measured on the map):
  - Step 1: `python3 eval/overlay_offsets.py grid` writes `overlays/grid_*.png` (git-ignored).
  - Step 2: landmarks picked BY EYE on those grids (Claude, 2026-11-19) into `eval/results/week3/overlay_landmarks.csv`,
    with a quality label (good/fair/weak) and a note for each. No landmark could be matched in 10_0029, 05_0237 or
    11_0148; those are listed with empty coordinates.
  - Step 3: `python3 eval/overlay_offsets.py compute` → `eval/results/week3/overlay_offsets.csv`.
  - Per overlay (east, north; |offset|):

    | Overlay | East | North | |offset| | Landmarks |
    |---|---|---|---|---|
    | 05_0119 | −9.9 m | −2.2 m | 10.2 m | 2, weak |
    | 05_0355 | −10.2 m | +7.5 m | 12.6 m | 2 |
    | 10_0058 | −7.3 m | +15.2 m | 16.9 m | 3 |
    | 10_0087 | +1.5 m | +8.7 m | 8.8 m | 1, weak |
    | 10_0116 | −12.4 m | −12.8 m | 17.8 m | 2 |
    | 11_0296 | +2.5 m | −20.6 m | 20.7 m | 1, weak |
    | 11_0443 | +14.0 m | −37.5 m | 40.0 m | 2 |

  - Per flight, mean |offset| (max): 05 11.4 m (12.6), 10 14.5 m (17.8), 11 30.4 m (40.0). The signed means are 05
    (−10.0, +2.7), 10 (−6.0, +3.7), 11 (+8.2, −29.0) m. Flight 10's directions vary between overlays, so its signed
    mean is smaller than its typical offset.
  - Precision: about ±10 panel px per landmark = ±3 m (10), ±4 m (05), ±8 m (11). The picks ignore the small rotation.
    2–3 overlays per flight is far too few for a per-flight bias estimate. Read these as "offsets of 10–40 m exist
    between the dataset positions and the Google Earth map", not as calibrated numbers.
- Tests:
  - `env -u PYTHONPATH ~/venvs/trn/bin/python -m pytest -q .` (eval/): 54 passed, 0 skipped. The real-data tests in
    `test_visloc_real.py` now run on 10, 05 and 11: georef residual, all UAV positions inside the map, one sample per
    flight.
  - `/usr/bin/python3 -m pytest -q test_summarize_vio_runs.py test_visloc_real.py test_check_splits.py`: 20 passed.
  - `src/trn_matcher`, ROS sourced, `python3 -m pytest -q test/`: 21 passed, 1 skipped (template copyright check). ament
    flake8 and pep257 are clean.
  - `test_overlay_offsets.py` (2 tests) covers the metre conversion, and that an overlay with no landmark is listed but
    not averaged.
- Leakage check on the extracted data: `python3 eval/check_splits.py --data ~/data/visloc/flights` → "no leakage ...
  (geographic check included)". The same result as with `--data ~/data/visloc/index`.
- `data/README.md`: UAV-VisLoc table filled in (6 zips, bytes, MD5 = record, local paths). Total 4,947,903,110 B.

## Week 4 — terrain matcher: harness and floor (executor scope: scaffolding only)

### 2026-11-19 — scope and decisions
- Akhil's instructions (2026-11-19), in addition to the week 4 brief:
  - The executor scaffolds only. The matcher itself is Akhil's.
  - The harness calls `match(image, map_patch, prior) -> (x, y, scale, rot_deg, score) or None`.
  - Results are reported per flight, never pooled across splits.
  - Run only on tune (flight 10). Test (flight 11) stays untouched until Akhil says so.
  - Two floor baselines: return the prior, and a random point in the search window.
  - Add a label-offset diagnostic. It is diagnostic only and never applied to scores.
  - Every error table shows the floor next to it and the 15 m note.
  - Search space: scale ratio 0.8–1.3, rotation ±5°.
  - Do not touch `height` or the thermal flights.
- Interface (`src/trn_matcher/trn_matcher/interface.py`), conventions chosen by the executor (Akhil can change them):
  - `x, y`: east, north [m] of the image centre's ground position, in the region ENU frame (same frame as the labels).
  - `scale`: estimated image ground size / `prior.footprint_m`. The nominal footprint is the chip ground size, which
    is the scale prior.
  - `rot_deg`: direction the image's up axis points, clockwise from north.
  - `score`: larger means more confident, on any scale.
  - Return a `MatchResult(..., diag={...})` to have diagnostics (inliers, residual, ...) written to the per-frame CSV.
    A plain 5-tuple also works.
  - The search space is the 4th argument, with a default, so the 3-argument call still works.
  - `Prior` = (east, north, sigma_m, footprint_m).
  - Pixel ↔ ENU helpers for the map patch use the tile store's convention (row 0 north, pixel edges at integers).
- Search window: ±150 m square around the prior, which is 3 × the loader's 50 m prior sigma. The map patch is centred
  on the prior and sized to hold the image anywhere in the search space: `2·150 + footprint·1.3·(cos 5° + sin 5°)`.
  That is 474 m for flight 10, cut at 0.5 m/px (949 px). The aerial image is resized to 1024 px.
  - These are harness defaults (`--window-m`, `--map-m-per-px`, `--image-px`), not matcher settings.
- Baselines (`trn_matcher/baselines.py`):
  - `prior` returns the prior. Against the labels its error is the prior noise; against the true ground position it
    would be prior noise plus the label offset.
  - `random` returns a uniform pose in the search space, seeded per frame.
- `trn_matcher/matcher.py` is a signature-only stub (`FeatureMatcher.match` raises NotImplementedError) for Akhil to
  fill.
- `TileStore.chip_ground_size_m()` now holds the footprint rule; it moved there from `make_overlays.py`, which now
  calls it.
- A pose outside the search space, or with non-finite values, counts as no fix (`outside_search` / `invalid`).
  Matcher exceptions stop the run.

### Label registration error and its three consequences
The labels are the dataset's GPS positions (`UAV-coordinates.csv`). The map is Google Earth imagery, registered
independently. Week 3 measured, by eye on 7 overlays, offsets of 9–40 m between where the map puts an image and its
label:
- flight 05: mean 11 m;
- flight 10: mean 15 m;
- flight 11: mean 30 m, up to 40 m.

The source is `eval/results/week3/overlay_offsets.csv`. This label registration error is part of every error we
report, so:
1. **Error floor.** A perfect matcher would still show about 10–40 m error against the labels. Errors below about
   15 m are not distinguishable from label registration error, so differences between methods below that level mean
   nothing. Every error table therefore states this and shows the prior/random floor next to it
   (`eval/matcher_report.py` refuses a table without both baselines).
2. **Calibration mismatch between 05 and 11.** Week 5 fits the covariance model on flight 05, where the label offset
   looks like about 11 m, and tests it on flight 11, where it looks like about 30 m. A model fitted on 05 will predict
   errors that are too small for 11 even if the matcher is equally good, so the test coverage can miss because of the
   labels, not the matcher. When reading the week 5 test coverage, compare the miss with the label-offset diagnostic
   for each flight before blaming the covariance model.
3. **No hand-correction with test labels.** We must not shift flight 11's labels (or any scores) by its measured
   offset. That would be fitting to the test data. The label-offset diagnostic (`eval/label_offset.py`) only reports
   the median east/north offset and its spread. It is never applied to scores, labels or matcher output. On the test
   split, run it only after the final numbers are recorded.

### 2026-11-19 — harness, baselines on tune (flight 10)
- New:
  - `eval/eval_matcher.py`: the runner. It refuses `--split test` without `--allow-test`.
  - `eval/matcher_report.py`: per-flight tables and CDFs. The baselines are always included, and every table carries
    the 15 m note.
  - `eval/label_offset.py`.
  - Tests: `eval/test_eval_matcher.py` (16) and `src/trn_matcher/test/test_interface.py` (9), plus 1 tile store test.
- Command: `/usr/bin/python3 eval/eval_matcher.py --split tune` (57 s). Output in `eval/results/week4/tune/`:
  - `frames_prior.csv`, `frames_random.csv`, `run_*.json`;
  - `summary.csv`, `summary.md`, `cdf_10.png`.
- Result, flight 10 (tune), 144 frames (from `summary.md`):

  | Method | Role | Fixes | Median [m] | p95 [m] | Within 15 m | Wrong (> 50 m) |
  |---|---|---|---|---|---|---|
  | prior | floor | 144 | 62.0 | 116.6 | 0.028 | 0.625 |
  | random | floor | 144 | 134.4 | 231.3 | 0.007 | 0.917 |

  Errors below about 15 m are not distinguishable from label registration error.
  - The prior median of 62.0 m fits 50 m per-axis noise (Rayleigh median 58.9 m).
- Map coverage: in 27 of 144 frames, less than 90 % of the map patch has imagery (minimum 0.43, p10 0.75). Flight
  10's map is small compared with the ±150 m window, so the matcher will often see `valid = False` areas (black) in
  the patch and must ignore them. Each frame's value is `map_valid_frac` in the frames CSV.
- Not done this session:
  - **The ROS 2 node (brief task 4).** It needs the matcher, and a message for fix + diagnostics (trn_msgs has only
    NavBelief).
  - **The optional learned matcher (task 5).**
  - **Any run on calibrate or test.**
- Risk noted, settings not changed: week 3 saw by eye that some flight 10 images look rotated a few degrees against
  the map. The image-pair rotation estimate for flight 10 is noisy (p10–p90 −21° to +15°, `uav_scale.csv`). If the
  real rotation sometimes exceeds 5°, a ±5° search will miss those frames. The harness counts a pose outside ±5° as
  no fix.
- Rerun `/usr/bin/python3 eval/eval_matcher.py --split tune` at commit ffe972a, so the run manifests point at the
  committed harness. Per-frame errors are identical (seeded); only `time_ms` differs. Summary unchanged.

### 2026-11-19/20 — matcher written by the executor (Akhil's instruction), tune split only
- Instruction (Akhil, 2026-11-19), in brief:
  - Write the matcher (`trn_matcher/matcher.py`, `FeatureMatcher`) on tune (flight 10) only. Never run
    `--split test` or `--allow-test`.
  - Classical masked NCC, coarse to fine.
  - At most 4 tunable settings, each logged. Freeze them in a committed file before calibrate or test.
  - Never tune against the label offset.
  - One ±20° rotation sweep.
  - Synthetic tests.
  - Honest reporting with failure overlays.
  - A plain-language explanation.
  - Then a minimal ROS node and a fix message.
- Files:
  - `src/trn_matcher/trn_matcher/`: `features.py`, `masked_ncc.py`, `matcher.py`, `matcher_frozen.json`,
    `frames.py` (frame preparation shared by harness and node), `matcher_node.py`, `matcher_sift.py` (rejected
    comparison).
  - `src/trn_msgs/msg/TerrainFix.msg`.
  - `eval/`: `tune_thresholds.py`, `matcher_failures.py`, `diag_by_heading.py`.
  - Tests: `test_matcher.py` (synthetic), `test_matcher_node.py`.
- Development path, in order (every run on tune, all under `eval/results/week4/tune_variants/`, see its README):
  1. **First version** (`ea6aff8`, raw NCC maximum over candidates), accept-all, coarse 64 px, rotation ±5°:
     - gradient: median 75.8 m; intensity: 106.3 m. Both worse than the prior floor (62.0 m).
     - Diagnosis: wrong answers piled up at scale 0.8. The maximum of raw NCC favours the smallest template,
       because fewer pixels give higher chance correlations.
     - **Design fix (not a tuned setting):** compare candidates by Fisher z = atanh(NCC)·√(overlap pixels).
  2. **Setting 1, feature type**, compared once (`5e965e6`, Fisher z, coarse 64, ±5°, accept-all):
     - gradient: median 68.9 m, 7.4 % within 15 m, 42.6 % within 50 m;
     - intensity: median 53.2 m, 8.5 %, 47.5 %.
     - **Intensity wins on every measure → kept.**
  3. **SIFT + RANSAC comparison** (fixed settings): 0 fixes in 144 frames (max 10 inliers, median 2). **Adds
     nothing → rejected** (the module is kept only as the record, not wired in).
  4. **The one ±20° rotation sweep** (intensity, coarse 64, accept-all):
     - 63 % of fixes needed |rotation| > 5°;
     - fixes within 50 m rose from 47.5 % to 58.9 %, and the median fell from 53.2 to 30.7 m;
     - correct fixes span about −14° to +13° (p5–p95), and none reached ±20°.
     - Per Akhil's rule, **the default rotation range was widened to ±20°** (`3c70607`).
     - The rotation residual flips sign with flight direction (see the diagnostics below).
  5. **Setting 2, coarse size**, compared at 48 / 64 / 96 px (intensity, ±20°, accept-all): within 50 m 54.0 / 58.9
     / 64.7 % of fixes, median 36.3 / 30.7 / 30.1 m. **96 kept.** It was the largest tried; 128 was not tried
     because time grows with its square (96 already takes about 8 s per frame).
  6. **Settings 3 and 4, thresholds:** chosen with `python3 eval/tune_thresholds.py
     eval/results/week4/tune_variants/z_intensity_c96_rot20/frames_ncc.csv`. The rule was fixed before seeing
     results: on a grid of peak 0–0.5 × ratio 1.0–2.0, accept the most frames with ≤ 5 % wrong (> 50 m) among
     accepted and ≥ 20 accepted.
     - **Result: peak_min 0.2, ratio_min 1.2** (44/144 accepted, 0 wrong). Grid in `threshold_grid.csv`.
     - On tune, peak_min does not change the accepted set: ratio ≥ 1.2 alone gives the same 44 frames. 0.2 came
       from the rule's conservative tie-break.
  7. **Frozen** in `src/trn_matcher/trn_matcher/matcher_frozen.json` (`eab9cc3`, before any calibrate or test
     run). A test pins the file to exactly these four settings and the default search space.
- The four tunable settings:

  | Setting | Values tried | Tune result | Frozen |
  |---|---|---|---|
  | feature | gradient, intensity | within 50 m: 42.6 vs 47.5 % of fixes | intensity |
  | coarse_px | 48, 64, 96 | within 50 m: 54.0 / 58.9 / 64.7 % | 96 |
  | peak_min | 0–0.5 (grid) | does not bind on tune | 0.2 |
  | ratio_min | 1.0–2.0 (grid) | 44/144 accepted, 0 > 50 m | 1.2 |

  - Fixed by design, not tuned (`matcher.py`): coarse steps 0.05 scale and 1° rotation (from the brief), fine
    steps 0.0125 and 0.25°, fine level about 256 px across, local-normalisation window 1/16 of the footprint,
    second-peak exclusion 1/4 of the footprint, minimum overlap 50 %, window ±150 m.
  - Search space (Akhil's, rotation widened by his rule): scale 0.8–1.3, rotation ±20°.

### 2026-11-20 — frozen matcher on tune: results
- Command: `/usr/bin/python3 eval/eval_matcher.py --split tune --matcher trn_matcher.matcher:FeatureMatcher`,
  started 2026-11-19 21:18, finished 21:38. Settings came from the frozen file.
  - The manifest records commit `39477e9`. Between `eab9cc3` and that commit only the report code changed.
  - The summary was regenerated with `python3 eval/matcher_report.py eval/results/week4/tune`. Output is in
    `eval/results/week4/tune/`.
- Flight 10 (tune), all 144 frames. Errors are against the dataset labels; median and p95 are over accepted
  frames.

  | Method | Role | Accepted | Median [m] | p95 [m] | Within 15 m (of fixes / of all) | Wrong > 50 m (of fixes) |
  |---|---|---|---|---|---|---|
  | prior | floor | 144 (100 %) | 62.0 | 116.6 | 2.8 % / 2.8 % | 62.5 % |
  | random | floor | 144 (100 %) | 134.4 | 231.3 | 0.7 % / 0.7 % | 91.7 % |
  | ncc (frozen) | matcher | 44 (30.6 %) | 23.2 | 32.4 | 11.4 % / 3.5 % | 0.0 % |

  Errors below about 15 m are not distinguishable from label registration error.
- Blank-patch frames: 32 frames have less than 90 % map imagery in their patch. That is more than the 27 counted
  at ±5°, because the ±20° patch is larger.
  - Those frames: 11 accepted (34.4 %), median 23.2 m, p95 31.9 m, 0 wrong. Floor: prior median 63.0 m.
  - The other 112 frames: 33 accepted (29.5 %), median 23.3 m, p95 31.4 m, 0 wrong.
  - Masking works: missing imagery does not lower acceptance or accuracy here.
- Runtime: median 7.5 s per frame (p95 9.7 s), single process. Fine for replay, too slow for real time.
- Honest reading:
  - The matcher beats the floor only on the frames it accepts: 30.6 %. It rejects the other 69 %, which is the
    intended behaviour when evidence is weak, but it is a low availability.
  - Accepted fixes have a median error of 23 m against the labels. Most of that is the label offset (next item),
    so "within 15 m of the label" is only 11 % even for correct matches. The 15 m criterion cannot be met on flight
    10 while its labels carry about 20 m of along-track offset.
  - "0 wrong among 44 accepted" is in-sample (thresholds chosen on these frames). With 0 of 44, the wrong rate
    could still be up to about 7 % (95 %, rule of three). Calibrate (flight 05) will be the first out-of-sample
    check.
  - Of the 100 rejected frames, 46 had a best candidate within 50 m of the label, but their ratio (median 1.058) is
    indistinguishable from the 54 whose candidate was wrong (1.061). The diagnostics cannot rescue them.
- Label-offset diagnostic (never applied):
  - `python3 eval/label_offset.py eval/results/week4/tune/frames_ncc.csv` → `label_offset_ncc.csv`: median
    offset east −7.5 m, north +10.0 m; p10–p90 north −24.6 to +27.9 m, which is bimodal.
  - `python3 eval/diag_by_heading.py eval/results/week4/tune/frames_ncc.csv` → `heading_diag_ncc.csv`, split by
    flight direction:
    - southbound (heading ≈ 157°, n = 20): east −8.6 m (MAD 5.0), north −17.8 m (MAD 6.3);
    - northbound (≈ 337°, n = 24): east −6.8 m (MAD 5.3), north +22.6 m (MAD 4.2).

    So the labels are about 20 m behind the matched position along the flight direction, plus a fixed about 7–9 m
    east offset.
  - Within one direction the spread is about 5–6 m MAD. That is a rough upper bound on the matcher's own
    scatter, though not a validated accuracy.
  - Hypothesis, untested: a time lag between the GPS fix and the exposure, or a camera tilt along track.
  - Week 5 consequence: label error on flight 10 is structured, not random. The same may hold, with other values,
    on 05 and 11. This adds to the "calibration mismatch" consequence above.
- Rotation diagnostic (same script): the rotation the matcher finds follows the dataset's two angle columns.
  - Southbound: +10.6° matched vs Phi1 − Phi2 = +9.3°. Northbound: −4.5° vs −14.5°.
  - So the stored "north-up" images look turned by roughly Phi1 − Phi2. A rotation prior from that difference could
    narrow the search later. It is not used now: the matcher reads no metadata.
- Failure overlays: `/usr/bin/python3 eval/matcher_failures.py eval/results/week4/tune --method ncc --count 6`.
  The images are in `eval/results/week4/tune/failures/` (git-ignored); the index is `failures_index.csv`. There are
  no wrong accepted fixes, so the six are rejected frames: 3 whose candidate was wrong and 3 whose candidate was
  right. Failure modes seen:
  1. **Repetitive structure** (10_0076, 10_0099, 10_0100): parallel tree strips and crop rows match equally well
     at several places, so the ratio is 1.03–1.10. In 0076 and 0100 the candidate was right (13 m and 6 m from the
     label) but could not be trusted.
  2. **Large rotation** (10_0101, 10_0102, 10_0088): tree strips run about 20° steeper in the image than on the
     map. The best answer was about −12.5° at scale 0.8, a distorted compromise. Some frames may lie at or past
     the ±20° edge.
  3. **Featureless hazy winter map** (10_0088): crop rows and tree lines in the photo, almost nothing on the map at
     the label.
- ROS node:
  - `trn_msgs/TerrainFix` (new; NavBelief unchanged) carries the fix and the diagnostics.
  - `ros2 run trn_matcher matcher_node` (parameters in `matcher_node.py`) replays a split (tune by default; test
    refused unless `allow_test`) through the frozen matcher and publishes `terrain_fix`. The label is not
    published.
  - Built with `colcon build --symlink-install --packages-select trn_msgs trn_matcher`.
  - Replay of every 6th tune frame (`eval/results/week4/tune/node_replay.log`): it publishes fixes and refusals
    with reasons. 10_0007 and 10_0013 give exactly the harness's positions (e.g. −564.0 / −122.6 m).
- Tests: eval 71 passed (venv); system Python subset 37; `trn_matcher` 43 passed, 1 skipped (template copyright);
  ament flake8 and pep257 clean.
  - The synthetic tests recover a known shift, scale and rotation to < 1 m, 0.02 and 0.5°, also with 40 % of the
    map masked and under haze plus contrast inversion. An unrelated image gets a lower peak and ratio and is
    rejected.

### How the matcher works, in plain words (for explaining it in an interview)

**The question it answers.** We have one photo taken straight down from the drone, a rough guess of where the
drone is (the prior, wrong by about 50 m), and a satellite map of the area. Where on the map was the photo taken?
The matcher slides the photo over the map and asks, at every position, how well do the two pictures agree? The
position where they agree best is the answer. Everything below makes that "slide and compare" step fair and fast.

**Step 1: make both pictures comparable** (`features.py`). The photo and the map were taken on different days,
seasons and years, in different light and haze. Comparing raw pixel colours fails, because a field that is green
in the photo can be brown on the map.
- *Grayscale.* Colour is the least reliable thing between seasons, so it is dropped.
- *Local contrast normalisation.* Around every pixel, subtract the average brightness of its neighbourhood and
  divide by how much the brightness varies there. The window is a Gaussian about 1/16 of the photo's width
  (about 8 m on flight 10). Haze makes a whole area greyer and flatter, and a darker exposure makes it darker.
  After this step both look alike, because only "brighter or darker than its surroundings, and by how much"
  survives. A small floor on the variation stops a perfectly flat area (water, hazy fog) from being blown up
  into noise.
- *Gradient (edge strength) or plain normalised intensity.* Option 'gradient' keeps only how sharply brightness
  changes: road edges, field borders, building outlines. It is useful when surfaces swap brightness between
  seasons, because an edge stays an edge even if the field on one side turns from dark to bright. Option
  'intensity' keeps the normalised brightness itself. Both were tried once on the tune flight, and intensity won
  (see the tuning table). A likely reason: flight 10's maps are hazy winter images, where fine edges are weak,
  but large patterns such as field blocks and tree strips still show as brighter and darker areas.

**Step 2: blank out what must not count (masking).** Two kinds of pixels carry no information.
- Parts of the map patch with **no map imagery** (outside the dataset's map: black).
- The **corners** that appear when the photo is rotated: a rotated square needs a bigger square to hold it, and
  the extra corners are empty.

If those pixels were compared, the black areas would match each other or produce fake edges. So each picture
carries a yes/no mask, and the comparison at every position uses only pixels that are "yes" in both. For edge
features the mask is also shrunk by a few pixels next to missing imagery, because the jump from picture to black
looks like a strong edge. On flight 10, 27 of 144 frames have more than 10 % of their map patch missing, so this
matters.

**Step 3: the comparison score: normalised cross-correlation (NCC)** (`masked_ncc.py`). Put the photo at one
position on the map. Take the overlapping pixels that are valid in both. Compute the correlation coefficient
between the two sets of values: +1 means the same pattern, 0 means unrelated, −1 means inverted. It is
"normalised", so a photo that is overall brighter or more contrasted than the map still scores 1 if the pattern
is the same. Computing it at every position one by one would be slow, so it is done for all positions at once
with Fourier transforms (the FFT): six correlations of whole images give, for every position, the pixel count,
the sums and the sums of squares needed for the masked correlation.

**Step 4: try every size and angle (scale and rotation).**
- *Size.* We know roughly how much ground the photo covers (the nominal footprint, about 124 m for flight 10,
  from the map chip size), but not exactly. So the photo is tried at 0.8× to 1.3× that size.
- *Angle.* The photos are stored "north-up", but the tune flight showed they are often turned by several
  degrees, so the photo is also tried at different angles: −20° to +20°, 1° apart. This range was first ±5° and
  was widened after the one rotation sweep, see the log above.

For each (size, angle) pair, the photo is shrunk to the map's pixel size, rotated, and correlated with the whole
search area. The search area is a square ±150 m around the prior (3 × the prior's 50 m uncertainty).

**Step 5: fairness between sizes (Fisher z).** A smaller photo has fewer pixels, and with fewer pixels a high
correlation happens more easily by chance. The same is true when only part of the photo lies on valid map. In
the first tune run this made the smallest size win far too often. So candidates are compared by z =
atanh(NCC) × √(number of overlapping pixels). This is the standard way to turn a correlation into "how surprising
is this, given how many pixels it is based on", and it puts all sizes and overlaps on one footing.

**Step 6: coarse to fine.** Trying 11 sizes × 41 angles at full map detail would be slow. So the search is first
done on a coarse copy of everything (setting coarse_px = 96: about 1.5 m per pixel on flight 10, where the photo is about 80 pixels across). Then,
around the best coarse answer only, it is repeated at full detail (about 0.5 m per pixel) with smaller size and
angle steps and a small position range. Finally a parabola is fitted through the best score and its neighbours,
to place the peak between pixels (sub-pixel refinement).

**Step 7: decide whether to trust it.** The answer always exists (some position is best), but it may be
meaningless. Two numbers decide.
- **peak**: the correlation (NCC) at the answer. Low means even the best position agrees poorly.
- **ratio**: the z score at the answer divided by the best z at least a quarter footprint away (the "second
  peak"). A ratio near 1 means another, unrelated place matches about as well, so the answer is a coin toss
  (repetitive fields, featureless terrain). A clearly higher ratio means one place stands out.

If either is below its threshold, the matcher returns "no fix" rather than a doubtful position. That is the
project's rule: refuse to publish what cannot be backed up.

**Diagnostics** (in `MatchResult.diag`, the per-frame CSV and the ROS message, for week 5):

| Name | What it is | How to read it |
|---|---|---|
| `peak` | correlation at the answer, −1..1 | higher = photo and map agree better |
| `peak_z`, `second_z` | significance of the best and of the second-best (far away) candidate | used for the ratio |
| `ratio` | `peak_z / second_z` | ≈ 1: ambiguous; higher: one clear match |
| `second_peak` | correlation at the second-best place | context for the ratio |
| `overlap_valid_frac` | share of the photo's footprint that lies on real map imagery at the answer | low = the match rests on part of the photo only |
| `scale` | photo ground size ÷ nominal footprint | far from 1 or at 0.8 / 1.3 = suspicious |
| `rot_deg` | how far the photo is turned, clockwise from north | at ±20 = maybe outside the search |
| `at_scale_edge`, `at_rot_edge` | coarse answer on the edge of the size/angle range | the true value may lie outside the search |
| `coarse_to_fine_m` | how far the fine step moved the coarse answer | large = coarse and fine disagree |
| `cand_east`, `cand_north` | the position found, also for rejected frames | lets week 5 and the failure plots see what a rejected frame would have said |
| `reason` | why a frame was rejected | e.g. "ratio below ratio_min" |

**What it does not do.**
- It does not use the drone's height or heading.
- It does not correct for terrain relief: the map is treated as flat.
- It does not learn anything: there are no trained weights.
- It does not shift its answer by the label offset.

### 2026-11-20 — sources of the numbers above
- Breakdowns of every tune run come from `python3 eval/tune_breakdown.py <run>/frames_ncc.csv ...`, saved as
  `eval/results/week4/tune_variants/breakdown.txt`. This covers shares within 15/30/50 m, the rotation and scale
  spread, the blank-patch split, and rejected candidates near or far from the label.
- The rotation residual of the ±20° sweep by flight direction comes from `python3 eval/diag_by_heading.py
  eval/results/week4/tune_variants/z_intensity_c64_rot20/frames_ncc.csv` (`heading_diag_ncc.csv`): +8.2°
  southbound and −6.5° northbound. This is the source of the "+8 / −6.5" in commit `3c70607`.
- Earlier, the same breakdowns were run once with a scratch script while deciding. Every number quoted in this
  log was reproduced with the scripts above.

## Week 4 follow-up (2026-11-20): calibrate run, label lag, top-k, rotation prior

### Instructions (Akhil, 2026-11-20)
- No frozen setting changes.
- Run the frozen matcher on calibrate (flight 05) only, and do not retune.
- Label-lag check, tune and calibrate separately. Nothing fitted on 11, no correction applied to scores.
- Top-3 distinct candidates in diag, with the best candidate unchanged and tested.
- Optional rotation prior (off by default) as a documented variant.
- Delete the SIFT file.
- Test (flight 11) untouched; `--allow-test` never used.

### Code (commit `1c60560`)
- **Matcher:**
  - `diag['topk']` holds up to 3 coarse candidates more than 20 m apart, best first: east, north, z, ncc, scale,
    rotation. It is diagnostic only; the returned fix is unchanged.
  - Optional rotation prior: `Prior.rot_deg` and `rot_sigma_deg`, default None. It narrows the rotation search to
    ±3σ inside the search range.
  - `matcher_frozen.json` is untouched.
- **Harness:**
  - `--workers N`: a process pool with identical rows.
  - `--rotation-prior phi1-phi2 --rotation-prior-sigma 3`: the variant.
  - Library versions are now recorded in run manifests.
- **Checks:**
  - `eval/compare_runs.py`.
  - `eval/test_matcher_regression.py`: the frozen best candidate on three tune frames must equal the committed
    frozen results, exactly under the reference environment (system Python, OpenCV 4.6.0, numpy 1.26.4,
    scipy 1.11.4).
- **Found while testing:** under the venv (OpenCV 5.0, numpy 2.5) the same code gives peak 0.1861 instead of
  0.1859 on a rejected frame, because interpolation differs between library versions. All reported runs use the
  system Python. The regression test allows small tolerances outside the reference environment and says so.
- **Full regression:** `/usr/bin/python3 eval/eval_matcher.py --split tune --matcher
  trn_matcher.matcher:FeatureMatcher --workers 8 --out eval/results/week4/tune_regression`, then
  `python3 eval/compare_runs.py` against `eval/results/week4/tune/frames_*.csv`: 144 frames, 0 differences for
  ncc, prior and random.
- **Deleted:** `src/trn_matcher/trn_matcher/matcher_sift.py` and its test, as Akhil asked. The week 4 log entry
  and `tune_variants/sift/` results are kept; the file remains in git history up to `e470a4a`.

### Calibrate (flight 05), frozen matcher, first out-of-sample run
- Command: `/usr/bin/python3 eval/eval_matcher.py --split calibrate --matcher trn_matcher.matcher:FeatureMatcher
  --workers 14` → `eval/results/week4/calibrate/` (`summary.md`, `cdf_05.png`, frames CSVs).
- Results, 473 frames. Median and p95 are over accepted fixes; errors are against the labels:

  | Subset | Method | Role | Accepted | Median [m] | p95 [m] | Within 15 m (of fixes / of all) | Wrong > 50 m (of fixes) |
  |---|---|---|---|---|---|---|---|
  | all 473 | prior | floor | 100 % | 55.8 | 125.2 | 3.2 % / 3.2 % | 58.1 % |
  | all 473 | random | floor | 100 % | 125.4 | 231.2 | 0.8 % / 0.8 % | 90.9 % |
  | all 473 | ncc | matcher | 74.8 % (354) | 25.4 | 58.3 | 18.6 % / 14.0 % | 8.5 % (30) |
  | < 90 % imagery (180) | ncc | matcher | 75.0 % | 22.0 | 50.4 | 23.7 % / 17.8 % | 6.7 % |
  | ≥ 90 % imagery (293) | ncc | matcher | 74.7 % | 27.9 | 59.1 | 15.5 % / 11.6 % | 9.6 % |

  Floor in the blank-patch subsets: prior median 55.4 m / 57.3 m. Errors below about 15 m are not
  distinguishable from label registration error.
- **Reading:**
  - Acceptance is much higher than on tune (74.8 % vs 30.6 %). The textured terrain gives large ratios (median
    2.0 vs 1.10 on tune).
  - **The wrong rate among accepted fixes is 8.5 %, above the 5 % target the thresholds were chosen for, and above
    the ~7 % upper bound quoted from tune's 0/44.** The thresholds do not transfer as a precision guarantee.
  - The 30 wrong fixes are mostly 50–90 m off (median 60.3 m; one at 148 m) with HIGH ratios (median 1.78), not
    low-confidence coin tosses.
  - They partly cluster in runs of about four consecutive frames (76–79, 144–148, 341–346, 366–371), so they are
    tied to particular places.
  - Source: `breakdown_calibrate_and_variant.txt` and `topk_check.txt`.
- **Failure overlays:** `/usr/bin/python3 eval/matcher_failures.py eval/results/week4/calibrate --method ncc
  --count 6` → `eval/results/week4/calibrate/failures/` (git-ignored).
  - **05_0076 (90 m, cluster 76–79):** the photo's road and fields match the map at the answer. At the label, the
    map shows greenhouses that are not in the photo. Either the label is about 90 m off here or the map changed. It
    cannot be decided without independent ground truth.
  - **05_0435 (148 m):** the label is at the edge of map coverage (patch only 45 % imagery). The true footprint is
    mostly off-map and the matcher locked onto a road elsewhere: a genuine matcher failure.
  - The other four are rejections: repetitive fields, or the label near the coverage edge.
- **Label-offset diagnostic** (`label_offset.py`, `diag_by_heading.py` on calibrate):
  - Median offset east −3.6 m, north −1.1 m, but spread is wide (MAD 18 / 12 m).
  - By direction (legs run east–west): eastbound fixes are about 7–11 m east of the label, westbound about
    12–14 m west. That is an along-track lead of about 10 m, smaller than flight 10's about 20 m.

### Label-lag check (diagnostic only; nothing applied to scores; nothing fitted on 11)
- Command: `/usr/bin/python3 eval/label_lag.py eval/results/week4/tune/frames_ncc.csv
  eval/results/week4/calibrate/frames_ncc.csv` → `eval/results/week4/label_lag.csv`, printed output in
  `label_lag.txt`. Repeated with `--time attr3` (`label_lag_attr3.*`): same results.
- **Method:** for each accepted fix, the along-track component of (label − fix), with the track direction and the
  speed taken from the neighbouring frames' labels and timestamps (`date`, 1 s resolution). The lag model is
  along = speed × lag, fitted through the origin. Also reported:
  - a constant along-track model;
  - a 2-D model, (label − fix) = constant east/north shift + speed × lag × track direction.

  Negative lag means the label is where the drone was that many seconds BEFORE the photo.

  | Flight | n | Speed (CV) | Lag (along-track fit) | Residual RMS / MAD | 2-D model: shift E/N, lag | Raw median error | DIAGNOSTIC lag-corrected median (own lag, in-sample) |
  |---|---|---|---|---|---|---|---|
  | 10 (tune) | 39 | 20.3 m/s (0.09) | −0.90 ± 0.08 s | 10.2 / 6.3 m | +7.7 / −1.5 m, −0.88 ± 0.08 s | 24.5 m | 12.9 m |
  | 05 (calibrate) | 339 | 23.6 m/s (0.18) | −0.31 ± 0.06 s | 25.2 / 14.8 m | +4.3 / +1.2 m, −0.35 ± 0.05 s | 25.3 m | 23.6 m |

- **The two lags do not agree:** −0.90 vs −0.31 s, 5.9 combined standard errors apart (5.4 for the 2-D model).
  - Cross-check (DIAGNOSTIC): flight 05's lag applied to 10 gives median 19.4 m; flight 10's lag applied to 05
    gives 24.2 m.
  - On flight 10 a lag removes about half of the error (in-sample). On flight 05 it explains almost nothing: the
    residual RMS of 25 m is dominated by something else.
  - Relief displacement in mountainous terrain is a plausible cause (hypothesis, untested, and no DEM is used yet).
  - Speed barely varies within a flight, so a timing lag and a fixed along-track offset (camera tilt) cannot be
    told apart reliably. The "both" model is unstable: flight 10 gives c +15.8 m with lag −1.67 s.
- **Conclusion:** no single lag constant explains the label offset across flights. A lag correction is not a safe
  global fix, and none is applied.

### Top-k candidates (diagnostic)
- `/usr/bin/python3 eval/topk_check.py eval/results/week4/tune_regression/frames_ncc.csv
  eval/results/week4/calibrate/frames_ncc.csv` → `topk_check.txt`. The question: is the label within 50 m of
  candidate #1, #2 or #3?
  - Accepted fixes: #1 in 98 % (tune) and 92 % (calibrate).
  - Rejected frames: #1 45 % / 53 %; #2–3 15 % / 15 %; none 40 % / 32 %.
  - Wrong accepted fixes on calibrate (30): #2–3 20 %, none 77 %.
- So for rejected frames the right place is often in the top-3. For the confident wrong fixes it usually is not,
  which fits the label/map-disagreement explanation better than ambiguity.

### Rotation-prior variant (VARIANT, not frozen)
- Rotation prior = wrap(Phi1 − Phi2) + N(0, 3°) per frame (seeded), with matcher σ = 3°, so the search is the
  prior ±9°.
  - Phi1 − Phi2 is the heading-derived quantity that tracked the matcher's rotation on flight 10 (week 4 heading
    diagnostic). The plain heading Phi2 was already used by the dataset authors to turn the images north-up.
- Commands: `/usr/bin/python3 eval/eval_matcher.py --split {tune,calibrate} --matcher
  trn_matcher.matcher:FeatureMatcher --rotation-prior phi1-phi2 --rotation-prior-sigma 3 --workers 7 --out
  eval/results/week4/variant_rotprior/{tune,calibrate}`.

  | Flight | Run | Accepted | Median [m] | p95 [m] | Within 15 m (of fixes) | Wrong > 50 m (of fixes) |
  |---|---|---|---|---|---|---|
  | 10 (tune) | frozen | 30.6 % | 23.2 | 32.4 | 11.4 % | 0.0 % |
  | 10 (tune) | rotation prior | 22.2 % | 22.2 | 33.4 | 15.6 % | 0.0 % |
  | 05 (calibrate) | frozen | 74.8 % | 25.4 | 58.3 | 18.6 % | 8.5 % |
  | 05 (calibrate) | rotation prior | 23.0 % | 26.6 | 80.5 | 13.8 % | 14.7 % |

  Floor: prior median 62.0 m (tune), 55.8 m (calibrate). Errors below about 15 m are not distinguishable from label
  registration error.
- **The prior hurts on both flights**, badly on 05.
- `diag_by_heading.py` on calibrate shows why: on flight 05, Phi1 − Phi2 has the OPPOSITE sign to the rotation
  the matcher finds:
  - eastbound: Phi1 − Phi2 +13.8° and +15.4°, matcher −4.1° and −4.5°;
  - westbound: −11.8° and −11.6° against +4.0° and +3.5°.

  On 05, 65 % of variant answers sit at the edge of the narrowed window.
  - On flight 10 the signs agree, but northbound legs differ by about 7°, so ±9° often clips the truth there too.
- The meaning of the dataset's angle columns is not documented, and their relation to image rotation is not
  consistent across flights. Do not use Phi1/Phi2 as a rotation prior without understanding them.

### What this changes for week 5 (covariance calibration)
1. **The label error differs by flight and has structure.** Flight 10: about 20 m along-track lead plus about 8 m
   east. Flight 05: about 10 m along-track, plus 25 m RMS that a lag does not explain. A covariance fitted on 05
   absorbs 05's label error, which is not 10's or 11's. Coverage on 11 can miss because of labels, not the matcher
   (consequence 2 above, now with numbers).
2. **The accept rule is not a precision guarantee:** 0 % wrong on tune in-sample, 8.5 % on calibrate. Week 5 must
   model the wrong-fix rate explicitly (a mixture or outlier term), not assume accepted means correct.
3. **The wrong fixes on 05 are confident** (high ratio). Peak and ratio alone will not flag them. Useful extra
   inputs: top-k z gap, overlap_valid_frac (05_0435 is a coverage-edge failure), map_valid_frac, and whether the
   prior lies near the map edge.
4. **Diagnostics shift between flights:** median ratio 1.10 (tune, accept-all) vs 2.0 (calibrate). A covariance
   model in raw ratio units fitted on 05 may not transfer to 11's terrain. Normalising per flight would itself need
   care.
5. **Library versions change results slightly.** Fit and test in the same environment (system Python, OpenCV 4.6).

### Things that look wrong or unresolved
- The 8.5 % wrong rate on calibrate, above the tune target.
- Clusters of confident 50–90 m fixes on 05: label error or map change? Undecided without independent ground
  truth.
- The angle columns Phi1/Phi2 relate to image rotation with opposite signs on 05 and 10.
- Two results differ between library environments (venv vs system).

## Week 5 — calibration of the fix error (started 2026-11-20)

### Rules (Akhil, 2026-11-20)
- Matcher frozen.
- Fit only on calibrate (flight 05): block cross-validation for model choice, block bootstrap for intervals,
  effective sample size reported.
- Freeze, then check once on tune (flight 10).
- Nothing on flight 11; no `--allow-test`.
- No lag correction and no rotation prior anywhere.
- Model drafted by the executor (Akhil's instruction): a mixture of Gaussian inliers and broad outliers.
- Every table carries the label-error sentence.
- Housekeeping: an environment check that fails loudly.

### Environment check (commit `90b20e1`)
- `eval/reference_env.json` holds the versions of the reported runs: Python 3.12.3, numpy 1.26.4, OpenCV
  4.6.0, scipy 1.11.4.
- `eval/envcheck.py` `require_reference_env()` exits with code 3 and lists the differences.
- Called by `eval_matcher.py` (after the test-split refusal), `calib_features.py`, `calib_fit.py`,
  `calib_eval.py` and `error_budget.py`.
- The venv (numpy 2.5, OpenCV 5.0, scipy 1.18) fails it. All week 5 commands run with `/usr/bin/python3`.

### The error model, in plain words
- **What it predicts.** For each candidate fix it gives two answers:
  1. how far off the fix probably is (a spread in metres);
  2. how likely it is to be plain wrong (more than 50 m from the label).
- **Two kinds of fixes.**
  - Most fixes land on the right place and are off by a modest amount: label registration error plus matcher
    error. That part is a round bell curve (2-D Gaussian) with spread σ.
  - Some fixes lock onto the wrong place, and then the error can be anything within the search area. That part
    is a much wider bell curve (σ_out ≥ 60 m).
  - The model says: with probability 1 − w the fix is of the first kind, with probability w of the second.
- **Where the features come in.** σ and w are not constants: they depend on the matcher's diagnostics x.
  - log σ = a0 + a·x.
  - logit w = b0 + b·x. The logistic function keeps w between 0 and 1.
  - The features are standardised with flight 05's mean and spread, and the slopes get a small penalty (ridge)
    so a few hundred frames cannot push them to extremes.
  - With no features this is the constant baseline.
- **What it does not do.** The bell curves are centred on zero. The model does not estimate or remove the label
  offset; that would be the lag correction, which is not applied.
- **How it is fitted.** Choose the parameters that make the observed errors most probable (maximum likelihood).
  "NLL" is the negative log of that probability per frame; lower is better, and it punishes both overconfidence
  and vagueness.
- **What comes out at run time.**
  - Radius for coverage p: the circle that should contain the label with probability p (50/90/95 %).
  - Coverage: how often it actually does.
  - P(wrong) = P(|e| > 50 m) under the mixture. It drives the validity states.
  - A floor matters: with an inlier σ of about 21 m, even a "right" fix has about 6 % probability of exceeding
    50 m. So P(wrong) never goes below about 6 %.

**Errors are against dataset labels, so reported uncertainty includes label registration error and is not
uncertainty about the true position.**

### Features and their shift between flights
- Built from the frozen runs: flight 05 calibrate, and flight 10 `tune_regression` (identical to the frozen tune
  run, with top-k).
  - Command: `/usr/bin/python3 eval/calib_features.py eval/results/week4/calibrate/frames_ncc.csv
    eval/results/week4/tune_regression/frames_ncc.csv` → `eval/results/week5/features_{05,10}.csv` and
    `feature_shift.md`.
  - Every frame with a candidate is used (473 / 144): the accepted fix, or the best rejected candidate.
  - Wrong (> 50 m): 18.2 % on 05, 37.5 % on 10.
- Shift between the flights (two-sample KS, all frames):

  | Feature | KS | Shift |
  |---|---|---|
  | log_ratio | 0.54 | median 0.58 → 0.10 |
  | rel_gap | 0.51 | |
  | peak | 0.21 | |
  | peak_z_norm | 0.18 | |
  | alt_dist_fp | 0.21 | |
  | edge_fp | 0.28 | |
  | overlap, at_bound | | almost constant; little information |

### Model choice on 05 (block CV, 8 contiguous blocks)
- Command: `/usr/bin/python3 eval/calib_fit.py` → `calibration_frozen.json`, `cv_models.csv`, `oof_05.csv`,
  `calib_fit.txt`.
- Seven feature sets × λ ∈ {1, 10}. Out-of-fold NLL (nats per frame):

  | Model | NLL | AUC wrong |
  |---|---|---|
  | M0 const | 9.693 | |
  | M1 ratio (λ 1) | 9.538 | 0.757 |
  | M2 robust (peak z + top-2 distance) | 9.580 | 0.728 |
  | M3 ratio+gap | 9.535 (best) | |
  | M4/M6 (with overlap and edge) | 9.65–9.68 | |
  | M5 ratio+all | 9.59 | |

- **Selection rule changed after the first run.**
  - The declared rule compared each model's mean NLL with the best ± the UNPAIRED standard error of block means
    (about 0.17–0.21). That error is dominated by terrain differences between blocks, so all 13 models were
    "eligible" and the shift tie-break picked the constant model.
  - Since the models are compared on the same frames, the rule now uses the PAIRED difference to the best model
    (SE of its block means).
  - The first output is kept: `calib_fit_declared_rule_unpaired_se.txt`. This is a rule change made after seeing
    a result, and it is reported as such.
- Paired differences to the best: M1 ratio λ 1 +0.003 ± 0.006, M2 robust +0.044 ± 0.011, M0 +0.157 ± 0.046.
  - Eligible: M1 ratio and M3. The shift tie-break picks M1 (KS 0.54 for both).
  - AUC 0.757 ≥ 0.65, so the features do separate wrong from right on 05.
  - CV NLL chosen − constant: −0.154 (block-bootstrap 95 % CI −0.238 to −0.097). n = 473, effective n 100 (wrong
    indicator) / 90 (NLL).
- **Frozen** (commit `3e3a2cb`, before any flight 10 evaluation), all fitted on all of 05:
  - selected = M1 ratio;
  - baselines: constant, ratio;
  - comparison: M2 shift-robust (added after the first run, before the flight 10 check).
- Fitted selected model:
  - inlier σ = e^3.05 ≈ 21 m per axis, almost independent of the ratio (slope 0.05);
  - σ_out ≈ 100 m;
  - logit w = −3.89 − 2.81·(standardised log ratio).

  The features act through w, the chance of being wrong. The spread of a right fix is about 21 m whatever the
  diagnostics say, about the size of the label registration error.

### Results
Errors are against dataset labels, so reported uncertainty includes label registration error and is not
uncertainty about the true position.

- `eval/results/week5/eval_05.md`: flight 05, out-of-fold, n = 473, effective n 100.

  | Model | NLL | Coverage 50/90/95 % | ECE P(wrong) | AUC wrong |
  |---|---|---|---|---|
  | selected = ratio | 9.538 [9.286, 9.784] | 0.50 / 0.90 / 0.96 | 0.062 [0.030, 0.105] | 0.757 |
  | constant | 9.693 | 0.50 / 0.89 / 0.94 | 0.079 | (0.33, artefact of fold offsets) |
  | shift-robust | 9.580 | 0.51 / 0.90 / 0.96 | 0.058 | 0.728 |

- `eval/results/week5/eval_10.md`: flight 10, frozen models, out-of-sample, n = 144, effective n 51.

  | Model | NLL | Coverage 50/90/95 % | ECE P(wrong) | AUC wrong |
  |---|---|---|---|---|
  | selected = ratio | 10.447 [9.899, 10.853] | 0.51 / 0.91 / 0.97 | 0.056 | 0.739 |
  | constant | 10.740 | 0.42 / 0.67 / 0.81 | 0.199 | 0.500 |
  | shift-robust | 10.893 | 0.40 / 0.72 / 0.78 | 0.236 | 0.719 |

  - The ECE bootstrap interval [0.058, 0.182] lies above its point estimate: ECE is biased upward on resampled
    small bins. Read it as "about 0.06–0.18".
- **The selected model's calibration holds out of sample.** The shift in log_ratio between flights is real
  information: flight 10 really is harder (37.5 % wrong vs 18.2 %), and only the ratio sees it. The shift-robust
  features and the constant model under-cover badly on 10. "Prefer comparable features" would have been the wrong
  choice here.
- Reliability plots: `reliability_{05,10}.png`.
  - On 10 the bins go from predicted 0.10 → observed 0.00, up to 0.56 → 0.54.
  - On 05 the lowest bin is under-predicted: 0.072 vs 0.126. These are the confident wrong fixes (label/map
    disagreement clusters).
- **Risk-coverage** (`risk_coverage_{05,10}.png`): accept frames from lowest risk.
  - On 10, P(wrong) from one model ranks exactly like the ratio, so the curves coincide (AURC 0.181 both). The
    shift-robust model gives 0.236.
  - On 05, out of fold, P(wrong) ranks worse than ratio (AURC 0.113 vs 0.071), because the 8 fold models are
    offset from each other.
  - So **a calibrated gate does not rank better than the old ratio gate**. What it adds is that its thresholds
    mean a probability, and that the probability transferred to 10. The ratio threshold's meaning did not: the
    frozen matcher gate gives 0 % wrong at 30.6 % on 10 but 8.5 % wrong on 05.
- **Validity states** (the frozen rule, from 05 out-of-fold):
  - STRONG needs ≤ 2 % wrong. No threshold reaches that on 05, so **there is no STRONG state**: the wrong rate on
    05 stays at about 8–12 % at every threshold, because of the confident label/map disagreements.
  - UNCERTAIN: P(wrong) ≤ 0.389, the largest threshold with ≤ 10 % wrong on 05. On 05 that is 85 % of frames at
    9.9 % wrong. On 10 it is 44 % of frames at 17.2 % wrong (above target) with 95 % coverage 0.953.
  - DO_NOT_PUBLISH: the rest. On 10 that is 56 % of frames at 54 % wrong.
- Threshold table (`eval_{05,10}.md`), fraction accepted and wrong rate among accepted:

  | P(wrong) ≤ | 05 | 10 |
  |---|---|---|
  | 0.20 | 73 %, 8.1 % wrong | 22 %, 0 % wrong |
  | 0.30 | 79 %, 8.5 % | 34 %, 4.1 % |

  A STRONG cut near 0.2 would look good on 10, but choosing it from 10 would be tuning on the check flight. It is
  not frozen.
- **Error budget** (`/usr/bin/python3 eval/error_budget.py eval/results/week5/features_10.csv
  eval/results/week5/features_05.csv` → `error_budget.txt`). Accepted fixes with |e| ≤ 50 m, grouped by flight
  direction:
  - **Flight 10:** RMS 24.3 m. Systematic per-direction offset 21.1 m, which is **75 % of the mean square**.
    Within-direction scatter 12.1 m RMS (8.6 m per axis; median residual 8.8 m), an upper bound on the matcher's
    own error.
  - **Flight 05:** RMS 27.3 m. Systematic 9.0 m (11 %). Scatter 25.8 m (18.2 m per axis). Either the matcher is
    less precise in the mountains, or the label noise there is random rather than systematic. This data cannot
    separate the two.
  - Note: 05's legs head about 90° and 270°, so the 90° bins split each direction in two. The systematic part is
    still captured.

### Negative results carried into week 5 (not applied anywhere)
- **Label lag:** −0.90 s on 10 vs −0.31 s on 05, about 6 SE apart. It explains about half of 10's error and almost
  none of 05's. Not a global correction.
- **Rotation prior from Phi1 − Phi2:** it lowers acceptance on both flights and doubles wrong fixes on 05, where
  the sign is opposite. Not used.

### What to change before week 6 (proposal for Akhil)
1. **Publication decision.** Move it from the matcher's frozen ratio gate to the calibrated P(wrong). For that,
   the matcher must hand over a candidate for every frame: run it accept-all (peak_min = ratio_min = 0) or use
   `last_diag`, and let the validity state machine decide.
2. **Define "wrong" so a STRONG state is reachable.** The 50 m criterion against these labels cannot get below
   about 8 % wrong on 05: the label error alone gives about 6 % beyond 50 m, plus the 05 disagreement clusters.
   Options:
   - a STRONG state defined on P(wrong) ≤ 0.2, accepted as a design choice and checked on test;
   - more calibration data (another RGB flight);
   - better labels (a lag model per flight).
3. **Covariance in NavBelief.** The inlier σ of about 21 m per axis is mostly label error. Fusion in week 6 should
   take the covariance as given, but remember it is label-referenced: it is not the uncertainty of the true
   position. Fusing several fixes will not average the systematic per-direction offset away.
4. **Covariance shape.** Isotropic covariance is a simplification. On flight 10 the error is elongated along
   track. An anisotropic Σ (along/cross-track) needs the heading; decide whether that is allowed.
5. **Keep the environment check** and run everything with `/usr/bin/python3`.

### 2026-11-21 — week 5 loose ends
- **Two decisions were made after seeing results** (recorded here as Akhil asked):
  1. The model-choice rule was changed after its first run, from an unpaired to a paired standard error. See
     "Model choice on 05" above; the first output is kept.
  2. The STRONG cut (P(wrong) ≤ 0.15) was set on 2026-11-21, after the flight 10 risk-coverage curve and
     threshold table had been seen. Flight 10 is therefore not a clean check of that cut; flight 11 (test) is.
     - The UNCERTAIN cut 0.389 is the frozen week 5 rule's t_publish, from flight 05 out-of-fold.
     - Cuts are in `src/trn_calibration/trn_calibration/validity_cuts.json`; `calibration_frozen.json` is
       unchanged. Cuts are not moved after seeing results.
- `eval/calib_eval.py` adds sharpness (median 90 % radius) next to coverage, and the states under these cuts.
  Rerun with `/usr/bin/python3 eval/calib_eval.py 05` and `... 10`: same frozen models, nothing refitted.
- Errors are against dataset labels, so reported uncertainty includes label registration error and is not
  uncertainty about the true position.
- Sharpness, median 90 % radius:

  | Model | 05 (out-of-fold) | 10 |
  |---|---|---|
  | selected (ratio) | 48.7 m | 173.7 m |
  | constant | 88.1 m | 85.3 m |
  | shift-robust | 50.5 m | 52.1 m |

  - On 10 the selected model is wide because many frames have a high outlier weight, so their 90 % region is set
    by the 100 m outlier part. That width is what keeps its coverage at 0.91. The constant is sharper on 10 but
    covers only 0.67 at 90 %.
- States with these cuts:

  | State | 05 (out-of-fold): frames / wrong / cov90 / sharpness | 10: frames / wrong / cov90 / sharpness |
  |---|---|---|
  | STRONG | 68.7 % / 8.3 % / 0.905 / 47.9 m | 18.1 % / 0.0 % / 1.000 / 47.8 m |
  | UNCERTAIN | 16.3 % / 16.9 % / 0.909 / 135.3 m | 26.4 % / 28.9 % / 0.895 / 146.5 m |
  | DO_NOT_PUBLISH | 15.0 % / 64.8 % / 0.887 / 185.3 m | 55.6 % / 53.7 % / 0.887 / 186.1 m |

- **Matcher accept-all mode:** `FeatureMatcher(accept_all=True)`. It is a constructor flag, not a setting, so
  `matcher_frozen.json` is unchanged.
  - It returns the best candidate for every frame that has one. The old peak/ratio gate's verdict is kept in
    `diag['gate_pass']` (and `diag['accepted']`). Frames without a valid candidate (no overlap, refined answer
    outside the search space) still return None.
  - Regression test `eval/test_matcher_regression.py::test_accept_all_returns_frozen_best_candidates`: the
    settings equal the frozen file, and on three tune frames the answer equals the frozen fix, or for a rejected
    frame the frozen `cand_east/north`. Exact in the reference environment; small tolerances under other library
    versions.

## Week 6 — fusion and the belief message (2026-11-21)

### Instructions (Akhil, 2026-11-21), on top of the week 6 brief
- **Odometry:** SYNTHETIC. Label-path increments plus the floor + random-walk drift from `drift_params.json`
  (not the power law). Random walk scaled to 0.1 / 0.5 / 1 / 2 % long-run drift.
- **Fixes:**
  - Factor: the week 5 mixture (inlier σ(ratio) or outlier).
  - Thinning: interval from flight 05's error autocorrelation, then frozen.
  - Gating: chi-square, reported.
  - No bias state. GTSAM iSAM2. The validity state is an output summary only.
- **NavBelief:**
  - fix_age = time since the last FUSED fix.
  - AGING threshold chosen and written down before results.
  - Validity from a state machine, plus a reason string.
  - Wired as a ROS 2 node.
- **Splits:** develop on 10, check on 05, never 11.
- The executor wrote the factor definitions and the gating as instructed. (The brief had them as "user writes".)

### Environments
- `gtsam` (4.3.0) exists only in the venv `~/venvs/trn`; system Python has none.
  - Fusion runs and the belief node use the venv interpreter.
  - The replay and matcher nodes use system Python.
  - `rclpy` imports in the venv when ROS is sourced.
- `eval/reference_env_fusion.json` holds the venv versions (numpy 2.5.4, scipy 1.18.1, gtsam 4.3.0).
  `eval/envcheck.py` now checks gtsam too; `eval_fusion.py` requires the fusion reference.
- Matcher and calibration results stay tied to system Python (`reference_env.json`).

### How the fusion works, in plain words
- **State.** Only the horizontal position (east, north), one unknown per camera frame (about every 3 s).
- **Odometry (SYNTHETIC).** Between frames we know how far we moved, but with drift.
  - In this project the odometry is made up: the true (label) movement plus a sampled error. That error is a tiny
    white "floor" (7 mm, week 2) plus a random walk whose variance grows with distance.
  - The random walk is scaled so that after 10 km the RMS drift is 0.1 %, 0.5 %, 1 % or 2 % of 10 km (10, 50, 100,
    200 m). It grows as the square root of distance.
  - The filter is told the correct drift statistics. That is optimistic: a real filter would not know them
    exactly.
- **Fixes.** The frozen matcher's best candidate for each frame (accept-all; the old gate verdict is kept only as
  information).
  - Each fix is modelled exactly as calibrated in week 5: either an inlier, scattered by σ(ratio) ≈ 21 m around
    the true position, or an outlier, scattered by σ_out ≈ 100 m, with probability w(ratio).
  - GTSAM solves least-squares problems, which cannot hold a sum of two bell curves. So the factor uses the
    "max-mixture" trick: at every step it takes whichever of the two explains the fix better.
  - A fix that looks like an outlier therefore pulls only weakly, and a fix that agrees pulls strongly.
- **Thinning.** Consecutive fixes share errors (flight 05: the along-track error stays correlated for about 2
  frames). Treating them as independent would make the filter overconfident.
  - Rule (frozen): fuse at most one fix per 9 s.
  - 9 s = the first lag at which both error autocorrelations on flight 05 fall below 1/e, × the 3 s frame step
    (`eval/fusion_thinning.py` → `thinning_05.json`).
- **Gate.** Before fusing, the fix is compared with where the filter expects to be. If the difference is too big
  for the combined uncertainty (predicted covariance + inlier σ²) at the 99 % level of a chi-square with 2 degrees
  of freedom, it is not fused.
- **iSAM2.** GTSAM's incremental smoother re-solves only the part of the problem a new measurement touches. That
  keeps each update under a few milliseconds.
- **Belief and validity.** After every update we read the current position and its 2×2 covariance.
  s = the 1-sigma length of the covariance's long axis. The rules, written down before any result
  (`fusion_frozen.json`):
  - DO_NOT_PUBLISH if no fix has been fused yet or s > 100 m (2 × the 50 m start prior);
  - AGING if s > 30 m (1.5 × the 21 m fix inlier σ);
  - UNCERTAIN if the last fused fix had P(wrong) > 0.15;
  - STRONG otherwise.
  - fix_age is the time since the last fused fix. The fusion never looks at the state.
- **ROS.**
  - `trn_fusion/replay_node` (system Python) publishes the SYNTHETIC odometry (`odom`), the recorded candidate
    fixes (`terrain_fix`, TerrainFix with the new `gate_pass`) and the start prior.
  - `trn_fusion/belief_node` (venv) runs the same FusionCore and publishes `nav_belief` (NavBelief: pose with the
    east/north covariance block, z and rotations marked unestimated with 1e6, fix_age, validity, reason).
  - `launch/replay.launch.py flight:=10 drift_pct:=1.0 seed:=0 speed:=20.0` starts both.

### Results
Errors are against dataset labels and include label registration error. Odometry is SYNTHETIC.

- Commands:
  - `env -u PYTHONPATH ~/venvs/trn/bin/python eval/eval_fusion.py 10` (development, 20 seeds) and `... 05` (check,
    run once with unchanged code and configuration).
  - Output: `eval/results/week6/fusion_{10,05}.md/.csv`, timelines `timeline_*_drift1pct.png` and
    `timeline_*_outage_{1,2}pct.png`.
- ATE RMSE (median) in metres, mean over 20 seeds:

  | Flight | Drift | Fused | Odometry-only from the prior | Odometry-only from the TRUE start | Fixes-only (all candidates) |
  |---|---|---|---|---|---|
  | 10 | 0.1 % | 19.8 (10.2) | 71.1 | **6.2** | 86.7 (30.1) |
  | 10 | 0.5 % | **24.0** (15.9) | 78.3 | 32.3 | 86.7 (30.1) |
  | 10 | 1 % | **32.1** (22.4) | 99.1 | 61.7 | 86.7 (30.1) |
  | 10 | 2 % | **46.6** (33.3) | 142.4 | 133.2 | 86.7 (**30.1**) |
  | 05 | 0.1 % | **11.1** (8.1) | 60.7 | 11.7 | 59.5 (27.4) |
  | 05 | 0.5 % | **18.1** (15.2) | 82.5 | 53.7 | 59.5 (27.4) |
  | 05 | 1 % | **24.9** (20.2) | 122.8 | 107.1 | 59.5 (27.4) |
  | 05 | 2 % | **37.1** (27.0) | 233.4 | 224.6 | 59.5 (27.4) |

  - "Odometry-only from the prior" starts at the same 50 m-uncertain prior as the fusion. "From the TRUE start"
    is an oracle that shows pure drift.
- **Where fusion does not win:**
  - **Flight 10 at 0.1 %:** odometry from the true start (6.2 m) beats fusion (19.8 m). The fixes' errors (about
    21 m, mostly label registration) are larger than the drift.
  - **Flight 05 at 0.1 %:** a tie (11.1 vs 11.7 m).
  - **Flight 10 at 2 %:** the fused median (33.3 m) is worse than the raw fixes' median (30.1 m). The fused RMSE
    is much better (46.6 vs 86.7 m), because outliers are suppressed.
- Consistency of the fused covariance against the labels (NEES 2 = consistent; share of frames inside the 95 %
  ellipse):

  | Flight | NEES at 0.1 / 0.5 / 1 / 2 % | Inside 95 % ellipse |
  |---|---|---|
  | 10 | 5.1 / 3.8 / 3.7 / 3.1 | 0.79 / 0.81 / 0.84 / 0.88 |
  | 05 | 3.1 / 2.7 / 2.5 / 2.3 | 0.87 / 0.91 / 0.91 / 0.93 |

  The fused covariance is overconfident, most on flight 10. Flight 10's label offset is systematic along each
  leg (week 4: about 20 m along-track), so even 9 s-thinned fixes are not independent there. The 9 s interval was
  set from flight 05, where the errors decorrelate faster.
- **Fix handling** (mean per run): candidates 139 (10) / 472 (05).

  | Flight | Thinned | Offered to the gate | Rejected by the chi-square gate | Fused |
  |---|---|---|---|---|
  | 10 | about 79 | about 60 | **15–20 (25–33 %)** | about 40 |
  | 05 | about 316 | about 156 | **22–32 (14–21 %)** | about 125 |

  - Fused fixes the final estimate explains as outliers: 5–15 % (10) and 2–6 % (05).
- **Validity, share of frames** (normal runs; DO_NOT_PUBLISH 0 %):

  | Flight | STRONG | AGING | UNCERTAIN |
  |---|---|---|---|
  | 10 | 27 % (23 % at 2 %) | 2–3 % (23 % at 2 %) | about 70 % |
  | 05 | about 75 % | 1–9 % | about 24 % |

  - On flight 10 most fixes have P(wrong) > 0.15, so UNCERTAIN dominates. The published error is the same as the
    fused error, since every frame is published.
- **Fix outage** (fixes stop after 30 % of the frames, seed 0; error in the 2-sigma band shown in the timelines):

  | Flight | Drift | Behaviour | Error inside 2σ during outage |
  |---|---|---|---|
  | 10 | 1 % (declared) | AGING after 86 s; **never reaches DO_NOT_PUBLISH** (1-sigma 60 m at the end; reaching 100 m at 1 % takes about 20 km) | 100 % |
  | 10 | 2 % (added after the first development run) | AGING at once, DO_NOT_PUBLISH after 350 s | 78 % |
  | 05 | 1 % | DO_NOT_PUBLISH at 1553 s | 97 % |
  | 05 | 2 % | DO_NOT_PUBLISH at 732 s | 98 % |

  Without fixes the uncertainty grows as the drift model says (unit test: within 20 % of sqrt(σ0² + b·d/2)).
- **Latency** (`eval_fusion.py`, per frame: odometry + fix + belief including covariance): median 0.2–0.4 ms;
  p95 up to 9 ms on 05 at 0.1 % (iSAM2 relinearisation).
- **Node:**
  - Replay of flight 10 at 20× speed publishes about 5–7 NavBelief per second (one per odometry step plus one per
    fused fix). In real time that is one per frame (about 0.3 Hz) plus fixes.
  - Callback latency median 0.61 ms, p95 1.42 ms, max 2.05 ms (`node_replay_10.log`).
  - `eval/compare_node_trace.py` confirms the node equals the offline fusion on all 144 frames: max difference
    5e-5 m (CSV rounding), validity 100 % equal.
- Tests:
  - `src/trn_fusion/test/test_fusion.py` (venv, 7): drift level definition, mixture choice, outlier pull 80 m vs
    345 m for a Gaussian, outage growth vs prediction, STRONG→AGING→DO_NOT_PUBLISH, gate and thinning, validity
    rules. The ament lint tests pass under system Python.
  - Eval: 81 (venv), 47 (system). trn_matcher 45, trn_calibration 6.

### Things that look wrong or are only partly right
1. **At low drift (0.1 %) fusion does not beat good odometry.** The fixes carry about 21 m of label-referenced
   error. A real system would need to weight fixes less when odometry is good, or (better) have labels without
   the systematic offset.
2. **The fused covariance is overconfident against the labels** (NEES 3–5 on flight 10). The 9 s thinning from
   flight 05 does not decorrelate flight 10's along-track label offset, and the fix model has no bias state (by
   rule). Consumers should not trust STRONG on flight 10 as "within 2σ" (only 79–88 % of frames are inside the
   95 % ellipse).
3. **Flight 05 is not a clean check of the fusion.** The fix model (week 5) was fitted on flight 05, so 05's fix
   probabilities are in-sample.
4. **The fixes were computed open-loop.** The matcher's search window was centred on the loader prior (label +
   50 m noise), not on the fused estimate. With real drift the window would follow the fused estimate and could
   miss the true position, so the results at 1–2 % drift are optimistic.
5. **The filter knows the exact drift statistics of the synthetic odometry.** Also optimistic.
6. **The declared outage scenario (1 % drift on flight 10) never reaches DO_NOT_PUBLISH**, because the flight is
   too short. The 2 % outage was added after seeing that.
7. **The chi-square gate uses the inlier σ only, and rejects 25–33 % of offered fixes on flight 10.** Many of them
   might be right fixes rejected because the belief was overconfident (item 2). Both the gate and the mixture
   down-weight outliers, so they overlap.
8. **The belief node depends on the venv** (GTSAM); the launch file starts it with that interpreter. A ROS-native
   GTSAM install would remove this.

## Week 7 — robustness and the consumer (2026-11-22)

### Instructions (Akhil)
1. Freeze the fusion design: an inflation factor fitted on 05 (NEES ≈ 2), and a gate chosen by a rule fixed in
   advance. Report on 10. Re-run the week 6 tables and keep the old ones as pre-freeze.
2. Closed loop.
3. Mismatched drift model.
4. Consumer node with outage replays.
5. Rosbag and figures.
6. Pre-commit lint hook.
7. Freeze list for the test.

Never flight 11. No bias state, no lag correction, no rotation prior.

### Pre-commit hook (`tools/pre-commit`, installed in `.git/hooks/pre-commit`)
- Runs ament flake8 and pep257 on every `src/` package with staged Python files, and blocks the commit on any
  finding. It was tested on a deliberately bad file.
- It caught a long line on its first real use. A bug in the hook itself (pep257 was skipped because of a second
  `cd`) was fixed in `88b463b`.

### 1. Fusion design freeze (`eval/fusion_design.py`, venv)
- **Inflation.** κ multiplies the fix inlier σ.
  - Grid 1.0–3.0 on flight 05, 20 seeds × 4 drift levels, week 6 chi-square gate.
  - Rule: mean NEES closest to 2. Result: **κ = 1.2**, mean NEES 1.94; NEES at 0.1/0.5/1/2 % = 1.68 / 2.11 /
    2.10 / 1.85; 95 % coverage 0.95.
  - **Flight 05 is in-sample for the fix model** (week 5 fitted it on 05), and now also for κ.
  - Source: `eval/results/week7/design_inflation_05.csv`, `design_05.md`.
- **Gate**, with κ = 1.2 on 05. Rule fixed beforehand: lowest RMSE averaged over the four drift levels.

  | Gate | RMSE at 0.1 / 0.5 / 1 / 2 % [m] | Mean RMSE [m] | Fixes gated per run |
  |---|---|---|---|
  | chi2_inlier (week 6) | 9.6 / 17.7 / 24.8 / 34.3 | 21.58 | 24 |
  | off (mixture only) | 10.2 / 17.3 / 23.9 / 34.1 | 21.37 | 0 |
  | **mixture_pvalue** | 10.2 / 17.2 / 23.8 / 33.4 | **21.17** | 1 |

  - **Chosen: mixture_pvalue.** The p-value is the probability of an innovation at least this large under the
    predicted inlier/outlier mixture; reject if below 0.01.
  - The three gates are within 0.4 m of each other. The rule picked one, but they are practically equivalent.
    The week 6 chi-square gate's 25–33 % rejections on flight 10 disappear.
- **Frozen** in `src/trn_fusion/trn_fusion/fusion_frozen.json` (`fix_inflation`, `gate_mode`,
  `design_freeze_week7`). The week 6 version is kept in `eval/results/week6/prefreeze/fusion_frozen_week6.json`.
- **Check on flight 10** (`design_check_10.md`):

  | Drift | RMSE | NEES | 95 % coverage |
  |---|---|---|---|
  | 0.1 % | 21.4 m | 4.67 | 0.71 |
  | 0.5 % | 24.3 m | 3.12 | 0.85 |
  | 1 % | 29.7 m | 2.63 | 0.89 |
  | 2 % | 44.2 m | 2.61 | 0.92 |

  **Mean NEES 3.26, still overconfident on 10.** Inflation fitted on 05 does not absorb flight 10's systematic
  along-track label offset, which is largest relative to the belief at low drift.
- **Week 6 tables re-run with the frozen design.** Command: `eval_fusion.py {10,05} --out
  eval/results/week7/frozen_design`. Pre-freeze tables are moved to `eval/results/week6/prefreeze/` (README says
  pre-freeze). Errors are against dataset labels and include label registration error; odometry SYNTHETIC.

  | Flight | Drift | Fused RMSE (median) | Odometry from true start | NEES | 95 % coverage |
  |---|---|---|---|---|---|
  | 10 | 0.1 % | 21.4 (11.2) | **6.2** | 4.67 | 0.71 |
  | 10 | 0.5 % | 24.3 (16.9) | 32.3 | 3.12 | 0.85 |
  | 10 | 1 % | 29.7 (22.4) | 61.7 | 2.63 | 0.89 |
  | 10 | 2 % | 44.2 (31.8) | 133.2 | 2.61 | 0.92 |
  | 05 | 0.1 % | 10.2 (7.2) | 11.7 | 2.09 | 0.95 |
  | 05 | 0.5 % | 17.2 (14.0) | 53.7 | 1.98 | 0.96 |
  | 05 | 1 % | 23.8 (19.2) | 107.1 | 1.95 | 0.95 |
  | 05 | 2 % | 33.4 (26.0) | 224.6 | 1.79 | 0.96 |

  - Fusion still loses to odometry from the true start at 0.1 % on flight 10.
  - Outage, 2 % drift, flight 10: the error is inside the 2-sigma band on 70 % of the outage frames (78 % before
    the freeze); flight 05: 94 %.

### 3. Filter with the wrong drift model (`eval/drift_mismatch.py`, `drift_mismatch.md`)
- "0.5× / 2× the true drift" is read as the RMS drift level, so the filter uses 0.25× / 4× the random-walk
  coefficient b. Recorded fixes, 20 seeds, frozen design.

  | Filter assumes | NEES | 95 % coverage | RMSE |
  |---|---|---|---|
  | 0.5× (too little drift) | 4.4–8.0 | 0.57–0.74 | up to +29 % (10 at 2 %: 57.2 vs 44.2 m) |
  | 2× (too much drift) | 1.0–1.6 | 0.85–0.99 | equal or slightly better (10 at 2 %: 42.4 m) |

- **Under-assuming drift makes the belief overconfident; over-assuming is safe.** If the drift is uncertain, err
  high.

### 4. Consumer node (`src/trn_consumer`)
- Policy (`policy.py`, unit-tested):
  - STRONG → NORMAL.
  - UNCERTAIN → FLAG_DEGRADED.
  - AGING → REQUEST_FIX_SLOW.
  - DO_NOT_PUBLISH → HOLD_FALLBACK: hold the last STRONG/UNCERTAIN pose and publish a fallback request once.
- `consumer_node` publishes `consumer/action`, `consumer/held_pose` and `consumer/fallback`, and logs every
  change. Software only: nothing is commanded.
- **Outage replays through ROS.** `ros2 launch launch/replay.launch.py ... fix_stop_fraction:=0.3`, seed 0;
  timelines and table from `eval/consumer_timeline.py` → `eval/results/week7/consumer/`.

  | Flight | Drift | First REQUEST_FIX_SLOW after fixes stop | First HOLD_FALLBACK | Error inside 2σ after the stop |
  |---|---|---|---|---|
  | 10 | 1 % | 78 s | never | 100 % |
  | 10 | 2 % | 0 s | 347 s | 70 % |
  | 05 | 1 % | 83 s | 1063 s | 100 % |
  | 05 | 2 % | 6 s | 245 s | 94 % |

  The held pose is stale by 0.8–1.4 km at the end, because the replayed vehicle keeps moving.
- **Bug found while testing.**
  - What happened: with all cores busy, the belief node (slow GTSAM import) started after the replay. It began
    the graph at the frame-0 prior, but the vehicle had already moved on (first odometry at t = 37 s on 05).
    The gate then rejected every fix (0 fused of 126) and the belief never recovered.
  - Fixes:
    - The replay now waits for subscribers.
    - The belief node refuses a prior more than 1 s older than its first odometry; it stays DO_NOT_PUBLISH with
      the reason "prior is stale".
  - **Wider lesson:** once the belief is far from the truth and confident, a gate locks it out. There is no
    re-initialisation path. The week 8 test does not exercise this, but a real system needs one.

### 5. Rosbag and figures
- Rosbag of the flight 10 replay (1 % drift, seed 0, fixes throughout): `~/data/rosbags/replay_10_1pct_seed0`,
  669 messages over 28 s at 25× speed (odom 144, terrain_fix 139, nav_belief 192, consumer). It stays outside the
  repo: its odometry and fixes are derived from dataset labels (no redistribution).
- Figures (`eval/make_figures.py` → `docs/figures/`):
  - `drift_sweep.png`: frozen design, both flights.
  - `validity_timeline.png`: read back from the rosbag; error inside 2σ on 92 % of frames.
  - `calibration_reliability.png`: week 5.
- PX4 hold command: skipped.

### 7. Freeze list
- `docs/frozen_for_test.md` lists 18 items with files.
- Still OPEN:
  - test modes for the calibration and fusion evaluation scripts (they refuse flight 11 by design);
  - open loop vs closed loop for the headline numbers;
  - the empty headline table templates.

### 2. Closed loop (`eval/closed_loop.py`, venv; finished 2026-11-21)
- **What changes.** The matcher no longer searches around the dataset prior (label + 50 m noise). It searches
  around the FUSED prediction.
  - Window: max(150 m, 3 × the predicted 1-sigma), capped at the map extent and 1000 m.
  - Only at the thinned fix times (≥ 9 s since the last fused fix).
  - Frozen matcher (accept-all) and frozen fusion design; same odometry seeds as the open loop.
  - 5 seeds × 4 drift levels × flights 10 and 05, 14 processes, detached with a PID file.
- **Calibration caveat.** The week 5 calibration was fitted with ±150 m windows; larger windows would make wrong
  matches more likely than it assumes. In practice the window stayed at 150 m (p95 and max 150 m; one call at
  152 m), so the calibration applied as fitted.
- **Environment.** These runs use the venv (OpenCV 5.0), so matcher numbers differ slightly from the
  system-Python reference runs (regression test: positions within 0.5 m, peak within 0.002).
- Results (`eval/results/week7/closed_loop/summary.md`). Track lost = fused error > 150 m for ≥ 3 consecutive
  frames. Errors are against dataset labels and include label registration error; odometry SYNTHETIC.

  | Flight | Drift | Closed-loop RMSE | Open-loop RMSE (same seeds) | Runs that lose track | Wrong candidates (> 50 m) | No candidate | Max fused error per run |
  |---|---|---|---|---|---|---|---|
  | 10 | 0.1 % | 21.5 | 21.3 | 0/5 | 40.0 % | 4.8 % | 65–66 m |
  | 10 | 0.5 % | 23.4 | 22.5 | 0/5 | 39.7 % | 4.8 % | 65 m |
  | 10 | 1 % | 27.7 | 26.9 | 0/5 | 41.4 % | 2.8 % | 65–82 m |
  | 10 | 2 % | 49.6 | 51.9 | 0/5 | 39.2 % | 3.6 % | 91–161 m |
  | 05 | 0.1 % | 10.7 | 10.3 | 0/5 | 14.0 % | 0 % | 48–51 m |
  | 05 | 0.5 % | 17.4 | 17.2 | 0/5 | 13.6 % | 0 % | 46–57 m |
  | 05 | 1 % | 24.8 | 24.4 | 0/5 | 13.3 % | 0.1 % | 53–104 m |
  | 05 | 2 % | 33.3 | 33.6 | 0/5 | 13.1 % | 0.1 % | 78–124 m |

- **Reading.**
  - With fixes every 9 s, closed and open loop give the same answer within about 2 m. The fused prediction is
    usually within 150 m, so the window is the same size and nearly the same place.
  - No run lost track. Single excursions reached 161 m (flight 10 at 2 %) and recovered.
  - The open-loop results of weeks 6–7 are therefore not optimistic at these drift levels, as long as fixes keep
    coming.
  - Not tested: closed loop during a fix outage. That is where the window would grow, and where the week 5
    calibration (±150 m) would no longer hold.
- **Two problems while running.**
  1. **Naming bug (mine).** Run names like `05_0.1_3` contain a dot, so `Path.with_suffix` treated `.1_3` as a
     suffix. All 0.1 % and 0.5 % runs of a flight wrote to one file, and later runs were skipped as "done".
     - The collided files are kept in `runs/_invalid_name_collision/` (not used, README).
     - The four valid flight 05 1 % runs were kept; the rest were re-run. Fixed in `2e3fcd5`.
  2. **WSL shut down when the Claude Code session ended** (twice, "up 0 min" afterwards). That killed the
     detached runs after about 95 minutes, just before the flight 05 runs (about 95 min each) finished.
     - Fixed in `cdf0b9e`: every matcher call is appended to `runs/<name>.cache.jsonl` (flushed and fsynced).
       A restarted run replays the deterministic fusion and reuses the cached calls. Checked: a cut cache gives
       identical attempts. A cached call made around a different prediction stops the run.
     - The caches hold label-derived positions and are git-ignored.
     - The third launch ran to completion in 2 h 37 min.

### 2026-11-21 — end of week 7: test status
- One fusion test was broken by the design freeze and went unnoticed until the final test run:
  `test_far_outlier_fix_barely_moves_the_estimate`.
  - Cause: the frozen gate (mixture_pvalue) rejects the 400 m test fix before the factor is used. The venv
    fusion tests had not been re-run after `88b463b`.
  - Fixed: the test now turns the gate off to test the factor itself.
  - The pre-commit hook now also runs `test_fusion.py` in the venv whenever `trn_fusion` changes (`2213d26`).
- Final run:
  - eval: 81 passed (venv), 47 passed (system Python).
  - trn_matcher: 45 passed, 1 skipped (template copyright test).
  - trn_calibration: 6 passed, 1 skipped.
  - trn_fusion: 8 passed (venv), lint passed (system Python).
  - trn_consumer: 5 passed, 1 skipped.

## Week 8 — pre-registration, the single test run, write-up (2026-11-21)

### Pre-registration (tag `pre-test`, commit `a1d57c0`)
- `docs/test_preregistration.md` was written before any computation on flight 11:
  - Headline = closed loop (5 seeds); secondary = open loop (20 seeds).
  - Empty tables T1–T4: fused error with odometry-only and raw-fix baselines; NEES and coverage; belief states with
    their wrong rates; matcher acceptance and fix wrong rates against "the calibration's promise" (mean predicted
    P(wrong)); calibration metrics with sharpness.
  - Predictions P1–P3, and what we would say if each failed.
  - The label-registration caveat on every table.
- `docs/frozen_manifest.json`: SHA-256 of 26 frozen files, including the pre-registration itself.
- The three open freeze items were resolved: the runner, the headline choice, and the tables.

### Test runner (tag `test-runner`, commit `8c0740f`)
- `eval/run_test.py` loads only frozen files and fits nothing.
- It refuses to run unless:
  - the environment matches;
  - the tracked tree is clean;
  - `pre-test` is an ancestor of HEAD;
  - every manifest hash matches, with the manifest read from the tag, not the working tree.
- A lock file refuses a second run. `--resume` continues only an unfinished run.
- Every matcher call is fsynced to a cache. Label-derived positions go to the git-ignored `private/` folder.
- Tests (`eval/test_run_test.py`, 7): dirty tree, untracked files allowed, hash mismatch, manifest from the tag,
  missing tag, second run, resume of a completed run, resume without a start.
- Before the run, a dry run on 15 flight 10 frames (scratchpad) exercised every pass. The existing scripts still
  refuse flight 11; no guard was weakened.

### The run
- Command: `env -u PYTHONPATH ~/venvs/trn/bin/python eval/run_test.py --workers 14`, detached (PID file).
- Timeline:
  - started 2026-11-21 14:41;
  - matcher pass on 590 frames done in about 26 min;
  - closed loop: 20 runs of about 303 matcher calls each.
- **One resume.**
  - WSL shut down with the session at about 17:40, after 14 of the 20 closed-loop runs had finished.
  - Resumed at 20:17 with `--resume` (recorded in `RUN.lock`). The guards re-checked every hash. The 6 unfinished
    runs replayed their 59 cached calls each and continued.
  - Completed 21:07. No run was repeated.
- Results: `docs/test_results.md` (pre-registered tables, filled) and `eval/results/test_flight11/`. Commit
  `49b8009`, tag `test-results`.

### Results (errors against dataset labels, include label registration error; odometry SYNTHETIC)
- **Closed loop (headline).**
  - Fused RMSE (median) at 0.1 / 0.5 / 1 / 2 %: 8.9 (7.0) / 17.3 (14.3) / 23.8 (19.0) / 34.3 (26.4) m.
  - NEES 2.13 / 1.92 / 1.90 / 1.93; 95 % coverage 0.94–0.96.
  - No track lost.
  - Perfect-start odometry: 20.5 / 91.5 / 199.2 / 396.2 m. Raw fixes: 36.0 m RMSE, median 26.7 m.
- **Open loop:** within 1 m of the closed loop.
- **Belief states:** STRONG about 87 %, UNCERTAIN about 12 %, AGING up to 4 % (at 2 %), DO_NOT_PUBLISH never.
- **Matcher pass.**
  - 577 of 590 frames had a candidate; acceptance by the frozen gate 0.868.
  - Wrong rates were below the calibration's promise in every group except DO_NOT_PUBLISH: accepted 0.086 vs 0.099;
    DO_NOT_PUBLISH 0.556 vs 0.499 (27 fixes).
- **Fix calibration:** NLL 9.208, coverage 0.53 / 0.92 / 0.95, sharpness 50.0 m, ECE 0.035, **AUC 0.597**.
- **Predictions:**
  - P1 (NEES > 2) FAILED: 1.97.
  - P2 (accepted wrong rate above the promise) FAILED: 0.086 vs 0.099.
  - P3a (no gain over perfect-start odometry at 0.1 %) FAILED: 8.9 vs 20.5 m.
  - P3b HELD.
  - The pre-registered wording for each failure is quoted in `docs/test_results.md`.

### Write-up and data
- `README.md` written in plain language: problem, stages, data caveats, results, figures, and nine limitations,
  including every post-hoc decision.
- `docs/private_files.md` (`eval/list_private_files.py`): the tracked files that hold label- or map-derived
  positions and must stay private. The new test results hold errors only; their positions and caches are in the
  git-ignored `private/` folder. The repository stays private; nothing was pushed.

### 2026-11-22 — EXPLORATORY, after the test run, not pre-registered: flight 11 label offset
- Command: `env -u PYTHONPATH ~/venvs/trn/bin/python eval/posthoc_test_offset.py`. It runs `eval/label_offset.py`
  on the test run's accepted fixes (501). The frames file and output are in the git-ignored `private/` folder.
  No test result changed.
- Median offset (fix − label): east −1.9 m, north −1.1 m (|2.1| m); with fixes > 50 m excluded, |2.0| m.
  - Spread: p10–p90 east −20 to +18 m, north −40 to +32 m; MAD 10.6 / 17.0 m.
  - Median error: 24.6 m.
- **Comparison with week 3:** the hand estimate from 2 overlays gave about 30 m (signed mean +8, −29 m). We trust
  this diagnostic for the shared offset (501 fixes against 2 hand-picked, weakly matched overlays).
  - But a single median over both flight directions would cancel a direction-dependent offset like flight 10's
    ±20 m along-track. The wide north spread leaves that possible.
  - The by-direction check (`diag_by_heading.py`) refuses the test split by design, so it was not run. "Small
    label offset" on flight 11 means "small shared offset"; the direction-dependent part is unknown.
