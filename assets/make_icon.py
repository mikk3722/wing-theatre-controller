"""Draws the Wing Theatre Controller app icon (design "C": white W on a green
plate, green T badge below) and writes icon.png / icon.icns / icon.ico next
to this script.  Run:  python3 assets/make_icon.py   (needs Pillow + Inter font)
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import sys, os
OUT = os.path.dirname(os.path.abspath(__file__))
SS = 4                      # supersampling
N = 1024 * SS
BOLD = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"
XB   = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
GREEN = (82, 183, 136); GREEN_D = (45, 106, 79); BG1 = (30, 32, 34); BG2 = (14, 15, 16)

def tile():
    """macOS-style tile: 824px rounded square centred on 1024 (Apple grid)."""
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    m = int(100 * SS); r = int(185 * SS)
    # soft shadow
    sh = Image.new("RGBA", (N, N), (0, 0, 0, 0)); d = ImageDraw.Draw(sh)
    d.rounded_rectangle([m, m + 12*SS, N - m, N - m + 12*SS], r, fill=(0, 0, 0, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(18 * SS)); im.alpha_composite(sh)
    # vertical gradient body
    body = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    grad = Image.new("RGBA", (1, N))
    for y in range(N):
        t = y / N
        grad.putpixel((0, y), tuple(int(BG1[i] * (1 - t) + BG2[i] * t) for i in range(3)) + (255,))
    grad = grad.resize((N, N))
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).rounded_rectangle([m, m, N - m, N - m], r, fill=255)
    body.paste(grad, (0, 0), mask); im.alpha_composite(body)
    # thin top highlight edge
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([m, m, N - m, N - m], r, outline=(255, 255, 255, 28), width=3 * SS)
    return im, m

def t_badge(im, cx, cy, w, h, fill, txt_fill):
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([cx - w//2, cy - h//2, cx + w//2, cy + h//2], int(h * 0.22), fill=fill)
    f = ImageFont.truetype(XB, int(h * 0.78))
    bb = d.textbbox((0, 0), "T", font=f)
    d.text((cx - (bb[0] + bb[2]) / 2, cy - (bb[1] + bb[3]) / 2), "T", font=f, fill=txt_fill)

def faders_w(im, cx, top, bottom, width, color):
    """Five fader slots; the caps trace a W (high-low-high-low-high)."""
    d = ImageDraw.Draw(im)
    n = 5; gap = width / (n - 1)
    caps = [0.12, 0.88, 0.40, 0.88, 0.12]          # 0 = top, 1 = bottom
    pts = []
    for i in range(n):
        x = cx - width / 2 + i * gap
        d.rounded_rectangle([x - 7*SS, top, x + 7*SS, bottom], 7*SS, fill=(60, 64, 68, 255))
        y = top + caps[i] * (bottom - top)
        pts.append((x, y))
    d.line(pts, fill=color, width=26*SS, joint="curve")
    for x, y in pts:
        d.rounded_rectangle([x - 46*SS, y - 26*SS, x + 46*SS, y + 26*SS], 10*SS, fill=(235, 238, 240, 255))
        d.rectangle([x - 46*SS, y - 3*SS, x + 46*SS, y + 3*SS], fill=color)

def letter_w(im, cx, cy, size, color):
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(BOLD, size)
    bb = d.textbbox((0, 0), "W", font=f)
    d.text((cx - (bb[0] + bb[2]) / 2, cy - (bb[1] + bb[3]) / 2), "W", font=f, fill=color)

def concept(kind):
    im, m = tile()
    c = N // 2
    if kind == "A":     # fader W + green T badge
        faders_w(im, c, m + 120*SS, c + 150*SS, 520*SS, GREEN)
        t_badge(im, c, N - m - 150*SS, 150*SS, 150*SS, GREEN, (14, 15, 16))
    elif kind == "B":   # big green W + white T badge
        letter_w(im, c, c - 70*SS, 520*SS, GREEN)
        t_badge(im, c, N - m - 140*SS, 140*SS, 140*SS, (240, 242, 244), (14, 15, 16))
    else:               # white W on green tile-in-tile + dark T
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([m + 70*SS, m + 70*SS, N - m - 70*SS, c + 150*SS], 90*SS, fill=GREEN_D)
        letter_w(im, c, (m + 70*SS + c + 150*SS) // 2, 380*SS, (240, 242, 244))
        t_badge(im, c, N - m - 130*SS, 130*SS, 130*SS, GREEN, (14, 15, 16))
    return im.resize((1024, 1024), Image.LANCZOS)

if __name__ == "__main__":
    im = concept("C")
    im.save(os.path.join(OUT, "icon.png"))
    im.save(os.path.join(OUT, "icon.icns"), format="ICNS",
            sizes=[(s, s) for s in (16, 32, 64, 128, 256, 512, 1024)])
    im.save(os.path.join(OUT, "icon.ico"), format="ICO",
            sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
