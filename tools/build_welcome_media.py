"""Builds assets/welcome.mp4 (looping golden shine) and assets/welcome.jpg from assets/welcome_source.jpg.
Usage:  python tools/build_welcome_media.py [source.jpg]
Needs: Pillow, numpy and ffmpeg on PATH (only to rebuild; the finished files are already in assets/)."""
from __future__ import annotations
import subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "assets"
W, H = 720, 960
GOLD = [(122, 88, 20), (212, 175, 55), (255, 236, 150), (212, 175, 55), (122, 88, 20)]

def gradient(w, h):
    img = Image.new("RGB", (w, h)); px = img.load()
    for y in range(h):
        t = y / max(1, h - 1) * (len(GOLD) - 1); i = min(int(t), len(GOLD) - 2); f = t - i
        c = tuple(int(GOLD[i][k] + (GOLD[i + 1][k] - GOLD[i][k]) * f) for k in range(3))
        for x in range(w): px[x, y] = c
    return img

def base_frame(src: Path) -> Image.Image:
    im = Image.open(src).convert("RGB")
    im = ImageOps.fit(im, (W, H), Image.LANCZOS, centering=(0.5, 0.45))
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2))
    # soft dark gradient at the bottom for the ribbon text
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for i in range(260):
        d.line([(0, H - i), (W, H - i)], fill=(10, 8, 4, int(190 * (1 - i / 260) ** 1.6)))
    im = Image.alpha_composite(im.convert("RGBA"), ov)
    d = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(str(A / "fonts" / "Caladea-Bold.ttf"), 54)
    f2 = ImageFont.truetype(str(A / "fonts" / "Carlito-Bold.ttf"), 27)
    g = gradient(W, 70); m = Image.new("L", (W, 70), 0)
    ImageDraw.Draw(m).text((W // 2, 35), "B O T N E X", font=f1, fill=255, anchor="mm")
    im.paste(g, (0, H - 170), m)
    d.text((W // 2, H - 92), "QUIZ ACADEMY  •  CLASS 12", font=f2, fill=(255, 240, 190), anchor="mm")
    d.line([(W // 2 - 150, H - 62), (W // 2 + 150, H - 62)], fill=(212, 175, 55), width=2)
    # golden frame
    fm = Image.new("L", (W, H), 0); fd = ImageDraw.Draw(fm)
    fd.rounded_rectangle((6, 6, W - 7, H - 7), 22, outline=255, width=14)
    fd.rounded_rectangle((30, 30, W - 31, H - 31), 12, outline=255, width=2)
    im.paste(gradient(W, H), (0, 0), fm)
    return im.convert("RGB")

def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else A / "welcome_source.jpg"
    base = base_frame(src)
    base.save(A / "welcome.jpg", quality=92)
    arr = np.asarray(base).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    diag = xx + yy * 0.55
    total, sweep_start, sweep_end = 72, 10, 44
    span = W + H * 0.55 + 400
    with tempfile.TemporaryDirectory() as td:
        for f in range(total):
            if sweep_start <= f <= sweep_end:
                pos = -200 + span * (f - sweep_start) / (sweep_end - sweep_start)
                band = np.exp(-((diag - pos) / 70.0) ** 2) * 0.55 + np.exp(-((diag - pos + 120) / 26.0) ** 2) * 0.25
                out = arr + band[..., None] * (255 - arr) * 0.9 + band[..., None] * np.array([40, 34, 8])
            else:
                out = arr
            Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(Path(td) / f"f{f:03d}.jpg", quality=92)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i", str(Path(td) / "f%03d.jpg"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", "-preset", "medium",
                        "-movflags", "+faststart", "-an", str(A / "welcome.mp4")], check=True)
    print("built", A / "welcome.mp4", (A / "welcome.mp4").stat().st_size // 1024, "KB")

if __name__ == "__main__":
    main()
