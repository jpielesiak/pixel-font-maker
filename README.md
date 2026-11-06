# Pixel Font Pipeline

Turns a set of small pixel-art letter images into an installable font (`.ttf` and `.otf`), with automatically calculated kerning so letters sit close together without touching.

## Explanation for non-programmers

Open pngs_joined folder.
Paste any number of images, each of the same height in pixels. The width is not an issue. Every letter should be black on a transparent backgroud,
Divide the letters with a single pixel wide vertical line of non-black color.

I used blue for the testing, the pipeline should work with other colors. Blue line will be replaced with transparency in the resulting cut images.
Images turned into .png files are then converted into .svg images.
Font is built from the .svg images.

```bash
python main.py           # generates the font with 1 pixel of free space between the letters' pixels
python main.py -font --hdist 2 --vdist 1 --name "My Pixel Font" --baseline 2 #hdist - min horizontal distance between different letter pixels; vdist - min vertical distance between different letters' pixels; baseline - how tall are all the y g q etc. tails in pixels

```

!!!A signmap.txt will be automatically generated on the first run. Fill the positions
with signs corresponding to them like:
1 A
2 B
3 C
...
to do so look at pngs_seperate folder and see what sign was assinged what number
(the order SHOULD be the order the pngs provided by you were in the pngs_joined, individual signs left to right on each of them)

Then run the programme again with

```bash
python main.py -font          # after filling signmap.txt
```

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

| Path                | What it is                                                                  |
| ------------------- | --------------------------------------------------------------------------- |
| `main.py`           | Runs the pipeline                                                           |
| `separate_pngs.py`  | Step 1: splits the source image into one PNG per letter                     |
| `png_to_svg.py`     | Step 2: turns each letter PNG into an SVG outline                           |
| `kerning_matrix.py` | Step 3: calculates how close every pair of letters can be                   |
| `build_font.py`     | Step 4: builds the font from the SVGs, `signmap.txt` and the kerning matrix |
| `pngs_seperate/`    | One PNG per letter, named `0.png`, `1.png`, …                               |
| `svgs/`             | One SVG per letter, with the same numbers as the PNGs                       |
| `matrices/`         | Kerning matrices (`.csv` and `.json`)                                       |
| `signmap.txt`       | Which character each image number represents (written by you)               |
| `fonts/`            | The finished `.ttf` and `.otf`                                              |

## Running the pipeline

With no flags, every step runs in order. With flags, only the chosen steps run.

| Flag    | Step                                       |
| ------- | ------------------------------------------ |
| `-sep`  | Separate the source image into letter PNGs |
| `-svg`  | Convert PNGs to SVGs                       |
| `-kern` | Calculate the kerning matrix               |
| `-font` | Build the font                             |

Options:

| Option          | Default     | Meaning                                                                                |
| --------------- | ----------- | -------------------------------------------------------------------------------------- |
| `--hdist N`     | `1`         | Minimum empty pixels between two letters side by side                                  |
| `--vdist N`     | `1`         | Minimum empty pixels between two letters above/below each other                        |
| `--name "Name"` | `PixelFont` | Font family name, as it appears in font menus                                          |
| `--baseline N`  | `0`         | Pixel rows at the bottom of each image that hang below the baseline (tails of g, p, y) |

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

**Windows:** right-click `fonts/PixelFont.ttf` and choose _Install for all users_. If Windows shows an old version, uninstall it first or rename the new file.

**macOS:** double-click the `.ttf` and click _Install Font_.

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

Put the font first in _Editor: Font Family_; the rest are fallbacks:

```
'PixelFont', Consolas, 'Courier New', monospace
```

Set _Editor: Font Size_ to 16 or 32. The letters have different widths, so code won't line up in perfect columns.
