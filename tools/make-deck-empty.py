#!/usr/bin/env python3
"""Build deck-empty.webp: the deck with no cassette, showing the bay.

    python3 tools/make-deck-empty.py

Inputs are both in the repository, so this reproduces without anything from
outside it:

    art/src/QFX-boombox-empty-bay.png   the render with an empty bay, 1930x815
    art/deck.webp                       the deck with a cassette in it, 1200x507

Unlike in the emulator this came from, both are committed here, so the asset
rebuilds from a fresh clone with nothing fetched.

The problem this solves is that the two are not the same picture. The source
render is still the original purple; the deck we ship has been graded to a
warm near-monochrome. Rather than guess at that grade, it is measured: the
plastic frame around the bay appears in both, untouched, so binning the
source's luminance against the shipped deck's channels over that frame gives
three curves that ARE the grade, whatever it was made of. The curves go on
the bay, and the bay goes in.

Two things worth not undoing.

The bay is composited into deck.webp rather than re-exported from the full
resolution master. deck.webp is that master downscaled and THEN embossed with
the transport symbols on its buttons -- measured, the two differ by a mean of
5.2 and all of it is in the top row. Re-exporting would quietly drop the
symbols. This way every pixel outside the bay is the shipped file's own.

The grade is fitted against a strip of frame held out of the fit, and the
residual is printed. If that number climbs, the curves have stopped
describing the grade and the bay will not match the deck around it.

Note for anyone lining things up: this render puts the spindles 372px apart
at y=440 in master coordinates, while the cassette's hubs in deck.webp are
308 apart at y=457. The two renders disagree. It does not matter today --
the reel animation only runs when a tape is loaded, so the two are never on
screen together -- but do not take the spindles here as the hub positions.
Those are in regions.json.
"""
import os
import sys
import numpy as np
from PIL import Image, ImageFilter

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "art")
SRC = os.path.join(ART, "src", "QFX-boombox-empty-bay.png")
DECK = os.path.join(ART, "deck.webp")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ART, "deck-empty.webp")

MW, MH = 1930, 815          # master coordinates, which the boxes below are in
SW, SH = 1200, 507          # what we ship

# The bay opening, generously bounded. It takes some surrounding frame with
# it, and that frame is identical in both, so it lands on itself after
# grading -- which puts the seam on matching pixels rather than on the
# opening's own edge, where it would show.
BAY = (396, 200, 1216, 724)

# Frame to fit the grade on, and a strip held back to check it against.
FIT = [(330, 196, 396, 724), (1216, 196, 1286, 724), (410, 140, 1200, 196)]
HOLD = [(410, 724, 1200, 772)]

NB = 48
bins = np.linspace(0, 255, NB + 1)
mids = 0.5 * (bins[:-1] + bins[1:])

# The render puts the spindles further apart than the cassette's hubs, so they
# are moved onto them here rather than by editing the source, which stays as
# it arrived. All four centres were found the same way -- a spindle and a hub
# are both rotationally symmetric, so the centre is the point whose
# neighbourhood best matches itself turned 180 degrees, which beats hunting
# for the bright ring (that centroid is pulled towards the lit side, and is
# what first had the hubs 17px too low).
SPINDLES = ((614, 434), (986, 434))      # in the empty-bay render
HUBS = ((643, 440), (952, 440))          # in deck.webp, which is what counts
# WELL_R is the spindle itself: spline and rim detail out to about 64, so 66
# lifts the whole thing. It also clears the raised panel between the hubs once
# moved -- 643+66 against a panel starting near 720, and 952-66 against one
# ending near 880.
WELL_R = 66

# ERASE_R is how much has to be painted out behind it, which is a good deal
# more. The well is sunk into the wall and throws a halo: measured by
# 90-degree sector from the old centre, the wall sits at 37-38 but the sector
# above the well reads 58 at r=60 and does not come back down to 38 until
# r≈96, with the shadow below it equally deep. An azimuthal mean hides this
# -- the bright top and dark bottom cancel -- which is how a first attempt at
# 68 came to leave a visible arc sweeping round the right spindle, on the
# side its move exposed.
ERASE_R = 96
# A flat stretch of back wall: measured, y 290..370 is the only band in the
# bay with no structure in it (sd about 3, nothing bright). Its mottle is
# what the rebuilt wall is textured with.
WALL_TEXTURE = (520, 295, 1080, 365)


