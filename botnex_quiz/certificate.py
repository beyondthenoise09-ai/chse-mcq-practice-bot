"""White & golden certificate drawn entirely by code (Pillow) - no template image."""
from __future__ import annotations
import io
import math
import unicodedata
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
W, H = 2000, 1414
GOLD_STOPS = [(0.00, (122, 88, 20)), (0.28, (201, 160, 52)), (0.50, (255, 236, 150)),
              (0.72, (201, 160, 52)), (1.00, (122, 88, 20))]
GOLD = (190, 148, 44)
INK = (52, 44, 32)
GREY = (110, 100, 86)

def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)

def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

DARK_STOPS = [(0.00, (104, 74, 14)), (0.50, (176, 134, 36)), (1.00, (104, 74, 14))]

def gold_gradient(w: int, h: int, vertical: bool = True, dark: bool = False) -> Image.Image:
    stops = DARK_STOPS if dark else GOLD_STOPS
    n = h if vertical else w
    line = Image.new("RGB", (1, n)) if vertical else Image.new("RGB", (n, 1))
    px = line.load()
    for i in range(n):
        t = i / max(1, n - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                col = _lerp(c0, c1, (t - t0) / (t1 - t0))
                break
        px[(0, i) if vertical else (i, 0)] = col
    return line.resize((w, h))

def clean_text(s: str, fallback: str = "") -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = "".join(ch for ch in s if ord(ch) < 0x250 or ch in "•–—’‘“”·")
    s = " ".join(s.split())
    return s or fallback

def spaced_width(d: ImageDraw.ImageDraw, text: str, f, spacing: int) -> int:
    return sum(d.textlength(c, font=f) for c in text) + spacing * (len(text) - 1)

def gold_text(img: Image.Image, xy, text: str, f, anchor: str = "ma", spacing: int = 0, dark: bool = False) -> None:
    """Draw text filled with a gold gradient. anchor: 'ma' centred at x."""
    d = ImageDraw.Draw(img)
    tw = int(spaced_width(d, text, f, spacing))
    asc, desc = f.getmetrics()
    th = asc + desc + 8
    mask = Image.new("L", (tw + 16, th), 0)
    md = ImageDraw.Draw(mask)
    x = 8
    for c in text:
        md.text((x, 4), c, font=f, fill=255)
        x += md.textlength(c, font=f) + spacing
    grad = gold_gradient(mask.width, mask.height, dark=dark)
    px, py = xy
    if anchor == "ma":
        px -= mask.width // 2
    shadow = Image.new("RGBA", mask.size, (120, 90, 20, 0))
    shadow.putalpha(mask.point(lambda v: int(v * 0.25)))
    img.paste(shadow, (int(px) + 2, int(py) + 3), shadow)
    img.paste(grad, (int(px), int(py)), mask)

def plain_text(d, xy, text, f, fill, anchor="ma", spacing=0):
    if spacing:
        tw = spaced_width(d, text, f, spacing)
        x = xy[0] - tw / 2 if anchor == "ma" else xy[0]
        for c in text:
            d.text((x, xy[1]), c, font=f, fill=fill)
            x += d.textlength(c, font=f) + spacing
    else:
        d.text(xy, text, font=f, fill=fill, anchor=anchor + "") if anchor not in ("ma",) else d.text(xy, text, font=f, fill=fill, anchor="ma")

def fit_font(d, text, name, start, max_w, spacing=0, min_size=36):
    size = start
    while size > min_size:
        f = font(name, size)
        if spaced_width(d, text, f, spacing) <= max_w:
            return f
        size -= 4
    return font(name, min_size)

def guilloche(base: Image.Image) -> None:
    """Very light engraved pattern in the background."""
    ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cx, cy = W // 2, H // 2
    for k in range(0, 46):
        r = 260 + k * 24
        d.ellipse((cx - r * 1.55, cy - r, cx + r * 1.55, cy + r), outline=(201, 160, 52, 16), width=2)
    for i in range(0, W + 1, 14):
        d.line([(i, 0), (i, H)], fill=(201, 160, 52, 6), width=1)
    base.alpha_composite(ov)

def corner_ornament(base: Image.Image, x: int, y: int, sx: int, sy: int) -> None:
    """Ornament in a corner; (sx, sy) = direction towards the inside of the page."""
    layer = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, r in enumerate((190, 150, 112, 76)):
        d.arc((-r, -r, r, r), 0, 90, fill=GOLD + (255,), width=6 - i)
    for r in (34, 20, 8):
        d.ellipse((46 - r // 2, 46 - r // 2, 46 + r // 2, 46 + r // 2), outline=GOLD + (255,), width=3)
    for t in range(0, 5):
        ang = math.radians(18 * t + 10)
        px, py = 210 * math.cos(ang), 210 * math.sin(ang)
        d.polygon([(px, py - 9), (px + 9, py), (px, py + 9), (px - 9, py)], fill=GOLD + (255,))
    if sx < 0:
        layer = ImageChops.offset(layer.transpose(Image.FLIP_LEFT_RIGHT), 0, 0)
    if sy < 0:
        layer = layer.transpose(Image.FLIP_TOP_BOTTOM)
    ox = x if sx > 0 else x - 300
    oy = y if sy > 0 else y - 300
    base.alpha_composite(layer, (ox, oy))

def border(base: Image.Image) -> None:
    d = ImageDraw.Draw(base)
    grad = gold_gradient(W, H, vertical=True)
    m = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(m)
    md.rounded_rectangle((34, 34, W - 34, H - 34), 26, outline=255, width=16)
    md.rounded_rectangle((70, 70, W - 70, H - 70), 14, outline=255, width=4)
    md.rounded_rectangle((84, 84, W - 84, H - 84), 8, outline=255, width=2)
    base.paste(grad, (0, 0), m)
    for (x, y, sx, sy) in ((96, 96, 1, 1), (W - 96, 96, -1, 1), (96, H - 96, 1, -1), (W - 96, H - 96, -1, -1)):
        corner_ornament(base, x, y, sx, sy)

def seal(base: Image.Image, cx: int, cy: int, r: int, top: str, big: str, small: str) -> None:
    layer = Image.new("RGBA", (r * 2 + 40, r * 2 + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = r + 20
    pts = []
    for i in range(72):
        ang = math.pi * 2 * i / 72
        rr = r if i % 2 == 0 else r - 16
        pts.append((c + rr * math.cos(ang), c + rr * math.sin(ang)))
    mask = Image.new("L", layer.size, 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    layer.paste(gold_gradient(layer.width, layer.height), (0, 0), mask)
    d.ellipse((c - r + 30, c - r + 30, c + r - 30, c + r - 30), outline=(255, 247, 214, 255), width=4)
    d.ellipse((c - r + 42, c - r + 42, c + r - 42, c + r - 42), outline=(122, 88, 20, 255), width=2)
    f1, f2, f3 = font("Carlito-Bold.ttf", 20), font("Caladea-Bold.ttf", 44), font("Carlito-Bold.ttf", 26)
    d.text((c, c - 40), top, font=f1, fill=(86, 60, 10), anchor="mm")
    d.text((c, c + 2), big, font=f2, fill=(70, 46, 6), anchor="mm")
    d.text((c, c + 42), small, font=f3, fill=(86, 60, 10), anchor="mm")
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(8)).point(lambda v: int(v * 0.30)))
    base.alpha_composite(shadow, (cx - c + 4, cy - c + 8))
    base.alpha_composite(layer, (cx - c, cy - c))

def stat_box(base, x, y, w, h, label, value, tone=None):
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((x, y, x + w, y + h), 18, fill=(255, 252, 244), outline=GOLD, width=3)
    d.rounded_rectangle((x + 8, y + 8, x + w - 8, y + h - 8), 12, outline=(232, 214, 160), width=1)
    d.text((x + w / 2, y + h * 0.40), str(value), font=font("Caladea-Bold.ttf", 66),
           fill=tone or INK, anchor="mm")
    d.text((x + w / 2, y + h * 0.80), label.upper(), font=font("Carlito-Bold.ttf", 26), fill=GREY, anchor="mm")

def wrap(d, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def render_certificate(info: dict) -> bytes:
    img = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    guilloche(img)
    border(img)
    d = ImageDraw.Draw(img)
    cx = W // 2

    # brand mark
    gold_text(img, (cx, 108), "B O T N E X   Q U I Z   A C A D E M Y", font("Carlito-Bold.ttf", 36), spacing=4, dark=True)
    d.line([(cx - 300, 172), (cx - 40, 172)], fill=GOLD, width=3)
    d.line([(cx + 40, 172), (cx + 300, 172)], fill=GOLD, width=3)
    d.polygon([(cx, 160), (cx + 12, 172), (cx, 184), (cx - 12, 172)], fill=GOLD)

    gold_text(img, (cx, 196), "CERTIFICATE", font("Caladea-Bold.ttf", 150), spacing=16)
    plain_text(d, (cx, 392), "O F   A C H I E V E M E N T", font("Carlito-Bold.ttf", 40), GOLD)
    plain_text(d, (cx, 452), "This certificate is proudly presented to", font("Caladea-Italic.ttf", 42), GREY)

    name = clean_text(info.get("name"), clean_text(info.get("username"), "Student"))
    f_name = fit_font(d, name, "Caladea-BoldItalic.ttf", 118, 1350)
    gold_text(img, (cx, 492), name, f_name)
    d.line([(cx - 520, 640), (cx + 520, 640)], fill=GOLD, width=3)
    uname = clean_text(info.get("username"))
    if uname:
        plain_text(d, (cx, 652), "@" + uname, font("Carlito-Regular.ttf", 34), GREY)

    plain_text(d, (cx, 712),
               f"for successfully completing the Class {clean_text(info.get('cls'), '12th')} "
               f"chapter-wise practice examination in", font("Caladea-Italic.ttf", 36), GREY)
    subject = clean_text(info.get("subject"))
    chapter = clean_text(info.get("chapter"))
    plain_text(d, (cx, 768), subject.upper(), font("Carlito-Bold.ttf", 42), GOLD, spacing=8)
    fch = font("Caladea-Bold.ttf", 52)
    lines = wrap(d, chapter, fch, 1500)[:2]
    y = 826
    for ln in lines:
        d.text((cx, y), ln, font=fch, fill=INK, anchor="ma")
        y += 62

    # stats row
    bw, bh, gap = 232, 128, 24
    labels = [("Total", info["total"], None), ("Attempted", info["attempted"], None),
              ("Correct", info["correct"], (28, 120, 62)), ("Incorrect", info["incorrect"], (166, 48, 48)),
              ("Unattempted", info["unattempted"], (110, 100, 86))]
    total_w = bw * 5 + gap * 4
    x0 = cx - total_w // 2
    for i, (lab, val, tone) in enumerate(labels):
        stat_box(img, x0 + i * (bw + gap), 960, bw, bh, lab, val, tone)

    # footer: date | seal | id
    acc = info["accuracy"]
    acc_s = f"{acc:.0f}%" if abs(acc - round(acc)) < 1e-9 else f"{acc:.1f}%"
    seal(img, cx, 1194, 100, "MARKS", f"{info['marks']}/{info['total']}", acc_s)
    d = ImageDraw.Draw(img)
    d.line([(330, 1232), (640, 1232)], fill=GOLD, width=3)
    d.text((485, 1220), clean_text(info.get("date")), font=font("Caladea-Bold.ttf", 36), fill=INK, anchor="ms")
    d.text((485, 1260), "DATE OF EXAMINATION", font=font("Carlito-Bold.ttf", 22), fill=GREY, anchor="mm")
    d.line([(W - 640, 1232), (W - 330, 1232)], fill=GOLD, width=3)
    d.text((W - 485, 1220), clean_text(info.get("cert_id")), font=font("Caladea-Bold.ttf", 36), fill=INK, anchor="ms")
    d.text((W - 485, 1260), "CERTIFICATE ID", font=font("Carlito-Bold.ttf", 22), fill=GREY, anchor="mm")
    gold_text(img, (cx, 1296), "Powered by BOTNEX", font("Carlito-Bold.ttf", 28), spacing=4, dark=True)

    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()
