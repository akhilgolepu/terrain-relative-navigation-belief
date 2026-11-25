# Data

No data is committed to this repo. Datasets live in `~/data/`.

Each dataset gets a section here with its source, the exact files downloaded, sizes, and licence,
added in the week it is first used.

## TUM VI (week 2: VIO baseline)

- Source: https://cvg.cit.tum.de/data/datasets/vi-dataset, files from https://vision.in.tum.de/tumvi/calibrated/512_16/
- Licence: Creative Commons Attribution 4.0 (CC BY 4.0). Attribution: Schubert, Goll, Demmel, Usenko, Stückler, Cremers,
  "The TUM VI Benchmark for Evaluating Visual-Inertial Odometry", IROS 2018.
- Used: the `room` sequences only, because they have motion-capture ground truth for the entire trajectory.
- Format: ROS 1 bags, 512x512 stereo fisheye at 20 Hz, IMU at 200 Hz. Converted to ROS 2 with `rosbags-convert`.

| File | Bytes | MD5 | Local path |
|---|---|---|---|
| dataset-room1_512_16.bag | 2,971,525,053 | 8aa20cf81bedac03e45c78239ce156c0 | `~/data/tumvi/` |
| dataset-room2_512_16.bag | 3,035,570,964 | a70ce1fc5585042af812427e9ab85752 | `~/data/tumvi/` (not downloaded yet) |

Download one file at a time and check it:

```bash
cd ~/data/tumvi
wget --tries=1 --limit-rate=20m https://vision.in.tum.de/tumvi/calibrated/512_16/dataset-room1_512_16.bag
wget https://vision.in.tum.de/tumvi/calibrated/512_16/dataset-room1_512_16.bag.md5
md5sum -c dataset-room1_512_16.bag.md5
```

## EuRoC MAV (not used)

Planned for week 2, but the ETH Research Collection server answered HTTP 429 to our scripted requests, so nothing was
downloaded (see `docs/log.md`, 2026-11-13 and 2026-11-14). Licence there: "In Copyright - Non-Commercial Use Permitted".

## Licence notes for later weeks

- UAV-VisLoc and VPAIR are academic use only: no redistribution.

## UAV-VisLoc (week 3: map side and data loader)

- Source: Zenodo record 19603534, "UAV-VisLoc: A Large-scale UAV Dataset with Continuous Trajectories for Visual
  Geo-localization", v1.0 (2026-05-18), DOI 10.5281/zenodo.19603534, https://zenodo.org/records/19603534.
  Cite the record / the authors' paper (Xu, Chen, Cao, Wang, Wei, Liu, Wang, Meng et al.).
- Licence: the record has no licence selected, and its README defers to the record. The satellite chips come from Google
  Earth Pro and are subject to Google Earth/Maps terms and attribution. Treated as **academic research use only, no
  redistribution**: no images, chips, overlays or samples are committed (see `.gitignore`); exact terms text quoted in
  `docs/log.md` (2026-11-18).
- Contents per flight zip `XX.zip` → `XX/`: `UAV-image/` (aerial JPGs, already north-up, no EXIF), `satellite-tile/`
  (JPG chips of a lat/lon-grid satellite map, 50 % overlap, file `satellite<XX>_<row>_<col>.jpg`),
  `XX-UAV-coordinates.csv` (per image: lat, lon, height, angles; heading = Phi2, or Phi1 where Phi2 is '-'),
  `XX-satellite-tile-coordinates.csv` (chip centre lat/lon).
- Splits (whole regions per split, `eval/splits.json`): hebei_huailai = flight 10 (tune, RGB plains/farmland);
  yunnan = flight 05 (calibrate, RGB mountainous); gansu = flight 11 (test, RGB arid).
- **Flights 18, 19, 20 (jiangsu_wuxi): thermal infrared, excluded from tune/calibrate/test, reserved as a cross-modal
  stress test.** Downloaded and kept on disk. The modality was found from the week 3 overlays; the dataset metadata does
  not say which flights are thermal.
- Downloaded in total: 05, 10, 11, 18, 19, 20 = 4.95 GB (limit 5 GB).
- How to get them: `python3 eval/visloc_download.py 05 10 11 18 19 20` (refuses > 5 GB, checks MD5, extracts to
  `~/data/visloc/flights/`). Index of all 30 flights without downloading them: `python3 eval/visloc_remote_index.py`
  (reads only the zips' file lists and CSVs; → `~/data/visloc/index/`).

| File | Bytes | MD5 (= record) | Local path |
|---|---|---|---|
| 05.zip (yunnan, calibrate; 473 images, 522 chips) | 600,568,121 | 12346ad958df3bb372e98916b68d1ea6 | `~/data/visloc/zips/`, extracted to `~/data/visloc/flights/05/` |
| 10.zip (hebei_huailai, tune; 144 images, 540 chips) | 143,528,824 | be11691d0993ab6db537b6aa8d674fee | `~/data/visloc/zips/`, extracted to `~/data/visloc/flights/10/` |
| 11.zip (gansu, test; 590 images, 1150 chips) | 3,491,364,359 | 97da09cc7aef00c35fa086425b4d2ac5 | `~/data/visloc/zips/`, extracted to `~/data/visloc/flights/11/` |
| 18.zip (jiangsu_wuxi, excluded: thermal infrared; 305 images, 1976 chips) | 199,351,774 | cd024e2929612015e1f0d0f0e125b9d4 | `~/data/visloc/zips/`, extracted to `~/data/visloc/flights/18/` |
| 19.zip (jiangsu_wuxi, excluded: thermal infrared; 352 images, 1140 chips) | 264,849,047 | f499e866cc2832b6b4971ed7ae05dfeb | `~/data/visloc/zips/`, extracted to `~/data/visloc/flights/19/` |
| 20.zip (jiangsu_wuxi, excluded: thermal infrared; 350 images, 2442 chips) | 248,240,985 | 2978179cebb0e7e22633e7ffff0dd695 | `~/data/visloc/zips/`, extracted to `~/data/visloc/flights/20/` |

Total 4,947,903,110 bytes. MD5s were checked against the Zenodo record by `eval/visloc_download.py` after each
download; flight 10 was rechecked with `md5sum` on 2026-11-19.
