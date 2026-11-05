"""Cut the pet skin sprites out of their source pictures.

The pet art comes as 2048 px pictures of 90×90 pixel art on white, each art
pixel drawn as a 2×2 block of a 180-cell grid. This samples the middle of each
cell, keys out the white background (flood-filled from the border, so white
inside the art stays), crops the pet's box and saves a lossless WebP to
frontend/src/assets/pets/<kind>_<pose>_<skin>.webp. Re-run it after changing
the art, then re-run scripts/pet_particles.py:

    python -I scripts/pet_sprites.py <folder with the source pictures>

The box is the same for every sprite of a kind (SPRITE_SIZE in petState.ts),
so the pet doesn't jump when its pose changes. Art that reaches past it grows
the box by whole art pixels; petSkins.ts lists those sprites (SKIN_ART) so
PetSprite can draw them overhanging.
"""

import os
import sys
from collections import deque

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PETS = os.path.join(ROOT, "frontend", "src", "assets", "pets")

N = 180          # grid cells across the picture (two per art pixel)
WHITE = 235      # every channel at or above: background
# Each kind's box in the grid: x, y, w, h. x and y are odd, so the art's
# pixels start on odd sprite rows and columns, as petSpriteLayers.ts expects.
BOX = {"familiar": (17, 29, 142, 122), "wizard": (9, 23, 162, 140)}

SOURCES = {
    "wizard_idle_bazooka": "Gemini_Generated_Image_2ty1hx2ty1hx2ty1.jpg",
    "familiar_idle_bazooka": "Gemini_Generated_Image_jypq51jypq51jypq.jpg",
    "wizard_sleep_gilded": "Gemini_Generated_Image_flzuoaflzuoaflzu.jpg",
    "familiar_idle_neon": "Gemini_Generated_Image_flzuoaflzuoaflzu (1).jpg",
    "wizard_idle_neon": "Gemini_Generated_Image_flzuoaflzuoaflzu (2).jpg",
    "familiar_fly_cosmic": "Gemini_Generated_Image_flzuoaflzuoaflzu (3).jpg",
    "wizard_drowsy_cosmic": "Gemini_Generated_Image_flzuoaflzuoaflzu (4).jpg",
    "familiar_sleep_gilded": "Gemini_Generated_Image_flzuoaflzuoaflzu (5).jpg",
    "wizard_idle_gilded": "Gemini_Generated_Image_j57cvcj57cvcj57c.jpg",
    "wizard_drowsy_gilded": "Gemini_Generated_Image_j57cvcj57cvcj57c (1).jpg",
    "wizard_idle_legend": "Gemini_Generated_Image_xgytc1xgytc1xgyt.jpg",
    "familiar_sleep_legend": "Gemini_Generated_Image_dissxzdissxzdiss.jpg",
}


def cells(path):
    """The grid's colours: the median of the middle 40% of each cell, clear of
    the blur where neighbouring cells meet."""
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.int32)
    c = im.shape[1] / N
    out = np.zeros((N, N, 3), np.int32)
    for j in range(N):
        for i in range(N):
            x0, x1 = int((i + 0.3) * c), int((i + 0.7) * c) + 1
            y0, y1 = int((j + 0.3) * c), int((j + 0.7) * c) + 1
            out[j, i] = np.median(im[y0:y1, x0:x1].reshape(-1, 3), axis=0)
    return out


def key(rgb):
    """RGBA with the white reachable from the border made transparent."""
    h, w, _ = rgb.shape
    white = rgb.min(axis=2) >= WHITE
    bg = np.zeros((h, w), bool)
    q = deque((y, x) for y in range(h) for x in range(w) if (y in (0, h - 1) or x in (0, w - 1)) and white[y, x])
    for y, x in q:
        bg[y, x] = True
    while q:
        y, x = q.popleft()
        for a, b in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= a < h and 0 <= b < w and white[a, b] and not bg[a, b]:
                bg[a, b] = True
                q.append((a, b))
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = rgb.clip(0, 255)
    rgba[..., 3] = np.where(bg, 0, 255)
    return rgba


def crop_box(alpha, kind):
    """The kind's box, grown by whole art pixels (2 cells) to take in any art
    past it: (x, y, w, h) in the grid."""
    x, y, w, h = BOX[kind]
    ys, xs = np.nonzero(alpha)
    grow = lambda n: max(0, n + n % 2)  # noqa: E731
    left = grow(x - xs.min())
    right = grow(xs.max() + 1 - (x + w))
    top = grow(y - ys.min())
    bottom = grow(ys.max() + 1 - (y + h))
    return x - left, y - top, w + left + right, h + top + bottom


def main(src):
    for name, file in SOURCES.items():
        rgba = key(cells(os.path.join(src, file)))
        x, y, w, h = crop_box(rgba[..., 3], name.split("_")[0])
        out = Image.fromarray(rgba[y : y + h, x : x + w], "RGBA")
        out.save(os.path.join(PETS, f"{name}.webp"), lossless=True, exact=False)
        bx, by, bw, bh = BOX[name.split("_")[0]]
        note = "" if (x, y, w, h) == (bx, by, bw, bh) else f"  overhangs: dx {x - bx}, dy {y - by}, {w}x{h}"
        print(f"{name}: {file}{note}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -I scripts/pet_sprites.py <folder with the source pictures>")
    main(sys.argv[1])
