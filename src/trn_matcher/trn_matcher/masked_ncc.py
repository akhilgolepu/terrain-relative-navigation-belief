"""
Masked normalised cross-correlation (NCC) of templates against one image, via FFT.

Both sides have a mask: pixels where the mask is False take no part in the correlation, on
the map (no imagery) and on the template (corners created by rotating the aerial image). At
every template position the NCC is computed only over the pixels valid in BOTH, with the mean
and variance of each side taken over those same pixels (Padfield, "Masked object registration
in the Fourier domain", IEEE TIP 2012). Six correlations give everything needed:

    n    = sum(Mi * Mt)            number of overlapping valid pixels
    sI   = sum(I Mi * Mt)          sI2 = sum(I^2 Mi * Mt)
    sT   = sum(Mi * T Mt)          sT2 = sum(Mi * T^2 Mt)
    sIT  = sum(I Mi * T Mt)
    ncc  = (sIT - sI sT / n) / sqrt((sI2 - sI^2 / n) (sT2 - sT^2 / n))

Output is 'valid' mode: entry (y, x) has the template's top-left pixel on image pixel (y, x).
"""
from __future__ import annotations

import numpy as np
from scipy import fft

_EPS_VAR = 1e-6   # minimum variance per pixel (features are about unit scale)


class MaskedCorrelator:
    """Correlate many templates (up to max_shape) against one fixed masked image."""

    def __init__(self, image: np.ndarray, mask: np.ndarray, max_shape: tuple[int, int]):
        """Precompute the image-side FFTs."""
        self.h, self.w = image.shape
        self.s = (fft.next_fast_len(self.h + max_shape[0] - 1, real=True),
                  fft.next_fast_len(self.w + max_shape[1] - 1, real=True))
        m = mask.astype(np.float64)
        i = np.where(mask, image, 0.0).astype(np.float64)
        self._f_m = fft.rfft2(m, self.s)
        self._f_i = fft.rfft2(i, self.s)
        self._f_i2 = fft.rfft2(i * i, self.s)

    def _corr(self, fa, fb, th: int, tw: int) -> np.ndarray:
        """Return the valid part of the correlation from two spectra."""
        return fft.irfft2(fa * fb, self.s)[th - 1:self.h, tw - 1:self.w]

    def ncc(self, template: np.ndarray, tmask: np.ndarray,
            min_overlap: float) -> tuple[np.ndarray, np.ndarray]:
        """
        Return (ncc, overlap) over all template positions fully inside the image.

        ncc is NaN where fewer than min_overlap x (valid template pixels) overlap valid image
        pixels, or where either side has no variance. overlap is the fraction of the template's
        valid pixels that land on valid image pixels.
        """
        th, tw = template.shape
        if th > self.h or tw > self.w:
            raise ValueError('template larger than image')
        tm = tmask.astype(np.float64)[::-1, ::-1]
        t = np.where(tmask, template, 0.0).astype(np.float64)[::-1, ::-1]
        f_tm, f_t, f_t2 = (fft.rfft2(a, self.s) for a in (tm, t, t * t))
        n = np.rint(self._corr(self._f_m, f_tm, th, tw))
        s_i = self._corr(self._f_i, f_tm, th, tw)
        s_i2 = self._corr(self._f_i2, f_tm, th, tw)
        s_t = self._corr(self._f_m, f_t, th, tw)
        s_t2 = self._corr(self._f_m, f_t2, th, tw)
        s_it = self._corr(self._f_i, f_t, th, tw)
        n_tot = max(float(tm.sum()), 1.0)
        with np.errstate(divide='ignore', invalid='ignore'):
            n_safe = np.maximum(n, 1.0)
            v_i = s_i2 - s_i * s_i / n_safe
            v_t = s_t2 - s_t * s_t / n_safe
            num = s_it - s_i * s_t / n_safe
            ok = (n >= min_overlap * n_tot) & (v_i > _EPS_VAR * n_safe) & (v_t > _EPS_VAR * n_safe)
            out = np.where(ok, num / np.sqrt(np.where(ok, v_i * v_t, 1.0)), np.nan)
        return np.clip(out, -1.0, 1.0), n / n_tot
