# Absolute position fix from the terrain matcher (trn_matcher), with the diagnostics that
# week 5 calibrates the covariance from. Use east/north only if has_fix is true.
# Frame: east/north [m] in the region's local ENU frame named in header.frame_id
# ("enu_<region>", origin in eval/splits.json), tangent to WGS84.
std_msgs/Header header
bool has_fix                 # false: no fix (evidence too weak); east/north/scale/rot are NaN
float64 east                 # m, ground position of the image centre
float64 north                # m
float64 scale                # image ground size / nominal footprint
float64 rot_deg              # image up axis, degrees clockwise from north
float64 score                # matcher confidence (= peak)
bool gate_pass               # old peak/ratio gate verdict (accept-all mode publishes every candidate)

# diagnostics, filled for accepted and rejected frames (NaN when not available)
float64 peak                 # NCC of the best candidate, -1..1
float64 peak_ratio           # Fisher z of the best candidate / of the best one >= 1/4 footprint away
float64 overlap_valid_frac   # fraction of the image footprint on map imagery at the answer
float64 prior_east           # m, prior position given to the matcher
float64 prior_north          # m
float64 prior_sigma_m        # prior standard deviation per axis
float64 search_window_m      # half side of the square search window around the prior
float64 footprint_m          # nominal image ground side length (scale 1)
float64 match_time_s         # wall time of the match call
string reason                # why there is no fix ('' when has_fix)
string source                # what was matched, e.g. "10/10_0001.JPG" when replaying the dataset
