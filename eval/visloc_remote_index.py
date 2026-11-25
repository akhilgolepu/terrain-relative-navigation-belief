#!/usr/bin/env python3
"""Index the UAV-VisLoc flight zips on Zenodo WITHOUT downloading them.

For each XX.zip it reads only the zip's central directory (the file list at the end of the archive) and the two small
coordinate CSVs inside it, plus the first bytes of one UAV image and one satellite chip (enough for the JPEG header),
using HTTP range requests. One request at a time, a pause between requests, and it stops at the first HTTP 429 or 403.
Transient errors (a response cut short, a timeout, a dropped connection) are retried: up to MAX_TRIES tries per request,
with a pause of RETRY_PAUSE_S x try number before each retry; if all tries fail it stops.

Writes, under OUT (default ~/data/visloc/index/; data, never committed):
  XX/XX-UAV-coordinates.csv, XX/XX-satellite-tile-coordinates.csv   copies of the CSVs from the zip
  flight_index.csv                                                    one row per flight (counts, sizes, bbox, columns)
Usage: python3 eval/visloc_remote_index.py [--flights 01 02 ...] [--out ~/data/visloc/index] [--pause-s 1.0]
"""
from __future__ import annotations

import argparse
import csv
import http.client
import io
import socket
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

RECORD = "https://zenodo.org/api/records/19603534"
UA = "trn-belief-research-client"
BLOCK = 1 << 18  # read-ahead block for range requests (256 KiB)
MAX_TRIES = 3
RETRY_PAUSE_S = 5.0
TRANSIENT = (http.client.IncompleteRead, http.client.RemoteDisconnected, TimeoutError, socket.timeout,
             ConnectionResetError, urllib.error.URLError)


class Stop(RuntimeError):
    pass


