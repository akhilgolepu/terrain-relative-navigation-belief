"""
Appearance-robust feature images for matching an aerial image against an older map.

Steps, for both the aerial image and the map:
  1. grayscale in [0, 1];
  2. local contrast normalisation: subtract the local mean and divide by the local standard
     deviation (Gaussian window), computed only over valid pixels, so haze, exposure and
     brightness differences between the two images largely cancel;
  3. kind 'intensity' keeps that normalised grayscale; kind 'gradient' takes its gradient
     magnitude (edge strength), which keeps where roads, field borders and buildings are but
     not whether a surface is darker or brighter than its surroundings (that flips with season
     and sun).
Pixels near an invalid area are dropped from the returned mask: the jump to "no imagery"
would otherwise look like a strong edge.
"""
from __future__ import annotations

import cv2
import numpy as np

KINDS = ('gradient', 'intensity')
_STD_FLOOR = 0.01      # grayscale units; keeps flat (hazy, uniform) areas from being blown up


def to_gray(rgb: np.ndarray) -> np.ndarray:
    """Return a float32 grayscale image in [0, 1]."""
    return cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0


def _blur(x: np.ndarray, sigma: float) -> np.ndarray:
    return cv2.GaussianBlur(x, (0, 0), sigmaX=sigma, sigmaY=sigma, borderType=cv2.BORDER_REFLECT)


def local_normalise(gray: np.ndarray, mask: np.ndarray, sigma: float) -> np.ndarray:
    """Return (gray - local mean) / local std over valid pixels; 0 where invalid."""
    m = mask.astype(np.float32)
    w = _blur(m, sigma)
    w_safe = np.maximum(w, 1e-6)
    g = gray * m
    mean = _blur(g, sigma) / w_safe
    var = np.maximum(_blur(g * g, sigma) / w_safe - mean * mean, 0.0)
    out = (gray - mean) / np.sqrt(var + _STD_FLOOR ** 2)
    return np.where(mask & (w > 1e-3), out, 0.0).astype(np.float32)


def gradient_magnitude(x: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    """Return the edge strength |grad x| after a light Gaussian smoothing."""
    s = _blur(x, sigma) if sigma > 0 else x
    gx = cv2.Sobel(s, cv2.CV_32F, 1, 0, ksize=3, scale=0.125, borderType=cv2.BORDER_REFLECT)
    gy = cv2.Sobel(s, cv2.CV_32F, 0, 1, ksize=3, scale=0.125, borderType=cv2.BORDER_REFLECT)
    return np.sqrt(gx * gx + gy * gy)


def feature_image(rgb: np.ndarray, mask: np.ndarray | None, kind: str, norm_sigma_px: float,
                  grad_sigma_px: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (feature, valid) for an RGB image and its validity mask (None = all valid).

    norm_sigma_px is the local-normalisation window, grad_sigma_px the smoothing before the
    gradient, both in pixels of this image.
    """
    if kind not in KINDS:
        raise ValueError(f'feature kind must be one of {KINDS}')
    mask = np.ones(rgb.shape[:2], bool) if mask is None else mask.astype(bool)
    z = local_normalise(to_gray(rgb), mask, norm_sigma_px)
    if kind == 'gradient':
        f = gradient_magnitude(z, grad_sigma_px)
        margin = int(np.ceil(2 * grad_sigma_px)) + 2
    else:
        f, margin = z, 1
    valid = mask
    if not mask.all():
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * margin + 1, 2 * margin + 1))
        valid = cv2.erode(mask.astype(np.uint8), k, borderType=cv2.BORDER_REPLICATE).astype(bool)
    return np.where(valid, f, 0.0).astype(np.float32), valid
