# Navigation belief: position estimate plus how far to trust it.
# Consumers must check `validity` before using `pose`.
# header.frame_id names the frame of `pose` (ENU local map frame).

std_msgs/Header header
geometry_msgs/PoseWithCovariance pose
builtin_interfaces/Duration fix_age     # time since the last accepted absolute fix
uint8 validity
uint8 STRONG=0
uint8 AGING=1
uint8 UNCERTAIN=2
uint8 DO_NOT_PUBLISH=3
string reason                           # short human-readable cause of the state
