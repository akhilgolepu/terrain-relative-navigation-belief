"""
Terrain matcher: masked normalised cross-correlation of edge features, coarse to fine.

Contract: interface.py. Plain-language description: docs/log.md (week 4, "How the matcher
works"). Outline, per frame:
  1. Features: grayscale, local contrast normalisation, gradient magnitude (features.py), for
     the map patch and for the aerial image, at two resolutions: coarse (the image about
     coarse_px pixels across) and fine (about FINE_PX across, not finer than the map).
  2. Coarse search: for every (scale, rotation) on a grid over the search space, resample and
     rotate the image to the map's ground resolution and correlate it with the map (masked
     NCC: no-imagery map pixels and rotated-corner pixels are left out). Candidates are
     compared by the significance of their correlation, z = atanh(NCC) x sqrt(overlap pixels)
     (Fisher z): a raw NCC maximum favours the smallest template, because fewer pixels give
     higher chance correlations, while z has the same no-match spread at every template size.
     Keep, for every candidate centre inside the window, the best z over all (scale, rotation).
  3. Quality: peak = the NCC of the best candidate; ratio = its z / the best z at least
     EXCLUSION_FRAC x footprint away from it (the second peak).
  4. Fine search around the best coarse answer (smaller scale and rotation steps, a few
     pixels of position), then a parabola through the peak and its neighbours for sub-pixel
     position.
  5. Accept if peak >= peak_min and ratio >= ratio_min; otherwise no fix (None).
Diagnostics of the last call (accepted or not) are in MatchResult.diag and self.last_diag.

The four tunable settings are those of MatcherSettings; everything in CAPITALS is fixed by
design, not tuned. The values in use are frozen in matcher_frozen.json.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path

import cv2
import numpy as np

from .features import feature_image
from .interface import DEFAULT_SEARCH, MatchResult, patch_px_to_en, Prior, SearchSpace
from .masked_ncc import MaskedCorrelator
from .tile_store import MapPatch

FROZEN_FILE = Path(__file__).with_name('matcher_frozen.json')

# fixed by design (not tuned)
COARSE_SCALE_STEP = 0.05     # brief: about 0.05
COARSE_ROT_STEP = 1.0        # degrees; brief: 1 degree
FINE_SCALE_STEP = 0.0125     # fine grid: +-2 steps around the coarse answer
FINE_ROT_STEP = 0.25
FINE_PX = 256                # image size across at the fine level (or the map resolution)
NORM_SIGMA_FRAC = 1 / 16     # local-normalisation window, fraction of the footprint
GRAD_SIGMA_PX = 1.0          # smoothing before the gradient, pixels at each level
EXCLUSION_FRAC = 0.25        # second peak at least this x footprint from the first
MIN_OVERLAP = 0.5            # at least half the image must lie on map imagery
REFINE_MARGIN_COARSE_PX = 2  # fine search covers +-2 coarse pixels around the coarse answer
SECOND_PEAK_FLOOR = 1.0      # ratio = z peak / max(z second, this), avoids dividing by ~0
TOPK = 3                     # distinct candidates reported in diag['topk'] (diagnostic only)
TOPK_SEPARATION_M = 20.0     # candidates count as distinct if more than this apart
ROT_PRIOR_NSIGMA = 3.0       # with a rotation prior, search rot_deg +- 3 sigma (inside the range)


@dataclass(frozen=True)
class MatcherSettings:
    """The tunable settings (at most four; see docs/log.md for how each was chosen)."""

    feature: str = 'gradient'   # 'gradient' or 'intensity'
    coarse_px: int = 64         # image size across at the coarse level, pixels
    peak_min: float = 0.0       # accept only if the coarse NCC peak is at least this
    ratio_min: float = 0.0      # ... and peak / second peak is at least this

    @classmethod
    def frozen(cls) -> 'MatcherSettings':
        """Return the committed frozen settings, or the defaults if none are frozen yet."""
        if FROZEN_FILE.exists():
            return cls(**json.loads(FROZEN_FILE.read_text())['settings'])
        return cls()


def _grid(lo: float, hi: float, step: float) -> np.ndarray:
    """Return lo..hi in steps of about step, always including both ends and 0 if inside."""
    if hi - lo < 1e-9:
        return np.array([lo])
    n = max(1, int(round((hi - lo) / step)))
    g = np.linspace(lo, hi, n + 1)
    if lo < 0 < hi and not np.any(np.isclose(g, 0.0)):
        g = np.sort(np.r_[g, 0.0])
    return g


class _Level:
    """The map at one resolution: features, valid mask and an FFT correlator."""

    def __init__(self, patch: MapPatch, k: int, kind: str, norm_sigma_px: float,
                 max_template: int):
        self.k = k
        h, w = (patch.image.shape[0] // k) * k, (patch.image.shape[1] // k) * k
        img, valid = patch.image[:h, :w], patch.valid[:h, :w]
        if k > 1:
            img = cv2.resize(img, (w // k, h // k), interpolation=cv2.INTER_AREA)
            valid = cv2.resize(valid.astype(np.float32), (w // k, h // k),
                               interpolation=cv2.INTER_AREA) > 0.999
        self.feat, self.valid = feature_image(img, valid, kind, norm_sigma_px, GRAD_SIGMA_PX)
        self.max_template = max_template

    def correlator(self) -> MaskedCorrelator:
        m = min(self.max_template, *self.feat.shape)
        return MaskedCorrelator(self.feat, self.valid, (m, m))


def _template(image_feat_cache: dict, image: np.ndarray, factor: float, rot_deg: float,
              kind: str, norm_sigma_px: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Return the image's feature template at `factor` x its pixel size, rotated by rot_deg.

    Positive rot_deg turns the content clockwise on the north-up map. The template is square
    with an odd side; its centre pixel is the image centre; mask False on rotated corners.
    """
    h0, w0 = image.shape[:2]
    size = (max(3, int(round(w0 * factor))), max(3, int(round(h0 * factor))))
    if size not in image_feat_cache:
        small = cv2.resize(image, size, interpolation=cv2.INTER_AREA if factor < 1
                           else cv2.INTER_LINEAR)
        image_feat_cache[size] = feature_image(small, None, kind, norm_sigma_px,
                                               GRAD_SIGMA_PX)[0]
    feat = image_feat_cache[size]
    w, h = size
    a = math.radians(rot_deg)
    c, s = math.cos(a), math.sin(a)
    side = int(math.ceil(w * abs(c) + h * abs(s)))
    side += 1 - side % 2
    rot = np.array([[c, -s], [s, c]])
    shift = rot @ (0.5 - np.array([w / 2, h / 2])) + side / 2 - 0.5   # pixel-centre coords
    m = np.hstack([rot, shift[:, None]]).astype(np.float64)
    tpl = cv2.warpAffine(feat, m, (side, side), flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
    cover = cv2.warpAffine(np.ones((h, w), np.float32), m, (side, side), flags=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
    return tpl, cover > 0.999


def _z(ncc: np.ndarray, n_pixels: np.ndarray) -> np.ndarray:
    """Return the Fisher z significance atanh(ncc) * sqrt(n); -inf where ncc is NaN."""
    with np.errstate(invalid='ignore'):
        z = np.arctanh(np.clip(ncc, -0.999, 0.999)) * np.sqrt(np.maximum(n_pixels, 1.0))
    return np.where(np.isfinite(ncc), z, -np.inf)


def _rot_range(prior: Prior, search: SearchSpace) -> tuple[float, float]:
    """Return the rotation range to search: the search range, narrowed by a rotation prior."""
    lo, hi = search.rot_range_deg
    if prior.rot_deg is None or prior.rot_sigma_deg is None:
        return lo, hi
    half = ROT_PRIOR_NSIGMA * prior.rot_sigma_deg
    p_lo, p_hi = max(lo, prior.rot_deg - half), min(hi, prior.rot_deg + half)
    if p_lo > p_hi:   # prior entirely outside the search range: use the nearest edge
        edge = lo if prior.rot_deg < lo else hi
        return edge, edge
    return p_lo, p_hi


def _top_candidates(best, best_ncc, best_idx, cands, patch, kc, rc) -> list[dict]:
    """
    Return up to TOPK coarse candidates, best first, each > TOPK_SEPARATION_M from the others.

    Diagnostic only: taken from the coarse best-z map; the returned fix is unchanged.
    """
    z = best.copy()
    hc, wc = z.shape
    yy, xx = np.ogrid[:hc, :wc]
    out = []
    for _ in range(TOPK):
        if not np.isfinite(z).any():
            break
        y, x = np.unravel_index(int(np.argmax(z)), z.shape)
        e, n = patch_px_to_en(patch, (x + 0.5) * kc, (y + 0.5) * kc)
        s, r = cands[best_idx[y, x]]
        out.append({'east': round(float(e), 2), 'north': round(float(n), 2),
                    'z': round(float(best[y, x]), 3), 'ncc': round(float(best_ncc[y, x]), 4),
                    'scale': round(float(s), 4), 'rot_deg': round(float(r), 3)})
        z[(yy - y) ** 2 + (xx - x) ** 2 <= (TOPK_SEPARATION_M / rc) ** 2] = -np.inf
    return out


def _subpixel(surface: np.ndarray, y: int, x: int) -> tuple[float, float]:
    """Return the parabola-vertex offset (dy, dx) in [-0.5, 0.5] around a 2-D maximum."""
    def vertex(a, b, c):
        d = a - 2 * b + c
        if not all(np.isfinite((a, b, c))) or d >= 0:
            return 0.0
        return float(np.clip(0.5 * (a - c) / d, -0.5, 0.5))
    h, w = surface.shape
    dy = vertex(surface[y - 1, x], surface[y, x], surface[y + 1, x]) if 0 < y < h - 1 else 0.0
    dx = vertex(surface[y, x - 1], surface[y, x], surface[y, x + 1]) if 0 < x < w - 1 else 0.0
    return dy, dx


class FeatureMatcher:
    """Masked NCC terrain matcher; settings default to the frozen ones."""

    name = 'ncc'

    def __init__(self, settings: MatcherSettings | None = None, accept_all: bool = False,
                 **overrides):
        """
        Use the given settings (or the frozen ones), with keyword overrides.

        accept_all=True returns the best candidate for every frame that has one, whatever the
        peak/ratio gate says; the gate's verdict is kept in diag['gate_pass'] (and 'accepted').
        It is not a setting: matcher_frozen.json is unchanged and the candidate is identical.
        """
        s = settings or MatcherSettings.frozen()
        self.settings = replace(s, **overrides) if overrides else s
        self.accept_all = accept_all
        self.last_diag: dict = {}

    def match(self, image: np.ndarray, map_patch: MapPatch, prior: Prior,
              search: SearchSpace = DEFAULT_SEARCH) -> MatchResult | None:
        """Return the fix, or None when the evidence is weak (see the module docstring)."""
        st = self.settings
        diag = {'feature': st.feature, 'coarse_px': st.coarse_px}
        self.last_diag = diag
        foot, m0 = prior.footprint_m, map_patch.m_per_px
        long_side = max(image.shape[:2])

        # coarse level
        kc = max(1, int(round(foot / st.coarse_px / m0)))
        rc = kc * m0
        scales = _grid(*search.scale_range, COARSE_SCALE_STEP)
        rot_lo, rot_hi = _rot_range(prior, search)
        rots = _grid(rot_lo, rot_hi, COARSE_ROT_STEP)
        if prior.rot_deg is not None:
            diag.update(rot_prior_deg=round(prior.rot_deg, 3),
                        rot_prior_sigma_deg=prior.rot_sigma_deg,
                        rot_search_deg=[round(rot_lo, 3), round(rot_hi, 3)])
        max_t = self._max_template(long_side, foot, rc, search)
        lvl = _Level(map_patch, kc, st.feature, NORM_SIGMA_FRAC * foot / rc, max_t)
        corr = lvl.correlator()
        hc, wc = lvl.feat.shape
        best = np.full((hc, wc), -np.inf)        # best z over candidates
        best_ncc = np.full((hc, wc), np.nan)     # NCC of that candidate
        best_idx = np.full((hc, wc), -1, int)
        cache: dict = {}
        cands = [(s, r) for s in scales for r in rots]
        for idx, (s, r) in enumerate(cands):
            factor = foot * s / long_side / rc
            tpl, tm = _template(cache, image, factor, r, st.feature, NORM_SIGMA_FRAC * foot / rc)
            if tpl.shape[0] > min(hc, wc):
                continue
            ncc, ov = corr.ncc(tpl, tm, MIN_OVERLAP)
            z = _z(ncc, ov * tm.sum())
            off = (tpl.shape[0] - 1) // 2
            win = (slice(off, off + ncc.shape[0]), slice(off, off + ncc.shape[1]))
            better = z > best[win]
            best[win][better] = z[better]
            best_ncc[win][better] = ncc[better]
            best_idx[win][better] = idx
        # only centres inside the search window
        east, north = patch_px_to_en(map_patch, (np.arange(wc) + 0.5) * kc,
                                     (np.arange(hc) + 0.5) * kc)
        inside = ((np.abs(north - prior.north) <= search.window_m)[:, None]
                  & (np.abs(east - prior.east) <= search.window_m)[None, :])
        best[~inside] = -np.inf
        diag.update(n_candidates=len(cands), coarse_m_per_px=round(rc, 4))
        if not np.isfinite(best).any():
            diag.update(accepted=False, reason='no candidate with enough map overlap')
            return None
        y0, x0 = np.unravel_index(int(np.argmax(best)), best.shape)
        peak, peak_z = float(best_ncc[y0, x0]), float(best[y0, x0])
        yy, xx = np.ogrid[:hc, :wc]
        far = (yy - y0) ** 2 + (xx - x0) ** 2 > (EXCLUSION_FRAC * foot / rc) ** 2
        rest = np.where(far, best, -np.inf)
        if np.isfinite(rest).any():
            y1, x1 = np.unravel_index(int(np.argmax(rest)), rest.shape)
            second_z, second = float(best[y1, x1]), float(best_ncc[y1, x1])
        else:
            second_z, second = 0.0, float('nan')
        ratio = peak_z / max(second_z, SECOND_PEAK_FLOOR)
        s_c, r_c = cands[best_idx[y0, x0]]
        diag.update(peak=round(peak, 4), peak_z=round(peak_z, 3), second_peak=round(second, 4),
                    second_z=round(second_z, 3), ratio=round(ratio, 4),
                    coarse_scale=round(s_c, 4), coarse_rot_deg=round(r_c, 3))
        diag['topk'] = _top_candidates(best, best_ncc, best_idx, cands, map_patch, kc, rc)

        # fine level around the coarse answer
        u_c, v_c = (x0 + 0.5) * kc, (y0 + 0.5) * kc          # patch pixels (continuous)
        fine = self._refine(image, map_patch, prior, search, s_c, r_c, u_c, v_c, kc)
        if fine is None:
            diag.update(accepted=False, reason='fine search found no valid overlap')
            return None
        u, v, s_f, r_f, fine_peak, overlap, kf = fine
        e, n = patch_px_to_en(map_patch, u, v)
        e, n = float(e), float(n)
        ce, cn = patch_px_to_en(map_patch, u_c, v_c)
        diag.update(cand_east=round(e, 3), cand_north=round(n, 3),
                    fine_peak=round(fine_peak, 4), overlap_valid_frac=round(overlap, 4),
                    scale=round(s_f, 4), rot_deg=round(r_f, 3), fine_m_per_px=round(kf * m0, 4),
                    coarse_to_fine_m=round(math.hypot(e - float(ce), n - float(cn)), 3),
                    at_scale_edge=bool(np.isclose(s_c, scales[0]) or np.isclose(s_c, scales[-1])),
                    at_rot_edge=bool(np.isclose(r_c, rots[0]) or np.isclose(r_c, rots[-1])))
        if not search.contains(prior, e, n, s_f, r_f):
            diag.update(accepted=False, reason='refined answer outside the search space')
            return None
        accepted = peak >= st.peak_min and ratio >= st.ratio_min
        diag.update(accepted=accepted, gate_pass=accepted, reason='' if accepted else
                    ('peak below peak_min' if peak < st.peak_min else 'ratio below ratio_min'))
        if not (accepted or self.accept_all):
            return None
        return MatchResult(e, n, s_f, r_f, peak, dict(diag))

    @staticmethod
    def _max_template(long_side, foot, res, search) -> int:
        a = math.radians(max(abs(r) for r in search.rot_range_deg))
        extent = foot * search.scale_range[1] / res * (abs(math.cos(a)) + abs(math.sin(a)))
        return int(math.ceil(extent)) + 3

    def _refine(self, image, patch, prior, search, s_c, r_c, u_c, v_c, kc):
        st, foot, m0 = self.settings, prior.footprint_m, patch.m_per_px
        long_side = max(image.shape[:2])
        kf = max(1, int(round(foot / FINE_PX / m0)))
        rf = kf * m0
        lo_s, hi_s = search.scale_range
        lo_r, hi_r = _rot_range(prior, search)
        scales = np.clip(s_c + FINE_SCALE_STEP * np.arange(-2, 3), lo_s, hi_s)
        rots = np.clip(r_c + FINE_ROT_STEP * np.arange(-2, 3), lo_r, hi_r)
        scales, rots = np.unique(scales), np.unique(rots)
        max_t = self._max_template(long_side, foot, rf, search)
        lvl = _Level(patch, kf, st.feature, NORM_SIGMA_FRAC * foot / rf, max_t)
        # crop the fine map around the coarse answer: largest template + margin on each side
        margin = int(math.ceil(REFINE_MARGIN_COARSE_PX * kc / kf)) + 2
        half = max_t // 2 + margin
        cu, cv = int(round(u_c / kf)), int(round(v_c / kf))
        y0, x0 = cv - half, cu - half
        feat = np.zeros((2 * half + 1, 2 * half + 1), np.float32)
        valid = np.zeros_like(feat, bool)
        hh, ww = lvl.feat.shape
        ys = slice(max(0, y0), min(hh, y0 + 2 * half + 1))
        xs = slice(max(0, x0), min(ww, x0 + 2 * half + 1))
        dst = (slice(ys.start - y0, ys.stop - y0), slice(xs.start - x0, xs.stop - x0))
        feat[dst], valid[dst] = lvl.feat[ys, xs], lvl.valid[ys, xs]
        corr = MaskedCorrelator(feat, valid, (min(max_t, feat.shape[0]),) * 2)
        cache: dict = {}
        best = None
        for s in scales:
            for r in rots:
                factor = foot * s / long_side / rf
                tpl, tm = _template(cache, image, factor, r, st.feature,
                                    NORM_SIGMA_FRAC * foot / rf)
                if tpl.shape[0] > feat.shape[0]:
                    continue
                ncc, ov = corr.ncc(tpl, tm, MIN_OVERLAP)
                z = _z(ncc, ov * tm.sum())
                if not np.isfinite(z).any():
                    continue
                y, x = np.unravel_index(int(np.argmax(z)), z.shape)
                if best is None or z[y, x] > best[0]:
                    best = (float(z[y, x]), ncc, ov, y, x, tpl.shape[0], float(s), float(r))
        if best is None:
            return None
        _, ncc, ov, y, x, side, s, r = best
        val = float(ncc[y, x])
        dy, dx = _subpixel(ncc, y, x)
        u = (x0 + x + side / 2 + dx) * kf
        v = (y0 + y + side / 2 + dy) * kf
        return u, v, s, r, val, float(ov[y, x]), kf

    def settings_dict(self) -> dict:
        """Return the settings in use as a plain dict."""
        return asdict(self.settings)
