import os
from PIL import Image


def _trace_outlines(black, width, height):
    """Turn a set of black pixels into closed outlines with no internal edges.

    Every pixel side that borders a non-black pixel becomes a directed edge,
    oriented so the black area is always on the right (clockwise on screen).
    Linking the edges gives outer contours (clockwise) and holes
    (counter-clockwise), which fill correctly with the nonzero rule.
    """
    edges = {}  # start point -> list of end points

    def add(a, b):
        edges.setdefault(a, []).append(b)

    for (x, y) in black:
        if (x, y - 1) not in black:
            add((x, y), (x + 1, y))              # top, going right
        if (x + 1, y) not in black:
            add((x + 1, y), (x + 1, y + 1))      # right, going down
        if (x, y + 1) not in black:
            add((x + 1, y + 1), (x, y + 1))      # bottom, going left
        if (x - 1, y) not in black:
            add((x, y + 1), (x, y))              # left, going up

    contours = []
    while edges:
        start = next(iter(edges))
        points = [start]
        current = start
        direction = None
        while True:
            options = edges[current]
            if len(options) == 1 or direction is None:
                nxt = options[0]
            else:
                # Two pixels touching only at a corner: turn right so the
                # pixels stay separate shapes. Then straight, then left.
                dx, dy = direction
                preferred = [(-dy, dx), (dx, dy), (dy, -dx)]
                nxt = next(
                    (p for d in preferred for p in options
                     if (p[0] - current[0], p[1] - current[1]) == d),
                    options[0],
                )
            options.remove(nxt)
            if not options:
                del edges[current]
            direction = (nxt[0] - current[0], nxt[1] - current[1])
            current = nxt
            if current == start:
                break
            points.append(current)
        contours.append(_drop_collinear(points))
    return contours


def _drop_collinear(points):
    """Keep only corner points of a closed polygon."""
    n = len(points)
    result = []
    for i in range(n):
        px, py = points[i - 1]
        cx, cy = points[i]
        nx, ny = points[(i + 1) % n]
        if (cx - px, cy - py) != (0, 0) and (cx - px) * (ny - cy) - (cy - py) * (nx - cx) == 0:
            continue  # straight line through this point
        result.append(points[i])
    return result


def _contour_to_path(points):
    x0, y0 = points[0]
    d = [f"M{x0} {y0}"]
    for x, y in points[1:]:
        d.append(f"L{x} {y}")
    d.append("Z")
    return "".join(d)


def run_png_to_svg(input_dir="pngs_seperate", output_dir="svgs"):
    os.makedirs(output_dir, exist_ok=True)
    count = 0

    for fname in os.listdir(input_dir):
        if not fname.lower().endswith(".png"):
            continue
        stem = os.path.splitext(fname)[0]

        img = Image.open(os.path.join(input_dir, fname)).convert("RGBA")
        width, height = img.size
        px = img.load()

        black = {
            (x, y)
            for y in range(height)
            for x in range(width)
            if px[x, y][3] > 0 and px[x, y][:3] == (0, 0, 0)
        }

        path_data = "".join(_contour_to_path(c) for c in _trace_outlines(black, width, height))

        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">\n'
            f'  <path d="{path_data}" fill="black" fill-rule="nonzero"/>\n'
            f"</svg>\n"
        )

        # Same number as the PNG: 12.png -> 12.svg
        with open(os.path.join(output_dir, f"{stem}.svg"), "w") as f:
            f.write(svg)
        count += 1

    print(f"Converted {count} letters to SVG in '{output_dir}'")