class HttpRangeFile(io.RawIOBase):
    """Read-only, seekable file over HTTP range requests, with a small block cache (enough for zipfile)."""

    def __init__(self, url: str, size: int, pause_s: float):
        self.url, self.size, self.pause_s, self.pos = url, size, pause_s, 0
        self.cache: dict[int, bytes] = {}
        self.requests = 0
        self.bytes = 0
        self.retries = 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def _fetch(self, start: int, end: int) -> bytes:
        for attempt in range(1, MAX_TRIES + 1):
            time.sleep(self.pause_s if attempt == 1 else RETRY_PAUSE_S * (attempt - 1))
            req = urllib.request.Request(self.url, headers={"User-Agent": UA, "Range": f"bytes={start}-{end - 1}"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    if r.status != 206:
                        raise Stop(f"expected HTTP 206, got {r.status} for {self.url}")
                    data = r.read()
                if len(data) != end - start:
                    raise http.client.IncompleteRead(data, end - start - len(data))
            except urllib.error.HTTPError as e:  # subclass of URLError: handle first
                if e.code in (403, 429):
                    raise Stop(f"HTTP {e.code} from server; stopping as instructed") from e
                raise
            except TRANSIENT as e:
                self.retries += 1
                print(f"  transient error on try {attempt}/{MAX_TRIES} ({type(e).__name__}: {str(e)[:80]})",
                      flush=True)
                if attempt == MAX_TRIES:
                    raise Stop(f"{MAX_TRIES} tries failed for bytes {start}-{end - 1} of {self.url}") from e
                continue
            self.requests += 1
            self.bytes += len(data)
            return data
        raise AssertionError("unreachable")

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        first, last = self.pos // BLOCK, (self.pos + n - 1) // BLOCK
        missing = [b for b in range(first, last + 1) if b not in self.cache]
        if missing:  # one request for the contiguous missing range
            lo, hi = missing[0] * BLOCK, min(self.size, (missing[-1] + 1) * BLOCK)
            data = self._fetch(lo, hi)
            for b in missing:
                self.cache[b] = data[b * BLOCK - lo:(b + 1) * BLOCK - lo]
        buf = b"".join(self.cache[b] for b in range(first, last + 1))
        out = buf[self.pos - first * BLOCK:self.pos - first * BLOCK + n]
        self.pos += len(out)
        return out

    def readinto(self, b) -> int:
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def jpeg_size(zf: zipfile.ZipFile, name: str) -> tuple[int, int] | None:
    """Pixel size from the first 256 KiB of a JPEG member (header only)."""
    from PIL import Image  # system python3-pil
    with zf.open(name) as fh:
        head = fh.read(1 << 18)
    try:
        return Image.open(io.BytesIO(head)).size
    except Exception:  # header not within the first bytes
        return None


def index_flight(flight: str, size: int, out: Path, pause_s: float) -> dict[str, object]:
    url = f"{RECORD}/files/{flight}.zip/content"
    f = HttpRangeFile(url, size, pause_s)
    zf = zipfile.ZipFile(f)
    names = zf.namelist()
    uav = sorted(n for n in names if "/UAV-image/" in n and not n.endswith("/"))
    sat = sorted(n for n in names if "/satellite-tile/" in n and not n.endswith("/"))
    csvs = [n for n in names if n.lower().endswith(".csv")]
    other = sorted({n.split("/")[1] if n.count("/") >= 1 else n for n in names} - {"UAV-image", "satellite-tile", ""})
    (out / flight).mkdir(parents=True, exist_ok=True)
    info: dict[str, object] = {"flight": flight, "zip_bytes": size, "n_entries": len(names), "n_uav_images": len(uav),
                               "n_satellite_tiles": len(sat), "csv_files": " ".join(csvs),
                               "top_level_items": " ".join(other)}
    for n in csvs:
        data = zf.read(n)
        (out / flight / Path(n).name).write_bytes(data)
        text = data.decode("utf-8-sig", errors="replace")
        rows = list(csv.reader(io.StringIO(text)))
        kind = "uav" if "UAV" in Path(n).name else "sat"
        info[f"{kind}_csv_columns"] = "|".join(rows[0]) if rows else ""
        info[f"{kind}_csv_rows"] = len(rows) - 1
        info[f"{kind}_csv_first_row"] = "|".join(rows[1]) if len(rows) > 1 else ""
    exts = sorted({Path(n).suffix.lower() for n in uav + sat})
    info["image_extensions"] = " ".join(exts)
    info["uav_bytes_per_image"] = int(sum(zf.getinfo(n).file_size for n in uav) / max(1, len(uav)))
    info["sat_bytes_per_tile"] = int(sum(zf.getinfo(n).file_size for n in sat) / max(1, len(sat)))
    info["uav_image_px"] = "x".join(map(str, jpeg_size(zf, uav[0]) or ())) if uav else ""
    info["sat_tile_px"] = "x".join(map(str, jpeg_size(zf, sat[0]) or ())) if sat else ""
    info["http_requests"], info["http_bytes"], info["http_retries"] = f.requests, f.bytes, f.retries
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--flights", nargs="+")
    ap.add_argument("--out", type=Path, default=Path.home() / "data/visloc/index")
    ap.add_argument("--pause-s", type=float, default=1.0)
    args = ap.parse_args()
    req = urllib.request.Request(RECORD, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        files = {f["key"]: f for f in json.load(r)["files"]}
    (args.out).mkdir(parents=True, exist_ok=True)
    flights = args.flights or sorted(k[:-4] for k in files if k[:-4].isdigit())
    index_csv = args.out / "flight_index.csv"
    done = {r["flight"]: r for r in csv.DictReader(index_csv.open())} if index_csv.exists() else {}
    rows = [done[f] for f in sorted(done) if f not in flights]  # keep flights indexed earlier
    try:
        for fl in flights:
            info = index_flight(fl, files[f"{fl}.zip"]["size"], args.out, args.pause_s)
            info["zip_md5"] = files[f"{fl}.zip"]["checksum"]
            rows.append(info)
            print(f"{fl}: {info['n_uav_images']} UAV images ({info['uav_image_px']}), {info['n_satellite_tiles']} tiles "
                  f"({info['sat_tile_px']}), {info['http_requests']} requests / {info['http_bytes'] / 1e6:.1f} MB",
                  flush=True)
    except Stop as e:
        print(f"STOPPED: {e}")
        return 3
    finally:
        if rows:
            keys = sorted({k for r in rows for k in r}, key=lambda k: (k != "flight", k))
            rows.sort(key=lambda r: r["flight"])
            with index_csv.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=keys)
                w.writeheader()
                w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
