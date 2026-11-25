"""Replay one flight through the fusion: SYNTHETIC odometry + recorded fix candidates -> NavBelief.

  ros2 launch launch/replay.launch.py flight:=10 drift_pct:=1.0 seed:=0 speed:=10.0 \
      [fix_stop_fraction:=0.3] [consumer:=true] [log_csv:=PATH] [consumer_log:=PATH]
Flight 11 (test) is refused by the replay node. The belief node runs with the venv interpreter
(~/venvs/trn/bin/python), the only one with GTSAM; ROS must be sourced (install/setup.bash).
"""
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

VENV_PY = os.path.expanduser('~/venvs/trn/bin/python')


def generate_launch_description():
    args = {k: DeclareLaunchArgument(k, default_value=v) for k, v in
            {'flight': '10', 'drift_pct': '1.0', 'seed': '0', 'speed': '10.0',
             'use_fixes': 'true', 'log_csv': 'none', 'fix_stop_fraction': '1.0',
             'consumer': 'true', 'consumer_log': 'none'}.items()}
    lc = {k: LaunchConfiguration(k) for k in args}
    env = dict(os.environ)
    env.pop('PYTHONNOUSERSITE', None)
    belief = ExecuteProcess(
        cmd=[VENV_PY, '-m', 'trn_fusion.belief_node', '--ros-args',
             '-p', ['drift_pct:=', lc['drift_pct']], '-p', ['use_fixes:=', lc['use_fixes']],
             '-p', ['log_csv:=', lc['log_csv']]],
        output='screen', additional_env={'PYTHONUNBUFFERED': '1'})
    replay = Node(package='trn_fusion', executable='replay_node', output='screen',
                  parameters=[{'flight': ParameterValue(lc['flight'], value_type=str),
                               'drift_pct': ParameterValue(lc['drift_pct'], value_type=float),
                               'seed': ParameterValue(lc['seed'], value_type=int),
                               'speed': ParameterValue(lc['speed'], value_type=float),
                               'use_fixes': lc['use_fixes'],
                               'fix_stop_fraction': ParameterValue(lc['fix_stop_fraction'],
                                                                   value_type=float)}])
    consumer = Node(package='trn_consumer', executable='consumer_node', output='screen',
                    parameters=[{'log_csv': lc['consumer_log']}],
                    condition=IfCondition(lc['consumer']))
    return LaunchDescription(list(args.values()) + [belief, replay, consumer])
