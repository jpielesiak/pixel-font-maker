"""
build_font.py

Turns the glyph SVGs in svgs/ into a font (.otf + .ttf), using:
  - signmap.txt               which image number is which character
  - matrices/kerning_*.json   how many pixels glyph B can move left after glyph A

Kerning:
  Fonts have no "default kerning" setting, but the same effect can be made by
  changing every glyph's advance width. The most common value in the matrix
  (d) is subtracted from every advance width, and every pair whose value k is
  different from d gets a kerning pair of -(k - d) pixels. Pairs with k == d
  need no entry at all, which keeps the kerning table small.
"""

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.transform import Identity, Transform
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path.parser import parse_path
from fontTools.svgLib.path.shapes import PathBuilder

SVG_DIR = Path("svgs")
PNG_DIR = Path("pngs_seperate")
MATRIX_DIR = Path("matrices")
SIGNMAP = Path("signmap.txt")
OUTPUT_DIR = Path("fonts")

UNITS_PER_EM = 1024
SHAPE_TAGS = {"path", "rect", "polygon", "polyline", "circle", "ellipse", "line"}
SKIP_TAGS = {"defs", "clipPath", "mask", "symbol", "pattern", "marker", "metadata", "title", "desc"}
NO_FILL = {"none", "transparent", "white", "#fff", "#ffffff"}


# --------------------------------------------------------------------------
# signmap.txt
# --------------------------------------------------------------------------
def read_signmap(path=SIGNMAP, quiet=False):
    """Each line: '<number> <character>'. Only the FIRST space is a separator,
    so lines like '12 *', '13 \\', '14 #' and even '15  ' (a space) work."""
    mapping, unfilled = {}, []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.rstrip("\r\n")
            body = line.lstrip()
            if not body.strip():
                continue
            # "12" or "12 " = not filled in yet (note: "12  " = space character)
            if body.isdigit() or (body.endswith(" ") and body[:-1].isdigit()):
                unfilled.append(body.strip())
                continue
            number, sep, sign = body.partition(" ")
            if not sep or not number.isdigit():
                print(f"signmap line {line_no}: can't read {raw!r}, skipped")
                continue
            if len(sign) > 1 and len(sign.strip()) == 1:
                sign = sign.strip()          # tolerate trailing spaces
            if len(sign) != 1:
                print(f"signmap line {line_no}: expected one character, got {sign!r}, skipped")
                continue
            if sign in mapping.values():
                print(f"signmap line {line_no}: {sign!r} is already mapped, skipped")
                continue
            mapping[number] = sign
    if mapping and unfilled and not quiet:
        print(f"signmap: no sign given yet for {len(unfilled)} image(s): {', '.join(unfilled)}")
    return mapping


def signmap_is_filled(path=SIGNMAP):
    """True if signmap.txt exists and at least one line has a sign in it."""
    path = Path(path)
    if not path.exists():
        return False
    try:
        return bool(read_signmap(path, quiet=True))
    except UnicodeDecodeError:
        return True      # has content, let the build report the problem


def create_signmap_template(svg_dir=SVG_DIR, path=SIGNMAP):
    """Write one '<number> ' line per SVG, ready for the user to add the signs."""
    numbers = sorted((p.stem for p in Path(svg_dir).glob("*.svg") if p.stem.isdigit()), key=int)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(f"{n} \n" for n in numbers)
    print(f"Created {path} with {len(numbers)} entries.")
    print("Write the character each image represents after the space on each line,")
    print("then run:  python main.py -font")
    return numbers


def glyph_name(char):
    cp = ord(char)
    return f"uni{cp:04X}" if cp <= 0xFFFF else f"u{cp:05X}"


# --------------------------------------------------------------------------
# SVG reading
# --------------------------------------------------------------------------
def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _length(value):
    """'16', '16px', '16.0pt' -> 16.0 (unit is ignored, only proportions matter)."""
    m = re.match(r"\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", value or "")
    return float(m.group(1)) if m else None


