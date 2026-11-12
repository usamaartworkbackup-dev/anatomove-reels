#!/usr/bin/env python3
"""Anatomove reel renderer (free: Kokoro TTS + PIL + ffmpeg).

Usage: python3 render_reel.py script.json OUT_DIR TTS_MODEL_DIR [--frames t1,t2,...]

script.json:
{
  "slug": "text-neck",
  "voice": "am_michael", "speed": 1.05,
  "footer": "Sources: Hansraj 2014 · Damasceno 2018",
  "scenes": [
    {"type": "tilt", "tts": "spoken words", "say": "caption words",
     "steps": [[60, "27 kg"]], "sub": "on your neck?", "kicker": "LOOK DOWN"},
    {"type": "big", "tts": "...", "say": "...", "big": "2014", "sub": "...", "kicker": "THE SOURCE"},
    {"type": "cta", "tts": "...", "say": "...", "big": "Looking down?", "options": ["YES", "NO"]}
  ]
}
"""
import json, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
BG = (10, 14, 20)
ORANGE = (255, 92, 31)
CYAN = (34, 211, 238)
WHITE = (245, 247, 250)
GREY = (138, 148, 163)
BODY = (32, 40, 54)
BODY_EDGE = (70, 84, 106)

FONT_DIR = "/usr/share/fonts/opentype/inter"
FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(name, size):
    p = os.path.join(FONT_DIR, name)
    try:
        return ImageFont.truetype(p if os.path.exists(p) else FALLBACK, size)
    except OSError:
        return ImageFont.truetype(FALLBACK, size)


F_BIG = lambda s: font("InterDisplay-Black.otf", s)
F_BOLD = lambda s: font("Inter-Bold.otf", s)
F_SEMI = lambda s: font("Inter-SemiBold.otf", s)
F_XB = lambda s: font("Inter-ExtraBold.otf", s)


def ease_out_back(x):
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def clamp01(x):
    return min(max(x, 0.0), 1.0)


