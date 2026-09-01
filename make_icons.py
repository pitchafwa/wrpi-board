"""Regenerate the board's favicon / home-screen icon set from a single square
source PNG.  Usage:  python make_icons.py path/to/source.png

Writes into dashboard/: favicon.ico, icons/favicon-{16,32,48}.png, favicon.png,
apple-touch-icon.png, icon-{192,512}.png.  Needs Pillow.
"""
import sys
from PIL import Image, ImageDraw

SRC = sys.argv[1] if len(sys.argv) > 1 else "dashboard/icons/icon-master.png"
NAVY = (5, 13, 25)          # sampled from the source interior

src = Image.open(SRC).convert("RGB")
S = src.size[0]

# scale up ~12% and centre-crop so any bevel / rounded-corner cut-outs on the
# source fall outside the frame -> clean full-bleed square for the maskable icons
up = int(S * 1.12)
off = (up - S) // 2
full = src.resize((up, up), Image.LANCZOS).crop((off, off, off + S, off + S))
ImageDraw.Draw(full).rectangle([0, 0, S - 1, S - 1], outline=NAVY, width=3)
full.save("dashboard/icons/icon-master.png")


def rounded(size, rf=0.16):
    im = full.resize((size, size), Image.LANCZOS).convert("RGBA")
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1],
                                        radius=max(1, int(size * rf)), fill=255)
    im.putalpha(m)
    return im


for px in (16, 32, 48):
    rounded(px).save(f"dashboard/icons/favicon-{px}.png")
rounded(48).save("dashboard/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

# iOS / Android: full-bleed, opaque, no rounding (the OS masks it)
full.resize((180, 180), Image.LANCZOS).save("dashboard/icons/apple-touch-icon.png")
for px in (192, 512):
    full.resize((px, px), Image.LANCZOS).save(f"dashboard/icons/icon-{px}.png")

print("wrote dashboard/favicon.ico + dashboard/icons/*")
