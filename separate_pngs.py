import os
from PIL import Image


def run_separate(input_dir="pngs_joined", output_dir="pngs_seperate"):
    os.makedirs(output_dir, exist_ok=True)
    count = 0

    for fname in sorted(os.listdir(input_dir)):
        if not fname.lower().endswith(".png"):
            continue

        img = Image.open(os.path.join(input_dir, fname)).convert("RGBA")
        width, height = img.size
        px = img.load()

        def is_separator_col(cx):
            """True if the column has any non-black, non-transparent pixel (the blue line)."""
            for y in range(height):
                r, g, b, a = px[cx, y]
                if a > 0 and (r, g, b) != (0, 0, 0):
                    return True
            return False

        x = 0
        while x < width:
            start = x
            while x < width and not is_separator_col(x):
                x += 1
            if x >= width:
                break  # no more separators

            # Crop from the start of this letter to the blue line (inclusive),
            # so the blue line sits on the right edge.
            letter = img.crop((start, 0, x + 1, height))

            # Make every non-black, non-transparent pixel transparent (kills the blue line).
            data = list(letter.getdata())
            letter.putdata(
                [
                    (0, 0, 0, 0) if (a > 0 and (r, g, b) != (0, 0, 0))
                    else (r, g, b, a)
                    for r, g, b, a in data
                ]
            )

            # Skip letters with no black pixels left.
            if any(a > 0 and (r, g, b) == (0, 0, 0) for r, g, b, a in letter.getdata()):
                letter.save(os.path.join(output_dir, f"{count}.png"))
                count += 1

            x += 1  # move past the separator

    print(f"Separated {count} letters into '{output_dir}'")
