#!/usr/bin/env python3
"""Anatomove carousel renderer (free: PIL). 1080x1350 slides in the brand style.

Usage: python3 render_carousel.py carousel.json OUT_DIR

carousel.json:
{
  "title": "5 body myths we busted",
  "slides": [
    {"kind": "cover", "kicker": "SAVE THIS", "title": "5 body myths we busted", "sub": "swipe →"},
    {"kind": "point", "num": "1", "title": "Cracking knuckles causes arthritis", "verdict": "MYTH",
     "body": "A doctor cracked one hand for 60 years. No arthritis in either.", "source": "Unger 1998"},
    {"kind": "end", "title": "Which one surprised you?", "sub": "Follow @anatomove.physio for more"}
  ]
}
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
BG = (10, 14, 20)
ORANGE = (255, 92, 31)
CYAN = (34, 211, 238)
WHITE = (245, 247, 250)
GREY = (138, 148, 163)
CARD = (22, 28, 38)
FD = "/usr/share/fonts/opentype/inter"
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def F(name, size):
    p = os.path.join(FD, name)
    return ImageFont.truetype(p if os.path.exists(p) else FB, size)


def wrap(text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if fnt.getlength(t) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def block(d, y, text, fnt, fill, max_w=900, gap=1.15, x=W // 2, anchor="ma"):
    for ln in wrap(text, fnt, max_w):
        d.text((x, y), ln, font=fnt, fill=fill, anchor=anchor)
        y += int(fnt.size * gap)
    return y


def base(i, n):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((W // 2, 70), "ANATOMOVE", font=F("Inter-ExtraBold.otf", 30), fill=GREY, anchor="mm")
    # progress dots
    for k in range(n):
        x = W // 2 + (k - (n - 1) / 2) * 30
        d.ellipse((x - 7, H - 77, x + 7, H - 63), fill=ORANGE if k == i else (50, 58, 72))
    return im, d


def render(spec, out):
    os.makedirs(out, exist_ok=True)
    slides = spec["slides"]
    n = len(slides)
    paths = []
    for i, s in enumerate(slides):
        im, d = base(i, n)
        k = s.get("kind", "point")
        if k == "cover":
            if s.get("kicker"):
                d.text((W // 2, 330), s["kicker"], font=F("Inter-ExtraBold.otf", 40), fill=CYAN, anchor="mm")
            y = block(d, 420, s["title"].upper(), F("InterDisplay-Black.otf", 110), ORANGE, 920, 1.02)
            if s.get("sub"):
                block(d, y + 40, s["sub"], F("Inter-SemiBold.otf", 46), WHITE)
        elif k == "point":
            d.rounded_rectangle((70, 170, W - 70, H - 140), radius=48, fill=CARD)
            if s.get("num"):
                d.text((140, 250), s["num"], font=F("InterDisplay-Black.otf", 140), fill=ORANGE, anchor="lm")
            if s.get("verdict"):
                v = s["verdict"].upper()
                col = ORANGE if v in ("MYTH", "FALSE") else CYAN
                fv = F("InterDisplay-Black.otf", 54)
                tw = fv.getlength(v)
                d.rounded_rectangle((W - 140 - tw - 50, 210, W - 140, 290), radius=40, fill=col)
                d.text((W - 140 - (tw + 50) / 2, 250), v, font=fv, fill=BG, anchor="mm")
            y = block(d, 360, s["title"], F("InterDisplay-Black.otf", 72), WHITE, 860, 1.08, x=140, anchor="la")
            y = block(d, y + 40, s.get("body", ""), F("Inter-Medium.otf", 44), (210, 216, 226), 820, 1.35, x=140, anchor="la")
            if s.get("source"):
                d.text((140, H - 200), "Source: " + s["source"], font=F("Inter-SemiBold.otf", 30), fill=GREY, anchor="la")
        elif k == "end":
            y = block(d, 470, s["title"], F("InterDisplay-Black.otf", 96), WHITE, 900, 1.05)
            if s.get("sub"):
                block(d, y + 50, s["sub"], F("Inter-SemiBold.otf", 46), CYAN)
            d.text((W // 2, H - 180), "Educational content, not medical advice.", font=F("Inter-SemiBold.otf", 28),
                   fill=GREY, anchor="mm")
        p = os.path.join(out, f"slide_{i + 1:02d}.jpg")
        im.save(p, quality=92)
        paths.append(p)
    print("\n".join(paths))


if __name__ == "__main__":
    render(json.load(open(sys.argv[1])), sys.argv[2])