# ---------------------------------------------------------------- background
def make_background():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((x - W * 0.5) / W) ** 2 + ((y - H * 0.36) / H) ** 2)
    glow = np.clip(1.0 - d * 2.2, 0, 1) ** 2
    img = np.zeros((H, W, 3), np.float32)
    for i, c in enumerate(BG):
        img[..., i] = c
    img[..., 0] += glow * 26
    img[..., 1] += glow * 14
    img[..., 2] += glow * 6
    # faint grid
    grid = ((x.astype(int) % 90 == 0) | (y.astype(int) % 90 == 0)).astype(np.float32)
    img += grid[..., None] * 6
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.text((W // 2, 150), "ANATOMOVE", font=F_XB(34), fill=GREY, anchor="mm")
    return im


# ---------------------------------------------------------------- text helpers
def text_pop(img, xy, text, fnt, fill, t, delay=0.0, dur=0.35, stroke=0):
    """Scale-in text by rendering on a layer and resizing."""
    p = ease_out_back((t - delay) / dur) if t > delay else 0.0
    if p <= 0.01:
        return
    bbox = fnt.getbbox(text, stroke_width=stroke)
    tw, th = bbox[2] - bbox[0] + 40, bbox[3] - bbox[1] + 40
    layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((tw // 2, th // 2), text, font=fnt, fill=fill, anchor="mm",
                               stroke_width=stroke, stroke_fill=BG)
    s = max(p, 0.05)
    layer = layer.resize((max(1, int(tw * s)), max(1, int(th * s))), Image.LANCZOS)
    a = clamp01((t - delay) / (dur * 0.6))
    if a < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    img.alpha_composite(layer, (int(xy[0] - layer.width / 2), int(xy[1] - layer.height / 2)))


def text_fade(img, xy, text, fnt, fill, t, delay=0.0, dur=0.3):
    a = clamp01((t - delay) / dur)
    if a <= 0:
        return
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dy = int((1 - ease_io(a)) * 24)
    ImageDraw.Draw(layer).text((xy[0], xy[1] + dy), text, font=fnt,
                               fill=fill + (int(255 * a),), anchor="mm")
    img.alpha_composite(layer)


def wrap(text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if fnt.getlength(test) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- captions
WEAK = {"a", "an", "the", "by", "at", "your", "to", "of", "and", "with", "in", "on", "for", "is",
        "was", "not", "it", "my", "be", "are", "you", "if", "or", "from", "that's", "but", "so", "when"}


def caption_chunks(text, n_words=4):
    words = text.split()
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt_exists = i + 1 < len(words)
        end_punct = w.endswith((".", "?", "!", ","))
        too_long = len(cur) >= n_words
        weak_end = w.lower().strip(".,?!") in WEAK and nxt_exists and len(cur) < n_words + 2
        if end_punct or (too_long and not weak_end):
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def chunk_times(chunks, speech_dur, lead=0.05):
    total = sum(len(c) + 3 for c in chunks)
    t, out = lead, []
    for c in chunks:
        d = speech_dur * (len(c) + 3) / total
        out.append((t, t + d, c))
        t += d
    return out


def draw_caption(img, timed, t):
    cur = None
    for a, b, c in timed:
        if a <= t < b:
            cur = (a, c)
    if cur is None and timed and t >= timed[-1][1]:
        cur = (timed[-1][0], timed[-1][2])
    if cur is None:
        return
    a, c = cur
    fnt = F_XB(64)
    lines = wrap(c.upper(), fnt, 860)
    p = clamp01((t - a) / 0.15)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    y0 = 1330 - (len(lines) - 1) * 40 + int((1 - ease_io(p)) * 18)
    alpha = int(255 * p)
    for i, ln in enumerate(lines):
        y = y0 + i * 80
        tw = fnt.getlength(ln)
        pad = 26
        d.rounded_rectangle((W / 2 - tw / 2 - pad, y - 44, W / 2 + tw / 2 + pad, y + 40),
                            radius=22, fill=(0, 0, 0, int(170 * p)))
        d.text((W / 2, y), ln, font=fnt, fill=WHITE + (alpha,), anchor="mm")
    img.alpha_composite(layer)


# ---------------------------------------------------------------- figure
def draw_figure(img, angle_deg, t):
    """Side-profile person looking at a phone; head pivots at C7 by angle_deg."""
    d = ImageDraw.Draw(img)
    px, py = 470, 900
    # torso / shoulders
    d.rounded_rectangle((300, py - 10, 660, 1180), radius=120, fill=BODY, outline=BODY_EDGE, width=4)
    # spine dots in torso
    for i in range(5):
        yy = py + 30 + i * 46
        d.ellipse((px - 11, yy - 9, px + 11, yy + 9), fill=(60, 74, 96))
    a = math.radians(angle_deg)
    ux, uy = math.sin(a), -math.cos(a)  # direction of neck (forward = +x)
    # cervical vertebrae along neck
    neck_len = 130
    for i in range(7):
        f = (i + 0.5) / 7
        cx, cy = px + ux * neck_len * f, py + uy * neck_len * f
        heat = clamp01(angle_deg / 60)
        col = tuple(int(CYAN[k] * (1 - heat) + ORANGE[k] * heat) for k in range(3))
        r = 13
        d.ellipse((cx - r, cy - r * 0.8, cx + r, cy + r * 0.8), fill=col)
    nx, ny = px + ux * neck_len, py + uy * neck_len
    # head
    hr = 108
    hx, hy = nx + ux * 92, ny + uy * 92
    d.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=BODY, outline=BODY_EDGE, width=4)
    # face direction (perpendicular, forward): eye + nose
    fx, fy = math.cos(a), math.sin(a)
    ex, ey = hx + fx * 62 + ux * 12, hy + fy * 62 + uy * 12
    d.ellipse((ex - 11, ey - 11, ex + 11, ey + 11), fill=WHITE)
    nsx, nsy = hx + fx * hr, hy + fy * hr
    d.polygon([(nsx - ux * 18, nsy - uy * 18), (nsx + fx * 26, nsy + fy * 26), (nsx + ux * 18, nsy + uy * 18)],
              fill=BODY_EDGE)
    # phone
    phx, phy = 760, 1040
    phone = Image.new("RGBA", (90, 160), (0, 0, 0, 0))
    pd = ImageDraw.Draw(phone)
    pd.rounded_rectangle((0, 0, 89, 159), radius=18, fill=(20, 24, 32), outline=WHITE, width=5)
    pd.rounded_rectangle((12, 16, 77, 140), radius=8, fill=CYAN + (120,))
    phone = phone.rotate(35, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(phone, (phx - phone.width // 2, phy - phone.height // 2))
    # gaze line (dashed)
    gx, gy = phx - 20, phy - 30
    steps = 10
    for i in range(0, steps, 2):
        x1 = ex + (gx - ex) * i / steps
        y1 = ey + (gy - ey) * i / steps
        x2 = ex + (gx - ex) * (i + 1) / steps
        y2 = ey + (gy - ey) * (i + 1) / steps
        d.line((x1, y1, x2, y2), fill=CYAN, width=4)
    # angle arc
    if angle_deg > 1:
        R = 210
        d.arc((px - R, py - R, px + R, py + R), start=-90, end=-90 + angle_deg, fill=CYAN, width=6)
        d.line((px, py, px, py - R - 20), fill=GREY, width=3)
        lx = px + math.sin(a / 2) * (R + 60)
        ly = py - math.cos(a / 2) * (R + 60)
        d.text((lx, ly), f"{int(round(angle_deg))}°", font=F_XB(52), fill=CYAN, anchor="mm")


def draw_pool(img, t, dur, mode):
    """Standing body: blood drains to the legs (mode='drain') or calves pump it back up (mode='pump')."""
    cx = W // 2
    head = (cx, 600, 74)
    torso = (cx - 95, 690, cx + 95, 960)
    legL = (cx - 80, 970, cx - 12, 1240)
    legR = (cx + 12, 970, cx + 80, 1240)
    p = ease_io(t / max(dur * 0.75, 0.5))
    if mode == "idle":
        brain, legs = 1.0, 0.25
    elif mode == "drain":
        brain, legs = 1.0 - 0.6 * p, 0.25 + 0.65 * p
    else:
        brain, legs = 0.4 + 0.6 * p, 0.9 - 0.6 * p
    d = ImageDraw.Draw(img)
    # body outlines (filled dark)
    d.ellipse((head[0] - head[2], head[1] - head[2], head[0] + head[2], head[1] + head[2]), fill=BODY, outline=BODY_EDGE, width=4)
    d.rounded_rectangle(torso, radius=70, fill=BODY, outline=BODY_EDGE, width=4)
    for lg in (legL, legR):
        d.rounded_rectangle(lg, radius=34, fill=BODY, outline=BODY_EDGE, width=4)
    # blood fill in legs (from the bottom)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for lg in (legL, legR):
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((lg[0] + 6, lg[1] + 6, lg[2] - 6, lg[3] - 6), radius=28, fill=255)
        top = lg[3] - (lg[3] - lg[1]) * legs
        fill = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(fill).rectangle((lg[0], top, lg[2], lg[3]), fill=ORANGE + (215,))
        layer.paste(fill, (0, 0), Image.composite(fill.getchannel("A"), Image.new("L", img.size, 0), mask))
    # brain glow
    r = int(head[2] * 0.72)
    ld.ellipse((head[0] - r, head[1] - r - 6, head[0] + r, head[1] + r - 6), fill=ORANGE + (int(60 + 170 * brain),))
    img.alpha_composite(layer)
    # particles travelling between torso and legs
    for k in range(16 if mode != "idle" else 0):
        ph = (k * 0.137) % 1
        prog = (t * 0.55 + ph) % 1
        y = 720 + prog * 470 if mode == "drain" else 1190 - prog * 470
        x = cx + ((k * 53) % 120 - 60)
        a = int(255 * math.sin(math.pi * prog))
        d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=ORANGE + (a,))
    # calf squeeze rings in pump mode
    if mode == "pump":
        s = 0.5 + 0.5 * math.sin(t * 7)
        for lg in (legL, legR):
            yy = lg[1] + (lg[3] - lg[1]) * 0.62
            w = 10 + 10 * s
            d.ellipse((lg[0] - w, yy - 22, lg[2] + w, yy + 22), outline=CYAN, width=6)
    # brain meter label
    d.text((head[0] + 150, head[1] - 10), "BRAIN", font=F_BOLD(30), fill=GREY, anchor="lm")
    bx0, bx1 = head[0] + 150, head[0] + 330
    d.rounded_rectangle((bx0, head[1] + 14, bx1, head[1] + 40), radius=13, fill=(24, 30, 40), outline=BODY_EDGE, width=2)
    d.rounded_rectangle((bx0 + 4, head[1] + 18, bx0 + 4 + (bx1 - bx0 - 8) * brain, head[1] + 36), radius=9,
                        fill=CYAN if brain > 0.6 else ORANGE)


def draw_meter(img, frac):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 120, 560, 170, 1120
    d.rounded_rectangle((x0, y0, x1, y1), radius=25, fill=(24, 30, 40), outline=BODY_EDGE, width=3)
    h = (y1 - y0 - 12) * clamp01(frac)
    if h > 4:
        d.rounded_rectangle((x0 + 6, y1 - 6 - h, x1 - 6, y1 - 6), radius=19, fill=ORANGE)
    d.text(((x0 + x1) / 2, y1 + 40), "LOAD", font=F_BOLD(30), fill=GREY, anchor="mm")


# ---------------------------------------------------------------- scenes
def parse_num(label):
    try:
        return float("".join(ch for ch in label if ch.isdigit() or ch == "."))
    except ValueError:
        return 0.0


def render_scene_frame(bg, sc, t, dur, timed, max_num):
    img = bg.copy().convert("RGBA")
    typ = sc["type"]
    if sc.get("kicker"):
        text_fade(img, (W // 2, 250), sc["kicker"], F_XB(40), CYAN, t, 0.0, 0.25)
    if typ == "tilt":
        steps = sc["steps"]
        n = len(steps)
        # step start times: a step may name a cue phrase from "say"; it starts when that caption chunk starts
        starts = []
        for k, st in enumerate(steps):
            cue = st[2] if len(st) > 2 else None
            s0 = None
            if cue:
                for a, b, c in timed:
                    if cue.lower() in c.lower():
                        s0 = a
                        break
            if s0 is None:
                s0 = 0.0 if k == 0 else dur * k / n
            starts.append(s0)
        i = max(k for k in range(n) if starts[k] <= t) if t >= starts[0] else 0
        local = t - starts[i]
        prev_angle = steps[i - 1][0] if i > 0 else 0
        target = steps[i][0]
        e = ease_io(local / 0.6)
        ang = prev_angle + (target - prev_angle) * e
        prev_frac = parse_num(steps[i - 1][1]) / max_num if i > 0 else 0
        draw_meter(img, prev_frac + (parse_num(steps[i][1]) / max_num - prev_frac) * e)
        draw_figure(img, ang, t)
        text_pop(img, (W // 2 + 60, 400), steps[i][1].upper(), F_BIG(170), ORANGE, local, 0.05, 0.35, stroke=6)
        if sc.get("sub"):
            text_fade(img, (W // 2 + 60, 525), sc["sub"], F_SEMI(48), WHITE, t, 0.25)
    elif typ == "pool":
        draw_pool(img, t, dur, sc.get("mode", "drain"))
        if sc.get("label"):
            text_pop(img, (W // 2, 360), sc["label"].upper(), F_BIG(sc.get("size", 130)), ORANGE, t, 0.1, 0.35, stroke=6)
        if sc.get("sub"):
            text_fade(img, (W // 2, 465), sc["sub"], F_SEMI(46), WHITE, t, 0.3)
    elif typ == "big":
        fnt = F_BIG(sc.get("size", 200))
        lines = wrap(sc["big"].upper(), fnt, 920)
        for k, ln in enumerate(lines):
            text_pop(img, (W // 2, 640 + k * (fnt.size * 1.02) - (len(lines) - 1) * fnt.size * 0.5), ln,
                     fnt, ORANGE if k == 0 else WHITE, t, 0.05 + 0.12 * k, 0.38, stroke=6)
        if sc.get("sub"):
            for k, ln in enumerate(wrap(sc["sub"], F_SEMI(54), 900)):
                text_fade(img, (W // 2, 900 + k * 70), ln, F_SEMI(54), WHITE, t, 0.35 + 0.1 * k)
    elif typ == "cta":
        text_pop(img, (W // 2, 560), sc["big"], F_BIG(110), WHITE, t, 0.05, 0.38, stroke=4)
        opts = sc.get("options", ["YES", "NO"])
        d = ImageDraw.Draw(img)
        for k, o in enumerate(opts):
            p = ease_out_back((t - 0.35 - 0.15 * k) / 0.35) if t > 0.35 + 0.15 * k else 0
            if p <= 0:
                continue
            three = len(opts) >= 3
            gap, bw, fs = (320, 300, 50) if three else (400, 330, 80)
            cx = W / 2 + (k - (len(opts) - 1) / 2) * gap
            wbox, hbox = bw * p, 170 * p
            col = (ORANGE, CYAN, WHITE)[k % 3]
            d.rounded_rectangle((cx - wbox / 2, 820 - hbox / 2, cx + wbox / 2, 820 + hbox / 2),
                                radius=int(40 * p), fill=col)
            if p > 0.6:
                f_o = F_BIG(fs)
                while f_o.getlength(o) > bw - 40 and fs > 24:
                    fs -= 2
                    f_o = F_BIG(fs)
                d.text((cx, 820), o, font=f_o, fill=BG, anchor="mm")
        if sc.get("sub"):
            for k2, ln in enumerate(wrap(sc["sub"], F_SEMI(46), 860)):
                text_fade(img, (W // 2, 1000 + k2 * 60), ln, F_SEMI(46), GREY, t, 0.6)
    draw_caption(img, timed, t)
    return img


# ---------------------------------------------------------------- audio
def tts_all(script, tts_dir, work):
    from kokoro_onnx import Kokoro
    import soundfile as sf
    k = Kokoro(os.path.join(tts_dir, "kokoro-v1.0.onnx"), os.path.join(tts_dir, "voices-v1.0.bin"))
    durs, parts, sr = [], [], 24000
    for i, sc in enumerate(script["scenes"]):
        samples, sr = k.create(sc.get("tts", sc["say"]), voice=script.get("voice", "am_michael"),
                               speed=script.get("speed", 1.05), lang="en-us")
        speech = len(samples) / sr
        pad = sc.get("pad", 0.35)
        parts.append(np.concatenate([samples, np.zeros(int(pad * sr), np.float32)]))
        durs.append((speech, speech + pad))
    audio = np.concatenate(parts)
    peak = np.max(np.abs(audio)) or 1
    audio = audio / peak * 0.89
    sf.write(os.path.join(work, "voice.wav"), audio, sr)
    return durs


def scene_lengths(durs):
    """Snap each scene to whole frames, carrying rounding so video == audio length."""
    out, acc_t, acc_f = [], 0.0, 0
    for speech, total in durs:
        acc_t += total
        frames = int(round(acc_t * FPS)) - acc_f
        acc_f += frames
        out.append((speech, frames))
    return out


def encode_scene(bg, sc, frames, speech, max_num, path):
    timed = chunk_times(caption_chunks(sc["say"]), speech)
    dur = frames / FPS
    tmp = path[:-4] + ".part.mp4"
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS), tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(frames):
        t = f / FPS
        im = render_scene_frame(bg, sc, t, dur, timed, max_num)
        # progress bar handled by caller via sc['_t0'], sc['_total']
        d = ImageDraw.Draw(im)
        prog = (sc["_t0"] + t) / sc["_total"]
        d.rectangle((0, 0, int(W * prog), 10), fill=ORANGE)
        p.stdin.write(im.convert("RGB").tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise SystemExit("ffmpeg failed on " + path)
    os.replace(tmp, path)


def main():
    script_path, out_dir, tts_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    frames_only = None
    if "--frames" in sys.argv:
        frames_only = [float(x) for x in sys.argv[sys.argv.index("--frames") + 1].split(",")]
    script = json.load(open(script_path))
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, "work")
    os.makedirs(work, exist_ok=True)
    bg = make_background()
    if script.get("footer"):
        ImageDraw.Draw(bg).text((W // 2, 1450), script["footer"], font=F_SEMI(28), fill=GREY, anchor="mm")
    max_num = max([parse_num(s[1]) for sc in script["scenes"] if sc["type"] == "tilt" for s in sc["steps"]] or [1])
    durs = tts_all(script, tts_dir, work)
    lens = scene_lengths(durs)
    total = sum(f for _, f in lens) / FPS
    t0 = 0.0
    for sc, (speech, frames) in zip(script["scenes"], lens):
        sc["_t0"], sc["_total"], sc["_frames"], sc["_speech"] = t0, total, frames, speech
        t0 += frames / FPS
    if frames_only is not None:
        for gt in frames_only:
            for i, sc in enumerate(script["scenes"]):
                if sc["_t0"] <= gt < sc["_t0"] + sc["_frames"] / FPS:
                    t = gt - sc["_t0"]
                    timed = chunk_times(caption_chunks(sc["say"]), sc["_speech"])
                    im = render_scene_frame(bg, sc, t, sc["_frames"] / FPS, timed, max_num)
                    im.convert("RGB").save(os.path.join(out_dir, f"frame_{gt:05.2f}.jpg"), quality=90)
        print("frames saved; total", round(total, 2))
        return
    files = []
    for i, sc in enumerate(script["scenes"]):
        path = os.path.join(work, f"scene_{i:02d}.mp4")
        encode_scene(bg, sc, sc["_frames"], sc["_speech"], max_num, path)
        files.append(path)
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as fh:
        for f in files:
            fh.write(f"file '{os.path.abspath(f)}'\n")
    silent = os.path.join(work, "video.mp4")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", silent], check=True)
    final = os.path.join(out_dir, f"Anatomove - {script['title']}.mp4")
    tmp = final[:-4] + ".part.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", silent, "-i", os.path.join(work, "voice.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, final)
    print("done", final, round(total, 2), "s")


if __name__ == "__main__":
    main()
