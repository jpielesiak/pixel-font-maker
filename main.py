import argparse

from separate_pngs import run_separate
from png_to_svg import run_png_to_svg
from kerning_matrix import run_kerning
from build_font import run_build_font, signmap_is_filled, create_signmap_template


def main():
    parser = argparse.ArgumentParser(description="Pipeline runner")
    parser.add_argument("-sep", action="store_true", help="Run PNG separation step")
    parser.add_argument("-svg", action="store_true", help="Run PNG-to-SVG step")
    parser.add_argument("-kern", action="store_true", help="Run kerning matrix step")
    parser.add_argument("-font", action="store_true", help="Run font building step")
    parser.add_argument("--hdist", type=int, default=1, help="Min horizontal gap in pixels")
    parser.add_argument("--vdist", type=int, default=1, help="Min vertical gap in pixels")
    parser.add_argument("--name", default="PixelFont", help="Font family name")
    parser.add_argument("--baseline", type=int, default=0,
                        help="Pixel rows at the bottom of the image that are below the baseline")

    args = parser.parse_args()

    flags = [args.sep, args.svg, args.kern, args.font]
    run_all = not any(flags)

    if run_all or args.sep:
        print("Running PNG separation step...")
        run_separate()

    if run_all or args.svg:
        print("Running PNG-to-SVG step...")
        run_png_to_svg()

    if run_all or args.kern:
        print("Running kerning matrix step...")
        run_kerning(horizontal_dist=args.hdist, vertical_dist=args.vdist)

    if run_all or args.font:
        if not signmap_is_filled():
            print("signmap.txt is missing or empty, skipping font building step.")
            create_signmap_template()
        else:
            print("Running font building step...")
            run_build_font(family=args.name, horizontal_dist=args.hdist,
                           vertical_dist=args.vdist, baseline_px=args.baseline)


if __name__ == "__main__":
    main()