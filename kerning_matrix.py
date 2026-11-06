"""
kerning_matrix.py

Builds a pairwise "how far can glyph B slide left over glyph A" matrix
from the glyph PNGs in pngs_seperate/ and saves it to matrices/.

Algorithm (per pair A, B):
  1. Turn A into a 0/1 matrix (1 = black pixel).
  2. Build A's "halo": every black pixel marks horizontal_dist cells to its
     left/right and vertical_dist cells above/below with 2. The halo is
     padded on the right by horizontal_dist columns, so the safety margin
     also exists just past A's right edge.
  3. Turn B into a 0/1 matrix.
  4. Slide B left over A one pixel at a time (i = 1 .. width(A) // 2).
     At shift i, B's column 0 sits on A's column width(A) - i.
     If any black pixel of B lands on a 1 or 2 of A's halo -> stop.
     Otherwise result = i.
  The result is the number of pixels B can be moved left.
"""

import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image

INPUT_DIR = Path("pngs_seperate")
OUTPUT_DIR = Path("matrices")


def load_glyph(path, threshold=128):
    """Load a PNG as a 0/1 matrix (1 = black, opaque pixel)."""
    arr = np.asarray(Image.open(path).convert("RGBA"), dtype=np.int32)
    luminance = arr[..., :3].mean(axis=2)
    alpha = arr[..., 3]
    return ((alpha >= threshold) & (luminance < threshold)).astype(np.uint8)


def build_halo(glyph, horizontal_dist, vertical_dist):
    """0 = empty, 1 = black pixel, 2 = forbidden zone around black pixels.
    Width is padded by horizontal_dist on the right."""
    height, width = glyph.shape
    halo = np.zeros((height, width + horizontal_dist), dtype=np.uint8)
    for y, x in zip(*np.nonzero(glyph)):
        halo[y, max(0, x - horizontal_dist): x + horizontal_dist + 1] = 2
        halo[max(0, y - vertical_dist): y + vertical_dist + 1, x] = 2
    halo[:, :width][glyph == 1] = 1
    return halo


def fit_distance(halo1, width1, glyph2, max_shift=None):
    """How many pixels glyph2 can be moved left over glyph1 (via its halo)."""
    if halo1.shape[0] != glyph2.shape[0]:
        raise ValueError("Glyphs must have the same height")
    if max_shift is None:
        max_shift = width1 // 2

    blocked = halo1 != 0
    halo_width = halo1.shape[1]
    width2 = glyph2.shape[1]
    black2 = glyph2 == 1

    result = 0
    for i in range(1, max_shift + 1):
        start = width1 - i                    # where glyph2's column 0 lands
        n = min(width2, halo_width - start)   # columns of glyph2 over the halo
        if np.any(blocked[:, start:start + n] & black2[:, :n]):
            break
        result = i
    return result


def compute_pair(img1_path, img2_path, horizontal_dist, vertical_dist):
    """Convenience function for a single pair of PNG files."""
    g1, g2 = load_glyph(img1_path), load_glyph(img2_path)
    halo1 = build_halo(g1, horizontal_dist, vertical_dist)
    return fit_distance(halo1, g1.shape[1], g2)


def _numeric_key(path):
    try:
        return (0, int(path.stem))
    except ValueError:
        return (1, path.stem)


def run_kerning(horizontal_dist=1, vertical_dist=1,
                input_dir=INPUT_DIR, output_dir=OUTPUT_DIR):
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = sorted(input_dir.glob("*.png"), key=_numeric_key)
    if not paths:
        print(f"No PNG files found in {input_dir}")
        return None

    names = [p.stem for p in paths]
    glyphs = [load_glyph(p) for p in paths]
    halos = [build_halo(g, horizontal_dist, vertical_dist) for g in glyphs]

    n = len(paths)
    matrix = np.zeros((n, n), dtype=int)
    for a in range(n):              # left glyph
        for b in range(n):          # right glyph (A vs A included)
            matrix[a, b] = fit_distance(halos[a], glyphs[a].shape[1], glyphs[b])

    base = output_dir / f"kerning_h{horizontal_dist}_v{vertical_dist}"

    # CSV: rows = left glyph, columns = right glyph
    with open(base.with_suffix(".csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["left\\right"] + names)
        for name, row in zip(names, matrix):
            writer.writerow([name] + row.tolist())

    # JSON: {left: {right: pixels}} - handy for the font-building step
    data = {names[a]: {names[b]: int(matrix[a, b]) for b in range(n)}
            for a in range(n)}
    with open(base.with_suffix(".json"), "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved {n}x{n} matrix to {base}.csv and {base}.json")
    return matrix