#!/usr/bin/env python3
"""Download selected UAV-VisLoc flight zips from Zenodo, verify their MD5, and extract them.

- Refuses to start if the selected zips add up to more than --max-gb (default 5).
- One file at a time, rate-limited (--max-mbps, default 20 MB/s), resumes a partial .part file with a Range request.
- Transient errors (response cut short, timeout, dropped connection): up to 3 tries per file with a pause; HTTP 429 or
  403 stops at once. MD5 must match the record's checksum, otherwise it stops.
- Extraction refuses absolute paths and '..' members (archives are untrusted).
Writes ~/data/visloc/zips/XX.zip and ~/data/visloc/flights/XX/ (data, never committed). Academic use only.

Usage: python3 eval/visloc_download.py 05 11 18 19 20
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import socket
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

RECORD = "https://zenodo.org/api/records/19603534"
UA = "trn-belief-research-client"
MAX_TRIES = 3
TRANSIENT = (http.client.IncompleteRead, http.client.RemoteDisconnected, TimeoutError, socket.timeout,
             ConnectionResetError, urllib.error.URLError)


class Stop(RuntimeError):
    pass


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, size: int, dest: Path, max_bps: float) -> None:
    part = dest.with_suffix(".zip.part")
    for attempt in range(1, MAX_TRIES + 1):
        have = part.stat().st_size if part.exists() else 0
        if have == size:
            break
        headers = {"User-Agent": UA}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as r, \
                    part.open("ab" if have else "wb") as out:
                if have and r.status != 206:
                    raise Stop(f"resume asked for bytes {have}- but got HTTP {r.status}")
                t0, got = time.monotonic(), 0
                while chunk := r.read(1 << 20):
                    out.write(chunk)
                    got += len(chunk)
                    ahead = got / max_bps - (time.monotonic() - t0)
                    if ahead > 0:
                        time.sleep(ahead)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                raise Stop(f"HTTP {e.code} from server; stopping as instructed") from e
            raise
        except TRANSIENT as e:
            print(f"  transient error on try {attempt}/{MAX_TRIES}: {type(e).__name__}: {str(e)[:80]}", flush=True)
            if attempt == MAX_TRIES:
                raise Stop(f"{MAX_TRIES} tries failed for {url}") from e
            time.sleep(10 * attempt)
            continue
    if part.stat().st_size != size:
        raise Stop(f"{part} has {part.stat().st_size} bytes, expected {size}")
    part.rename(dest)


def safe_extract(zpath: Path, target: Path) -> int:
    with zipfile.ZipFile(zpath) as zf:
        for name in zf.namelist():
            p = Path(name)
            if p.is_absolute() or ".." in p.parts:
                raise Stop(f"unsafe member path {name!r} in {zpath}")
        zf.extractall(target)
        return len(zf.namelist())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("flights", nargs="+")
    ap.add_argument("--root", type=Path, default=Path.home() / "data/visloc")
    ap.add_argument("--max-gb", type=float, default=5.0)
    ap.add_argument("--max-mbps", type=float, default=20.0)
    args = ap.parse_args()
    with urllib.request.urlopen(urllib.request.Request(RECORD, headers={"User-Agent": UA}), timeout=60) as r:
        files = {f["key"]: f for f in json.load(r)["files"]}
    sel = [files[f"{fl}.zip"] for fl in args.flights]
    total = sum(f["size"] for f in sel)
    print(f"selected {', '.join(args.flights)}: {total / 1e9:.3f} GB (limit {args.max_gb:g} GB)")
    if total > args.max_gb * 1e9:
        print("over the limit; nothing downloaded")
        return 2
    zdir, fdir = args.root / "zips", args.root / "flights"
    zdir.mkdir(parents=True, exist_ok=True)
    fdir.mkdir(parents=True, exist_ok=True)
    try:
        for fl, f in zip(args.flights, sel):
            dest = zdir / f"{fl}.zip"
            want = f["checksum"].removeprefix("md5:")
            if not dest.exists():
                t0 = time.monotonic()
                download(f"{RECORD}/files/{fl}.zip/content", f["size"], dest, args.max_mbps * 1e6)
                print(f"{fl}: downloaded {f['size']:,} bytes in {time.monotonic() - t0:.0f} s", flush=True)
            got = md5(dest)
            if got != want:
                raise Stop(f"{fl}: MD5 {got} does not match record {want}")
            n = safe_extract(dest, fdir)
            print(f"{fl}: MD5 ok ({got}), extracted {n} members to {fdir}", flush=True)
    except Stop as e:
        print(f"STOPPED: {e}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
