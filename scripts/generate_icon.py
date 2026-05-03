"""
EXO Assistant — Icon Generator v2
Design épuré, net à toutes les tailles.
Hexagone + onde vocale, style Fluent / VS Code.
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Palette (cohérente avec Theme.qml) ──
BG_CENTER = (30, 30, 30)       # #1E1E1E
BG_EDGE   = (15, 15, 20)
ACCENT    = (0, 120, 212)      # #0078D4
ACCENT_LT = (58, 150, 221)    # #3A96DD
GLOW_CLR  = (0, 122, 204)     # #007ACC
SUCCESS   = (78, 201, 176)    # #4EC9B0
WHITE     = (255, 255, 255)

BASE = 1024  # render size


def hexagon_points(cx, cy, radius, rotation=0):
    """6 points réguliers."""
    pts = []
    for i in range(6):
        angle = math.radians(60 * i + rotation)
        pts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return pts


def draw_hexagon(draw, cx, cy, radius, fill, outline=None, width=0, rotation=30):
    pts = hexagon_points(cx, cy, radius, rotation)
    if fill:
        draw.polygon(pts, fill=fill)
    if outline:
        draw.polygon(pts, outline=outline, width=width)


def make_icon() -> Image.Image:
    S = BASE
    cx, cy = S // 2, S // 2

    # 1) Fond — carré arrondi sombre
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bg = Image.new("RGBA", (S, S), (*BG_CENTER, 255))
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    corner = int(S * 0.20)
    md.rounded_rectangle([0, 0, S - 1, S - 1], radius=corner, fill=255)
    canvas.paste(bg, mask=mask)

    # 2) Halo bleu subtil derrière l'hexagone
    hex_r = int(S * 0.26)
    hex_cy = cy - int(S * 0.04)

    halo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    for i in range(60):
        t = i / 60
        r = hex_r + int(S * 0.12 * (1 - t))
        a = int(18 * (1 - t))
        hd.ellipse([cx - r, hex_cy - r, cx + r, hex_cy + r], fill=(*ACCENT, a))
    halo = halo.filter(ImageFilter.GaussianBlur(radius=15))
    canvas = Image.alpha_composite(canvas, halo)

    # 3) Hexagone — contour net, intérieur sombre
    draw = ImageDraw.Draw(canvas)
    # Fill sombre (plus sombre que le fond pour contraste)
    draw_hexagon(draw, cx, hex_cy, hex_r, fill=(20, 22, 28, 220), rotation=30)

    # Contour brillant
    hex_line = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hld = ImageDraw.Draw(hex_line)
    pts = hexagon_points(cx, hex_cy, hex_r, 30)
    # Glow du contour
    for w in [10, 8, 6]:
        hld.polygon(pts, outline=(*ACCENT, 40), width=w)
    # Contour principal
    hld.polygon(pts, outline=(*ACCENT_LT, 230), width=4)
    canvas = Image.alpha_composite(canvas, hex_line)

    # 4) Ondes vocales — inside the hexagon
    wave_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wave_layer)

    arcs = [
        (int(S * 0.10), 9, 255),
        (int(S * 0.16), 7, 200),
        (int(S * 0.22), 5, 140),
    ]
    for radius, width, alpha in arcs:
        bbox = [cx - radius, hex_cy - radius, cx + radius, hex_cy + radius]
        wd.arc(bbox, -35, 35, fill=(*SUCCESS, alpha), width=width)
        wd.arc(bbox, 145, 215, fill=(*SUCCESS, alpha), width=width)

    canvas = Image.alpha_composite(canvas, wave_layer)

    # 5) Point central lumineux
    dot_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dot_layer)
    dot_r = int(S * 0.018)
    # Glow
    for i in range(20):
        t = i / 20
        r = dot_r + int(15 * (1 - t))
        a = int(60 * (1 - t))
        dd.ellipse([cx - r, hex_cy - r, cx + r, hex_cy + r], fill=(*SUCCESS, a))
    dd.ellipse([cx - dot_r, hex_cy - dot_r, cx + dot_r, hex_cy + dot_r],
               fill=(*WHITE, 220))
    canvas = Image.alpha_composite(canvas, dot_layer)

    # 6) Texte "EXO"
    draw = ImageDraw.Draw(canvas)
    try:
        font_size = int(S * 0.17)
        font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    text = "EXO"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    tx = cx - tw // 2
    ty = hex_cy + hex_r + int(S * 0.06)

    # Glow texte
    tglow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    tgd = ImageDraw.Draw(tglow)
    tgd.text((tx, ty), text, font=font, fill=(*ACCENT, 60))
    tglow = tglow.filter(ImageFilter.GaussianBlur(radius=8))
    canvas = Image.alpha_composite(canvas, tglow)

    draw = ImageDraw.Draw(canvas)
    draw.text((tx, ty), text, font=font, fill=(*WHITE, 235))

    # 7) Bordure extérieure fine
    border = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle([2, 2, S - 3, S - 3], radius=corner,
                         outline=(*ACCENT, 40), width=2)
    canvas = Image.alpha_composite(canvas, border)

    return canvas


def main():
    print("Generating EXO icon v2...")
    icon = make_icon()

    sizes = [256, 128, 64, 48, 32, 24, 16]
    frames = []
    for s in sizes:
        resized = icon.resize((s, s), Image.LANCZOS)
        if s <= 48:
            resized = resized.filter(ImageFilter.SHARPEN)
        frames.append(resized)

    script_dir = Path(__file__).resolve().parent
    icons_dir = script_dir.parent / "resources" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    ico_path = icons_dir / "exo.ico"
    frames[0].save(str(ico_path), format="ICO",
                   sizes=[(s, s) for s in sizes],
                   append_images=frames[1:])
    print(f"ICO saved: {ico_path}")

    png_path = icons_dir / "exo_fullres.png"
    icon.save(str(png_path), "PNG")
    print(f"PNG saved: {png_path}")


if __name__ == "__main__":
    main()