def _disc(h, w, cx, cy, r, soft=2.5):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    return np.clip((r - np.hypot(xx - cx, yy - cy)) / soft, 0, 1)


def _rebuild_wall(out, rgb, cx, cy, r):
    """Replace a disc with the back wall that belongs behind it.

    The wall is rebuilt, not cloned. Cloning was the first attempt and it
    showed: the only clean wall is the 80px band above the spindles, which is
    too short for a disc this size and carries a vertical gradient of its own,
    so the patch landed as a visible lighter circle beside each spindle.

    Instead the lighting comes from a quadratic surface fitted to the ring
    just outside the disc -- which is the real wall, so it picks up the bay's
    shading wherever the disc happens to be -- and the faint mottle comes from
    a high-pass of that flat band, tiled. Smooth fill alone reads as plastic.
    """
    pad = int(r) + 22
    y0, y1, x0, x1 = cy - pad, cy + pad, cx - pad, cx + pad
    sub = out[y0:y1, x0:x1]
    h, w = sub.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    d = np.hypot(xx - pad, yy - pad)
    ring = (d > r + 3) & (d < r + 19)

    # Reject what is not wall before fitting. At this radius the ring can
    # clip the raised panel between the hubs, and least squares has no
    # defence against that -- a corner of panel in the sample tilts the whole
    # surface. Anything more than three median deviations off the ring's own
    # median is dropped.
    lum = sub.mean(2)
    med = np.median(lum[ring])
    mad = np.median(np.abs(lum[ring] - med)) or 1.0
    ring = ring & (np.abs(lum - med) < 3.0 * 1.4826 * mad)

    X, Y = (xx - pad) / 100.0, (yy - pad) / 100.0
    terms = [np.ones_like(X), X, Y, X * X, X * Y, Y * Y]
    A = np.column_stack([t[ring] for t in terms])
    full = np.column_stack([t.ravel() for t in terms])
    base = np.empty_like(sub)
    for ch in range(3):
        coef, *_ = np.linalg.lstsq(A, sub[:, :, ch][ring], rcond=None)
        base[:, :, ch] = (full @ coef).reshape(h, w)

    tx0, ty0, tx1, ty1 = WALL_TEXTURE
    band = rgb[ty0:ty1, tx0:tx1]
    blur = np.asarray(Image.fromarray(np.clip(band, 0, 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(4))).astype(np.float64)
    hp = band - blur
    reps = (h // hp.shape[0] + 2, w // hp.shape[1] + 2, 1)
    base += np.tile(hp, reps)[:h, :w]

    m = _disc(h, w, pad, pad, r + 1)[:, :, None]
    out[y0:y1, x0:x1] = sub * (1 - m) + base * m


def _flatten_halo(img, cx, cy, r_from=100, r_to=170):
    """Subtract the brightness dome the old well leaves on the wall.

    Filling a disc is not enough. The well is sunk into the wall and lifts a
    wide, soft halo around itself -- measured from the old centre the wall
    reads 3 to 5 levels high at r=50 and is still a level or two high at
    r=105, fading out somewhere past 150. A disc cannot be opened wide enough
    to swallow that without eating the raised panel between the hubs, and a
    disc that stops inside the halo leaves its own rim showing, which is what
    the eye picks up: a faint arc round each spindle.

    So the dome is measured and subtracted instead. The wall's mean is taken
    in rings, outliers dropped so the panel and the bay's edges do not drag
    it, the far rings are taken as the true level, and the excess is removed
    with a taper to nothing at r_to. No boundary anywhere, so nothing for an
    arc to form on. It runs before the disc is filled, so the surface fit
    that fills it samples wall that is already flat.
    """
    pad = r_to + 6
    y0, y1, x0, x1 = cy - pad, cy + pad, cx - pad, cx + pad
    sub = img[y0:y1, x0:x1, :3]
    h, w = sub.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    d = np.hypot(xx - pad, yy - pad)
    lum = sub.mean(2)

    edges = np.arange(r_from, r_to + 1, 5.0)
    rs, vs = [], []
    for i in range(len(edges) - 1):
        m = (d >= edges[i]) & (d < edges[i + 1])
        if m.sum() < 60:
            continue
        v = lum[m]
        med = np.median(v)
        mad = np.median(np.abs(v - med)) or 1.0
        rs.append((edges[i] + edges[i + 1]) / 2)
        vs.append(v[np.abs(v - med) < 2.5 * 1.4826 * mad].mean())
    if len(rs) < 4:
        return
    rs, vs = np.array(rs), np.array(vs)
    far = vs[-3:].mean()
    excess = vs - far

    prof = np.interp(d, rs, excess, left=excess[0], right=0.0)
    prof *= np.clip((r_to - d) / 40.0, 0, 1)
    share = sub.reshape(-1, 3).mean(0)
    share = share / max(share.mean(), 1e-6)
    img[y0:y1, x0:x1, :3] = sub - prof[:, :, None] * share


# The back wall, inside the bay's own ledges. Everything in here is the flat
# moulding behind the mechanism; the raised panel, the spindles and the head
# carriage sit on it and are carried along rather than levelled.
BACK_WALL = (478, 300, 1122, 548)


def flatten_back_wall(img, target=None):
    """Even out the lighting across the back wall.

    Measured before this ran, the wall swung from 34 to 49 across the bay --
    a broad hump, brightest down the middle, which is how the photograph was
    lit rather than anything the moulding does. It reads as a stain once the
    spindles no longer sit in the bright part.

    The level is taken on a coarse grid, robustly: in each cell the median
    and its deviation decide which pixels are wall, and only those count, so
    the panel and the heads do not drag their cells. Cells with too little
    wall in them borrow from their neighbours. That grid is smoothed, scaled
    up and subtracted as a difference from the target, so features move with
    the wall under them and keep their own contrast -- subtracting a blur of
    the region itself would instead carve a halo round everything.
    """
    x0, y0, x1, y1 = BACK_WALL
    sub = img[y0:y1, x0:x1, :3]
    h, w = sub.shape[:2]
    lum = sub.mean(2)

    # What counts as wall is decided once, over the whole region. Deciding it
    # per cell does not work: in a cell mostly covered by a spindle the
    # majority level IS the spindle, so the cell reports the feature's
    # brightness and the wall gets levelled to it. That put a cell at 12.9
    # against a wall of 40.
    gmed = np.median(lum)
    gmad = np.median(np.abs(lum - gmed)) or 1.0
    is_wall = np.abs(lum - gmed) < 2.0 * 1.4826 * gmad

    GX, GY = 16, 7
    grid = np.full((GY, GX), np.nan)
    for gy in range(GY):
        for gx in range(GX):
            sl = (slice(gy * h // GY, (gy + 1) * h // GY),
                  slice(gx * w // GX, (gx + 1) * w // GX))
            cell, mask = lum[sl], is_wall[sl]
            if mask.sum() > mask.size * 0.25:
                grid[gy, gx] = cell[mask].mean()

    # fill any cell that was mostly feature, from the cells that were not
    ys, xs = np.nonzero(~np.isnan(grid))
    for gy in range(GY):
        for gx in range(GX):
            if np.isnan(grid[gy, gx]):
                d = np.hypot(xs - gx, ys - gy)
                grid[gy, gx] = grid[ys[d.argmin()], xs[d.argmin()]]

    g = Image.fromarray(grid.astype(np.float32), mode="F")
    g = g.resize((w, h), Image.BICUBIC)
    field = np.asarray(g).astype(np.float64)

    if target is None:
        target = float(np.nanmean(grid))
    share = sub.reshape(-1, 3).mean(0)
    share = share / max(share.mean(), 1e-6)

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    edge = np.minimum.reduce([xx, yy, w - 1 - xx, h - 1 - yy])
    m = np.clip(edge / 28.0, 0, 1)[:, :, None]

    img[y0:y1, x0:x1, :3] = sub - (field - target)[:, :, None] * share * m
    print("  back wall levelled to %.1f (was %.1f to %.1f across the bay)"
          % (target, np.nanmin(grid), np.nanmax(grid)))


def move_spindles(rgb):
    """Shift each spindle onto the hub it would actually drive."""
    out = rgb.copy()
    pad = WELL_R + 4
    size = pad * 2

    # Lift both out first: erasing one must not eat the other.
    taken = [rgb[cy - pad:cy + pad, cx - pad:cx + pad].copy() for cx, cy in SPINDLES]

    for cx, cy in SPINDLES:
        _flatten_halo(out, cx, cy)
    for cx, cy in SPINDLES:
        _rebuild_wall(out, out, cx, cy, ERASE_R)

    # Then put them back down on the hubs.
    m = _disc(size, size, pad, pad, WELL_R)[:, :, None]
    for patch, (hx, hy) in zip(taken, HUBS):
        here = out[hy - pad:hy + pad, hx - pad:hx + pad]
        out[hy - pad:hy + pad, hx - pad:hx + pad] = here * (1 - m) + patch * m
    return out


_src = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float64)
if _src.shape[:2] != (MH, MW):
    sys.exit("expected a %dx%d source, got %dx%d" % (MW, MH, _src.shape[1], _src.shape[0]))
_src = move_spindles(_src)
flatten_back_wall(_src)
for (sx_, sy_), (hx_, hy_) in zip(SPINDLES, HUBS):
    print("  spindle (%d,%d) -> hub (%d,%d)   moved %+d,%+d"
          % (sx_, sy_, hx_, hy_, hx_ - sx_, hy_ - sy_))
src_full = Image.fromarray(np.clip(_src, 0, 255).astype(np.uint8), "RGB")
deck = np.asarray(Image.open(DECK).convert("RGBA")).astype(np.float64)

# Fit at the shipped size, so the two sides of the comparison are the same
# scale and the same softness.
src_small = np.asarray(src_full.resize((SW, SH), Image.LANCZOS)).astype(np.float64)
lum_small = src_small @ np.array([0.299, 0.587, 0.114])
sx, sy = SW / MW, SH / MH


def gather(boxes):
    L, C = [], []
    for x0, y0, x1, y1 in boxes:
        a, b = int(round(x0 * sx)), int(round(y0 * sy))
        c, d = int(round(x1 * sx)), int(round(y1 * sy))
        L.append(lum_small[b:d, a:c].ravel())
        C.append(deck[b:d, a:c, :3].reshape(-1, 3))
    return np.concatenate(L), np.vstack(C)


def fit_curves(L, C):
    """Median shipped channel per luminance bin: the grade, whatever it was."""
    idx = np.clip(np.digitize(L, bins) - 1, 0, NB - 1)
    out = np.full((NB, 3), np.nan)
    for b in range(NB):
        m = idx == b
        if m.sum() >= 24:
            out[b] = np.median(C[m], axis=0)
    for ch in range(3):                      # carry across any empty bins
        good = ~np.isnan(out[:, ch])
        out[:, ch] = np.interp(mids, mids[good], out[good, ch])
    return out


def apply_curves(L, curves):
    return np.stack([np.interp(L, mids, curves[:, ch]) for ch in range(3)], -1)


L, C = gather(FIT)
curves = fit_curves(L, C)
print("  grade fitted on %d px of bay frame" % len(L))
for name, boxes in (("fit", FIT), ("held out", HOLD)):
    Lh, Ch = gather(boxes)
    r = np.abs(apply_curves(Lh, curves) - Ch)
    print("  residual, %-9s mean %5.2f   p95 %5.2f" % (name, r.mean(), np.percentile(r, 95)))

# Grade at full resolution, then downscale: grading after the downscale would
# put the curves through averaged pixels and flatten the mechanism's contrast.
lum_full = np.asarray(src_full).astype(np.float64) @ np.array([0.299, 0.587, 0.114])
graded = Image.fromarray(
    np.clip(apply_curves(lum_full, curves), 0, 255).astype(np.uint8), "RGB")
graded_small = np.asarray(graded.resize((SW, SH), Image.LANCZOS)).astype(np.float64)

x0 = int(round(BAY[0] * sx)) + 2
y0 = int(round(BAY[1] * sy)) + 2
x1 = int(round(BAY[2] * sx)) - 2
y1 = int(round(BAY[3] * sy)) - 2
h, w = y1 - y0, x1 - x0
ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
e = np.minimum.reduce([xs, ys, w - 1 - xs, h - 1 - ys])
feather = np.clip(e / 6.0, 0, 1)[:, :, None]

out = deck.copy()
out[y0:y1, x0:x1, :3] = (deck[y0:y1, x0:x1, :3] * (1 - feather) +
                         graded_small[y0:y1, x0:x1] * feather)
# The deck is cut out against the page; the bay is deep inside the silhouette
# and fully opaque, so deck.webp's own alpha carries straight over.
img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")
img.save(OUT, "WEBP", quality=92, method=6)
print("  wrote %s  %dx%d  %s  (bay x %d..%d, y %d..%d)"
      % (OUT, *img.size, img.mode, x0, x1, y0, y1))
