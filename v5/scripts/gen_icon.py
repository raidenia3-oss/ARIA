"""Genera assets/icon.ico + assets/icon.png para ARIA OS v5.0 (orbe cyan)."""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512
OUT = Path(__file__).resolve().parent.parent / "assets"


def radial(size: int, inner: tuple, outer: tuple) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    center = size / 2
    max_r = size * 0.5
    steps = 220
    for i in range(steps, 0, -1):
        ratio = i / steps
        radius = max_r * ratio
        alpha = int(255 * (1 - ratio) ** 1.6)
        color = tuple(
            int(inner[c] + (outer[c] - inner[c]) * ratio) for c in range(3)
        )
        draw.ellipse(
            [center - radius, center - radius, center + radius, center + radius],
            fill=color + (alpha,),
        )
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    icon = Image.new("RGBA", (SIZE, SIZE), (10, 14, 39, 255))
    draw = ImageDraw.Draw(icon)

    # Fondo redondeado con degradado vertical (navy -> indigo)
    for y in range(SIZE):
        ratio = y / SIZE
        color = (
            int(10 + 10 * ratio),
            int(14 + 16 * ratio),
            int(39 + 24 * ratio),
            255,
        )
        draw.line([(0, y), (SIZE, y)], fill=color)

    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=96, fill=255)
    icon.putalpha(mask)

    # Halo del orbe
    glow = radial(SIZE, (56, 189, 248), (0, 212, 255))
    glow = glow.resize((int(SIZE * 0.92), int(SIZE * 0.92)))
    icon.alpha_composite(glow, (int(SIZE * 0.04), int(SIZE * 0.04)))

    # Núcleo brillante
    core = radial(int(SIZE * 0.42), (255, 255, 255), (56, 189, 248))
    offset = int((SIZE - core.width) / 2)
    icon.alpha_composite(core, (offset, offset))

    # Rombo (glyph ARIA)
    cx, cy, r = SIZE / 2, SIZE / 2, SIZE * 0.20
    draw.polygon(
        [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)],
        fill=(255, 255, 255, 235),
    )

    icon.save(OUT / "icon.png")
    icon.save(
        OUT / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"OK: {OUT / 'icon.ico'} y {OUT / 'icon.png'}")


if __name__ == "__main__":
    main()
