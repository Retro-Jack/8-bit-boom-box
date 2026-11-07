#!/usr/bin/env python3
"""Take the other project's markings off the deck.

    python3 tools/debrand.py

The deck came from an emulator that had its own name on it: a logo on the
left panel and a wordmark across the right. Neither belongs in a library, so
both are painted out.

This has already been run on the committed artwork -- `art/deck.webp` is
clean, and `art/deck-empty.webp` is built from it. The script is kept because
it is the record of what was removed and from where, and because it is safe
to run again: erasing an area that is already plain panel simply refits the
panel over itself.

The patch is the same idea as the one in make-deck-empty.py. A quadratic
surface fitted to a ring just outside the patch supplies the panel's shading,
so the fill picks up whatever gradient is actually there, and grain matched
to the panel's own is added on top -- a smooth fill reads as a plastic smear
against a photograph. Outliers are dropped from the fit so a lit panel edge
clipped by the ring cannot tilt the whole surface.
"""
import os
import sys
import numpy as np
from PIL import Image

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "art")
DECK = os.path.join(ART, "deck.webp")
OUT = sys.argv[1] if len(sys.argv) > 1 else DECK

# Measured off deck.webp, in its own 1200x507 pixels. Each box is the mark
# plus a little margin, and stops short of the panels' lit edges -- those are
# part of the moulding and have to survive.
MARKS = [
    ((62, 174, 206, 291), "logo on the left panel"),
    ((782, 366, 1158, 420), "wordmark on the right panel"),
]


def erase(img, box, label):
    x0, y0, x1, y1 = box
    pad = 18
    sub = img[y0 - pad:y1 + pad, x0 - pad:x1 + pad, :3]
    h, w = sub.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    inner = (xx >= pad) & (xx < w - pad) & (yy >= pad) & (yy < h - pad)
    ring = ~inner

    lum = sub.mean(2)
    med = np.median(lum[ring])
    mad = np.median(np.abs(lum[ring] - med)) or 1.0
    ring = ring & (np.abs(lum - med) < 3.0 * 1.4826 * mad)

    X, Y = (xx - w / 2) / 100.0, (yy - h / 2) / 100.0
    terms = [np.ones_like(X), X, Y, X * X, X * Y, Y * Y]
    A = np.column_stack([t[ring] for t in terms])
    full = np.column_stack([t.ravel() for t in terms])
    base = np.empty_like(sub)
    for ch in range(3):
        coef, *_ = np.linalg.lstsq(A, sub[:, :, ch][ring], rcond=None)
        base[:, :, ch] = (full @ coef).reshape(h, w)

    rng = np.random.default_rng(20261107)
    base += rng.normal(0, lum[ring].std() * 0.8, (h, w, 1))

    m = (np.clip((xx - pad + 7) / 7, 0, 1) * np.clip((w - pad - xx + 7) / 7, 0, 1) *
         np.clip((yy - pad + 7) / 7, 0, 1) * np.clip((h - pad - yy + 7) / 7, 0, 1))[:, :, None]
    img[y0 - pad:y1 + pad, x0 - pad:x1 + pad, :3] = sub * (1 - m) + base * m
    print("  painted out the %s (x %d..%d, y %d..%d)" % (label, x0, x1, y0, y1))


img = np.asarray(Image.open(DECK).convert("RGBA")).astype(np.float64).copy()
for box, label in MARKS:
    erase(img, box, label)
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA").save(
    OUT, "WEBP", quality=92, method=6)
print("  wrote", OUT)
