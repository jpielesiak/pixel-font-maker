import os
from PIL import Image


def run_png_to_svg(input_dir="pngs_seperate", output_dir="svgs"):
    os.makedirs(output_dir, exist_ok=True)
    count = 0

    for fname in sorted(os.listdir(input_dir)):
        if not fname.lower().endswith(".png"):
            continue

        img = Image.open(os.path.join(input_dir, fname)).convert("RGBA")
        width, height = img.size
        px = img.load()

        def is_black(x, y):
            r, g, b, a = px[x, y]
            return a > 0 and (r, g, b) == (0, 0, 0)

        # Merge each horizontal run of black pixels into one rectangle,
        # and put all rectangles into a single path (no seams).
        parts = []
        for y in range(height):
            x = 0
            while x < width:
                if is_black(x, y):
                    start = x
                    while x < width and is_black(x, y):
                        x += 1
                    w = x - start
                    parts.append(f"M{start} {y}h{w}v1h-{w}z")
                else:
                    x += 1

        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">\n'
            f'  <path d="{"".join(parts)}" fill="black"/>\n'
            f"</svg>\n"
        )

        with open(os.path.join(output_dir, f"{count}.svg"), "w") as f:
            f.write(svg)
        count += 1

    print(f"Converted {count} letters to SVG in '{output_dir}'")