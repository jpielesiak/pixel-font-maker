# Pixel Font Pipeline

Turns a set of small pixel-art letter images into an installable font (`.ttf` and `.otf`), with automatically calculated kerning so letters sit close together without touching.

## Requirements

- Python 3.9 or newer
- Pillow, numpy and fontTools

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install Pillow numpy fonttools
```

## Quick start

```bash
python main.py              # first run: builds everything and creates signmap.txt
# fill in signmap.txt (see below)
python main.py -font        # builds the font
```

The finished fonts are in `fonts/`.

## Project layout

| Path | What it is |
|---|---|
| `main.py` | Runs the pipeline |
| `separate_pngs.py` | Step 1: splits the source image into one PNG per letter |
| `png_to_svg.py` | Step 2: turns each letter PNG into an SVG outline |
| `kerning_matrix.py` | Step 3: calculates how close every pair of letters can be |
| `build_font.py` | Step 4: builds the font from the SVGs, `signmap.txt` and the kerning matrix |
| `pngs_seperate/` | One PNG per letter, named `0.png`, `1.png`, … |
| `svgs/` | One SVG per letter, with the same numbers as the PNGs |
| `matrices/` | Kerning matrices (`.csv` and `.json`) |
| `signmap.txt` | Which character each image number represents (written by you) |
| `fonts/` | The finished `.ttf` and `.otf` |

## Running the pipeline

With no flags, every step runs in order. With flags, only the chosen steps run.

| Flag | Step |
|---|---|
| `-sep` | Separate the source image into letter PNGs |
| `-svg` | Convert PNGs to SVGs |
| `-kern` | Calculate the kerning matrix |
| `-font` | Build the font |

Options:

| Option | Default | Meaning |
|---|---|---|
| `--hdist N` | `1` | Minimum empty pixels between two letters side by side |
| `--vdist N` | `1` | Minimum empty pixels between two letters above/below each other |
| `--name "Name"` | `PixelFont` | Font family name, as it appears in font menus |
| `--baseline N` | `0` | Pixel rows at the bottom of each image that hang below the baseline (tails of g, p, y) |

Examples:

```bash
python main.py -kern --hdist 2 --vdist 1
python main.py -font --hdist 2 --vdist 1 --name "My Pixel Font" --baseline 2
python main.py -svg -font          # after editing letter PNGs
```

`--hdist` and `--vdist` must be the same for `-kern` and `-font`, because the font step loads the matrix file named after them (`matrices/kerning_h2_v1.json`).

## signmap.txt

Images are numbered, so the font needs to know which character each number is. If `signmap.txt` is missing or empty, the pipeline runs every step up to the font, then creates a template with one line per SVG:

```
0 
1 
2 
```

Type the character after the space on each line:

```
0 T
1 a
2 *
3 \
4 ~
5  
```

Rules:

- The line is split at the **first** space only, so any character works, including `* \ / | # @ ~ "`.
- Line `5` above is a number followed by **two** spaces: that maps image 5 to the space character. Make sure your editor doesn't delete trailing spaces.
- A line with just a number (or a number and one space) is not filled in yet. Those images are left out of the font and listed in the output.
- One character per line. Each character can only be used once.
- The file is read as UTF-8, so non-Latin characters (ą, ż, ß, …) are fine.

Once at least one line is filled in, the file is never overwritten.

## How kerning works

For every ordered pair of letters (A then B, including A then A), `kerning_matrix.py` calculates how many pixels B can move left towards A:

1. A's pixels are turned into a grid. Every black pixel gets a safety zone of `--hdist` pixels to its left and right and `--vdist` pixels above and below.
2. B is slid left over A one pixel at a time.
3. It stops as soon as any black pixel of B would land on A or its safety zone. The last position that fit is the result.
4. B never moves further than half of A's width, so small marks (accents, dots) can't slide over a whole letter.

A then B can be different from B then A (think `L` followed by `T` versus `T` followed by `L`).

The result is saved as `matrices/kerning_h{hdist}_v{vdist}.csv` (rows are the left letter, columns the right letter) and as `.json`.

When building the font, the most common value in the matrix is subtracted from every letter's width, so it acts as the default spacing. Only pairs that differ from it are stored as kerning pairs.

## Installing and using the font

**Windows:** right-click `fonts/PixelFont.ttf` and choose *Install for all users*. If Windows shows an old version, uninstall it first or rename the new file.

**macOS:** double-click the `.ttf` and click *Install Font*.

**Linux:** copy the `.ttf` to `~/.local/share/fonts/` and run `fc-cache -f`.

Prefer the `.ttf`: it includes a request to renderers not to smooth the letters, which the `.otf` cannot carry.

### Sharp rendering

The letters are 16 px tall, so they look sharpest at sizes that are multiples of 16 px (16, 32, 48 px, which is 12, 24, 36 pt on a standard screen). At those sizes each design pixel covers whole screen pixels, so there are no blurry edges even where smoothing stays on.

Turning smoothing off:

- **Windows:** classic programs follow the font's request. Browsers and Chromium-based apps (like VS Code) smooth anyway.
- **macOS:** no system switch. VS Code has `"workbench.fontAliasing": "none"`.
- **Linux:** per font, with `~/.config/fontconfig/fonts.conf`:

  ```xml
  <?xml version="1.0"?>
  <!DOCTYPE fontconfig SYSTEM "fonts.dtd">
  <fontconfig>
    <match target="font">
      <test name="family"><string>PixelFont</string></test>
      <edit name="antialias" mode="assign"><bool>false</bool></edit>
      <edit name="hinting" mode="assign"><bool>false</bool></edit>
    </match>
  </fontconfig>
  ```

  Then run `fc-cache -f` and restart your apps.

### VS Code

Put the font first in *Editor: Font Family*; the rest are fallbacks:

```
'PixelFont', Consolas, 'Courier New', monospace
```

Set *Editor: Font Size* to 16 or 32. The letters have different widths, so code won't line up in perfect columns.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| Wrong letters in the font | `signmap.txt` numbers don't match the images. Check that `svgs/12.svg` looks like `pngs_seperate/12.png`, then rerun `python main.py -svg -font`. |
| Thin white lines inside letters | SVGs from an old version of `png_to_svg.py`. Rerun `python main.py -svg -font`. |
| "Not a valid font file" on Windows | Font built by an old version of `build_font.py`. Rebuild with `python main.py -font`. |
| Letters sit too low or too high | Adjust `--baseline`. |
| Letters too close or too far apart | Change `--hdist` / `--vdist`, then rerun with `-kern -font` using the same values. |
| `No kerning matrix at …` | Run `-kern` with the same `--hdist` / `--vdist` you passed to `-font`. |
| `externally-managed-environment` on pip install | Use the virtual environment from *Requirements*. |
