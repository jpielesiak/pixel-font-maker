import argparse

from separate_pngs import run_separate
from png_to_svg import run_png_to_svg


def main():
    parser = argparse.ArgumentParser(description="Pipeline runner")
    parser.add_argument("-sep", action="store_true", help="Run PNG separation step")
    parser.add_argument("-svg", action="store_true", help="Run PNG-to-SVG step")
    parser.add_argument("-con", action="store_true", help="Run consensus step")
    parser.add_argument("-len", action="store_true", help="Run length CSV step")
    args = parser.parse_args()

    flags = [args.sep, args.svg, args.con, args.len]
    run_all = not any(flags)

    if run_all or args.sep:
        print("Running PNG separation step...")
        run_separate()

    if run_all or args.svg:
        print("Running PNG-to-SVG step...")
        run_png_to_svg()

    if run_all or args.con:
        print("Running consensus step...")
        # run_consensus()  # add when the script exists

    if run_all or args.len:
        print("Running length CSV step...")
        # run_lengths()  # add when the script exists


if __name__ == "__main__":
    main()
