"""Find the floating bits (sparkles, sleepy z's) in the pet sprites.

The pet art has its sparkles and z's drawn in as small islands of pixels apart
from the body. PetSprite clips each island out of the sprite and moves it on
its own (z's float up, sparkles twinkle), so this writes their boxes to
frontend/src/views/pet/petParticles.ts. Re-run it after changing the art:

    python scripts/pet_particles.py
"""

import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PETS = os.path.join(ROOT, "frontend", "src", "assets", "pets")
OUT = os.path.join(ROOT, "frontend", "src", "views", "pet", "petParticles.ts")

ALPHA = 40          # at or above: part of the art
MAX_AREA = 100      # bigger islands (the body, a dropped staff) stay put
GAP = 1             # islands this close move as one (the strokes of a z)
DARK = 90           # mean luminance below: a z, else a sparkle


def islands(im):
    """8-connected groups of opaque pixels, biggest first."""
    w, h = im.size
    px = im.load()
    seen = set()
    found = []
    for x in range(w):
        for y in range(h):
            if (x, y) in seen or px[x, y][3] < ALPHA:
                continue
            seen.add((x, y))
            stack, pts = [(x, y)], []
            while stack:
                a, b = stack.pop()
                pts.append((a, b))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        c, d = a + dx, b + dy
                        if 0 <= c < w and 0 <= d < h and (c, d) not in seen and px[c, d][3] >= ALPHA:
                            seen.add((c, d))
                            stack.append((c, d))
            found.append(pts)
    found.sort(key=len, reverse=True)
    return found


def box(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def near(a, b):
    return a[0] - GAP <= b[2] and b[0] - GAP <= a[2] and a[1] - GAP <= b[3] and b[1] - GAP <= a[3]


def kind_of(im, pts):
    px = im.load()
    lum = sum(0.299 * px[p][0] + 0.587 * px[p][1] + 0.114 * px[p][2] for p in pts) / len(pts)
    return "z" if lum < DARK else "spark"


def particles(im):
    """(kind, group, box) per floating bit. Bits in a group move as one: the
    strokes of one z, or sparkles drawn a pixel apart."""
    found = []  # [kind, group, box, pts]
    for pts in islands(im)[1:]:
        if len(pts) > MAX_AREA:
            continue
        found.append([kind_of(im, pts), len(found), box(pts), pts])
    # Join close islands of a kind; one may touch two others that don't touch
    # each other, so keep merging until nothing changes.
    merged = True
    while merged:
        merged = False
        for a in found:
            for b in found:
                if a[0] == b[0] and a[1] != b[1] and near(a[2], b[2]):
                    old, new = max(a[1], b[1]), min(a[1], b[1])
                    for f in found:
                        if f[1] == old:
                            f[1] = new
                    merged = True
    # Boxes reach one clear pixel past the art: the clip edges fall between
    # device pixels at most sizes and blend what they cross, so they must only
    # cross empty ones. A glyph gets one box when that holds nothing else.
    w, h = im.size
    px = im.load()

    def pad(b):
        return max(b[0] - 1, 0), max(b[1] - 1, 0), min(b[2] + 1, w), min(b[3] + 1, h)

    def clean(b, own):
        return all(px[x, y][3] < ALPHA or (x, y) in own for x in range(b[0], b[2]) for y in range(b[1], b[3]))

    def disjoint(boxes):
        return not any(
            a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
            for i, a in enumerate(boxes)
            for b in boxes[i + 1:]
        )

    # PetSprite cuts the boxes out of the body with an even-odd fill, where two
    # overlapping holes would cancel out, so boxes must not overlap either. A
    # sparkle that can't be boxed that way stays put as part of the body.
    out = []  # [kind, group, box]
    for g in sorted({f[1] for f in found}):
        members = [f for f in found if f[1] == g]
        kind = members[0][0]
        own = {p for f in members for p in f[3]}
        union = pad(tuple(fn(f[2][i] for f in members) for i, fn in enumerate((min, min, max, max))))
        boxes = [union] if clean(union, own) else [pad(f[2]) for f in members]
        if not (all(clean(b, own) for b in boxes) and disjoint(boxes)):
            if kind == "z":
                sys.exit(f"z at {union[0]},{union[1]} is too close to other art to cut out")
            continue
        out.extend([kind, g, b] for b in boxes)
    if not disjoint([b for _, _, b in out]):
        sys.exit("bits from different groups overlap")
    # Number groups top to bottom, then left to right, so the output is stable.
    order = {}
    for _, group, _ in sorted(out, key=lambda f: (f[2][1], f[2][0])):
        order.setdefault(group, len(order))
    return sorted(((k, order[g], b) for k, g, b in out), key=lambda f: (f[1], f[2][1], f[2][0]))


def render():
    """The petParticles.ts text for the art as it is now."""
    lines = [
        "// Generated by scripts/pet_particles.py from src/assets/pets/*.webp; don't edit by hand.",
        "// Boxes in sprite pixels of the floating bits PetSprite animates on their own.",
        "",
        "export interface PetParticle {",
        "  kind: 'z' | 'spark';",
        "  /** Islands in the same group move together (the strokes of one z). */",
        "  group: number;",
        "  x: number;",
        "  y: number;",
        "  w: number;",
        "  h: number;",
        "}",
        "",
        "export const PET_PARTICLES: Record<string, PetParticle[]> = {",
    ]
    for name in sorted(os.listdir(PETS)):
        if not name.endswith(".webp"):
            continue
        im = Image.open(os.path.join(PETS, name)).convert("RGBA")
        lines.append(f"  {name[:-5]}: [")
        for kind, group, (x0, y0, x1, y1) in particles(im):
            lines.append(f"    {{ kind: '{kind}', group: {group}, x: {x0}, y: {y0}, w: {x1 - x0}, h: {y1 - y0} }},")
        lines.append("  ],")
    lines.append("};")
    return "\n".join(lines) + "\n"


def main():
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(render())
    print(f"wrote {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
