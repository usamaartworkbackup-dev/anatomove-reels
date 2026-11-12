#!/usr/bin/env python3
"""Anatomove story card renderer (free: PIL). 1080x1920, leaves room for an Instagram sticker.

Usage: python3 render_story.py story.json OUT.jpg
story.json: {"kicker": "QUICK QUIZ", "title": "Which nerve gives you a dead arm?", "sub": "answer with the sticker below 👇",
             "sticker_space": true}
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BG = (10, 14, 20)
ORANGE = (255, 92, 31)
CYAN = (34, 211, 238)
WHITE = (245, 247, 250)
GREY = (138, 148, 163)
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


def render(spec, out):
    import re
    strip = lambda t: re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE0F]", "", t).strip()
    spec = {k: strip(v) if isinstance(v, str) else v for k, v in spec.items()}
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((W // 2, 260), "ANATOMOVE", font=F("Inter-ExtraBold.otf", 34), fill=GREY, anchor="mm")
    if spec.get("kicker"):
        d.text((W // 2, 420), spec["kicker"].upper(), font=F("Inter-ExtraBold.otf", 46), fill=CYAN, anchor="mm")
    ft = F("InterDisplay-Black.otf", 96)
    y = 500
    for ln in wrap(spec["title"], ft, 900):
        d.text((W // 2, y), ln, font=ft, fill=ORANGE, anchor="ma")
        y += 104
    if spec.get("sub"):
        fs = F("Inter-SemiBold.otf", 50)
        y += 30
        for ln in wrap(spec["sub"], fs, 880):
            d.text((W // 2, y), ln, font=fs, fill=WHITE, anchor="ma")
            y += 64
    # leave y 1150-1500 empty for the Instagram sticker; emojis are not drawn (font has none)
    im.save(out, quality=92)
    print(out)


if __name__ == "__main__":
    render(json.load(open(sys.argv[1])), sys.argv[2])