def _parse_transform(text):
    """Supports matrix, translate, scale, rotate, skewX, skewY (combined too)."""
    t = Identity
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", text or ""):
        v = [float(a) for a in re.split(r"[\s,]+", args.strip()) if a]
        if name == "matrix" and len(v) == 6:
            step = Transform(*v)
        elif name == "translate":
            step = Transform().translate(v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            step = Transform().scale(v[0], v[1] if len(v) > 1 else v[0])
        elif name == "rotate":
            import math
            step = Transform()
            if len(v) == 3:
                step = step.translate(v[1], v[2])
            step = step.rotate(math.radians(v[0]))
            if len(v) == 3:
                step = step.translate(-v[1], -v[2])
        elif name == "skewX":
            import math
            step = Transform(1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY":
            import math
            step = Transform(1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            continue
        t = t.transform(step)
    return t


def _fill_of(el, inherited):
    fill = el.get("fill")
    style = el.get("style", "")
    m = re.search(r"fill\s*:\s*([^;]+)", style)
    if m:
        fill = m.group(1)
    return (fill or inherited).strip().lower()


class SvgGlyph:
    def __init__(self, path):
        self.root = ET.parse(path).getroot()
        vb = self.root.get("viewBox")
        if vb:
            self.x, self.y, self.width, self.height = [float(v) for v in re.split(r"[\s,]+", vb.strip())]
        else:
            self.x = self.y = 0.0
            self.width = _length(self.root.get("width"))
            self.height = _length(self.root.get("height"))
        if not self.width or not self.height:
            raise ValueError(f"{path}: no viewBox or width/height")

    def draw(self, pen, base_transform):
        """Draw every filled shape onto pen, applying nested <g> transforms."""
        self._walk(self.root, pen, base_transform, "black")

    def _walk(self, el, pen, transform, fill):
        tag = _local(el.tag)
        if tag in SKIP_TAGS:
            return
        if "transform" in el.attrib:
            transform = transform.transform(_parse_transform(el.get("transform")))
        fill = _fill_of(el, fill)
        if tag in SHAPE_TAGS and fill not in NO_FILL:
            pb = PathBuilder()
            el_copy = ET.Element(tag, {k: v for k, v in el.attrib.items() if k != "transform"})
            pb.add_path_from_element(el_copy)
            for d in pb.paths:
                parse_path(d, TransformPen(pen, transform))
        for child in el:
            self._walk(child, pen, transform, fill)


# --------------------------------------------------------------------------
# Kerning
# --------------------------------------------------------------------------
def load_kerning(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def most_common_value(kerning, numbers):
    counts = Counter(kerning[a][b] for a in numbers for b in numbers
                     if a in kerning and b in kerning[a])
    return counts.most_common(1)[0][0] if counts else 0


# --------------------------------------------------------------------------
# Font building
# --------------------------------------------------------------------------
def _notdef(pen_factory, width, height):
    pen = pen_factory()
    m = width // 10
    for (x0, y0, x1, y1), outer in (((m, 0, width - m, height), True),
                                     ((2 * m, m, width - 2 * m, height - m), False)):
        pts = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)] if outer else \
              [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        pen.moveTo(pts[0]); [pen.lineTo(p) for p in pts[1:]]; pen.closePath()
    return pen


def _build(kind, family, glyphs, advances, cmap, metrics, feature_code, out_path):
    names = list(glyphs)
    fb = FontBuilder(UNITS_PER_EM, isTTF=(kind == "ttf"))
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap(cmap)

    if kind == "ttf":
        outlines = {}
        for name, drawer in glyphs.items():
            pen = TTGlyphPen(None)
            drawer(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
            outlines[name] = pen.glyph()
        fb.setupGlyf(outlines)
    else:
        charstrings = {}
        for name, drawer in glyphs.items():
            pen = T2CharStringPen(advances[name], None)
            drawer(pen)
            charstrings[name] = pen.getCharString()
        fb.setupCFF(re.sub(r"[^A-Za-z0-9-]", "", family) + "-Regular",
                     {"FullName": f"{family} Regular", "FamilyName": family}, charstrings, {})

    lsb = {}
    for name in names:
        bounds = None
        if kind == "ttf":
            g = fb.font["glyf"][name]
            g.recalcBounds(fb.font["glyf"])
            bounds = getattr(g, "xMin", 0)
        else:
            from fontTools.pens.boundsPen import BoundsPen
            bp = BoundsPen(None)
            glyphs[name](bp)
            bounds = bp.bounds[0] if bp.bounds else 0
        lsb[name] = (advances[name], int(round(bounds)))
    fb.setupHorizontalMetrics(lsb)

    ascent, descent = metrics
    fb.setupHorizontalHeader(ascent=ascent, descent=descent)
    ps_name = re.sub(r"[^A-Za-z0-9-]", "", family) or "PixelFont"
    # Windows refuses fonts without full name (4) and PostScript name (6)
    fb.setupNameTable({
        "familyName": family,
        "styleName": "Regular",
        "uniqueFontIdentifier": f"{ps_name}-Regular;1.000",
        "fullName": f"{family} Regular",
        "psName": f"{ps_name}-Regular",
        "version": "Version 1.000",
    })
    fb.setupOS2(version=4, sTypoAscender=ascent, sTypoDescender=descent, sTypoLineGap=0,
                usWinAscent=ascent, usWinDescent=-descent,
                fsType=0,                 # installable, no embedding restrictions
                fsSelection=0x40 | 0x80)  # REGULAR + USE_TYPO_METRICS
    os2 = fb.font["OS/2"]
    os2.recalcUnicodeRanges(fb.font)
    os2.recalcCodePageRanges(fb.font)
    if not (os2.ulCodePageRange1 or os2.ulCodePageRange2):
        os2.ulCodePageRange1 = 1          # at least Latin 1
    fb.setupPost()
    if kind == "ttf":
        # 'gasp' table: ask the renderer for no anti-aliasing (no grayscale,
        # no ClearType smoothing) at every size. Only TrueType honours this.
        from fontTools.ttLib import newTable
        gasp = newTable("gasp")
        gasp.version = 1
        gasp.gaspRange = {0xFFFF: 0}
        fb.font["gasp"] = gasp
        fb.font["head"].flags |= 1 << 3   # round sizes to whole pixels
    if feature_code:
        addOpenTypeFeaturesFromString(fb.font, feature_code)
    fb.save(out_path)
    print(f"Saved {out_path}")


def run_build_font(family="PixelFont", horizontal_dist=1, vertical_dist=1,
                   matrix_path=None, baseline_px=0,
                   svg_dir=SVG_DIR, png_dir=PNG_DIR, signmap=SIGNMAP,
                   output_dir=OUTPUT_DIR):
    """baseline_px = how many pixel rows at the bottom of the 16 px image are
    BELOW the baseline (descender space, e.g. for g, p, y). 0 = image bottom."""
    svg_dir, png_dir, output_dir = Path(svg_dir), Path(png_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    signs = read_signmap(signmap)
    numbers = [n for n in sorted(signs, key=int) if (svg_dir / f"{n}.svg").exists()]
    for n in signs:
        if n not in numbers:
            print(f"{n}.svg not found, {signs[n]!r} will be missing from the font")
    if not numbers:
        print("Nothing to build")
        return

    # Scale: the PNG height (in pixels) becomes 1 em.
    png_height = Image.open(png_dir / f"{numbers[0]}.png").height
    units_per_px = UNITS_PER_EM / png_height
    descent = -int(round(baseline_px * units_per_px))
    ascent = UNITS_PER_EM + descent

    # Kerning
    matrix_path = Path(matrix_path) if matrix_path else \
        MATRIX_DIR / f"kerning_h{horizontal_dist}_v{vertical_dist}.json"
    kerning = load_kerning(matrix_path) if matrix_path.exists() else {}
    if not kerning:
        print(f"No kerning matrix at {matrix_path}, building without kerning")
    default = most_common_value(kerning, numbers)
    default_units = int(round(default * units_per_px))
    print(f"Most common kerning value: {default} px -> taken out of every advance width")

    glyphs, advances, cmap = {}, {}, {}

    glyphs[".notdef"] = lambda pen: _notdef(lambda: pen, UNITS_PER_EM // 2, ascent)
    advances[".notdef"] = UNITS_PER_EM // 2

    for n in numbers:
        char = signs[n]
        name = glyph_name(char)
        svg = SvgGlyph(svg_dir / f"{n}.svg")
        scale = UNITS_PER_EM / svg.height
        # SVG: y grows downwards. Font: y grows upwards, baseline at 0.
        base = Transform(scale, 0, 0, -scale,
                         -svg.x * scale, (svg.y + svg.height) * scale + descent)
        glyphs[name] = (lambda s, b: (lambda pen: s.draw(pen, b)))(svg, base)
        advances[name] = max(0, int(round(svg.width * scale)) - default_units)
        cmap[ord(char)] = name

    # Pairs that differ from the default
    lines = []
    for a in numbers:
        for b in numbers:
            k = kerning.get(a, {}).get(b)
            if k is None or k == default:
                continue
            value = -int(round((k - default) * units_per_px))
            lines.append(f"    pos {glyph_name(signs[a])} {glyph_name(signs[b])} {value};")
    feature_code = ("languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n\n"
                    "feature kern {\n" + "\n".join(lines) + "\n} kern;\n") if lines else ""
    print(f"{len(lines)} kerning pairs differ from the default")

    stem = output_dir / family.replace(" ", "")
    metrics = (ascent, descent)
    _build("otf", family, glyphs, advances, cmap, metrics, feature_code, stem.with_suffix(".otf"))
    _build("ttf", family, glyphs, advances, cmap, metrics, feature_code, stem.with_suffix(".ttf"))