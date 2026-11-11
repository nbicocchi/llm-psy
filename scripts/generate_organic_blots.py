"""New procedural folded-ink stimuli; never replace historical stimuli.

Python standard library only. Seeded geometry, paper grain and pigment fields
are reproducible with this generator version and Python/zlib implementation.
These images are original illustrations, not clinical Rorschach plates.
"""

import hashlib
import argparse
import json
import math
from pathlib import Path
import random
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "folded-ink-organic-v1"
SIZE = 640
HALF = SIZE // 2
PRESETS = (
    (271828, "Charcoal wash", "charcoal"),
    (314159, "Charcoal and vermilion", "vermilion"),
    (161803, "Muted pigment study", "pigment"),
)
DIVERSE_PRESETS = (
    (577219, "Wide charcoal fan", "charcoal", "wide"),
    (693147, "Vertical charcoal and red", "vermilion", "vertical"),
    (223607, "Separated pigment islands", "pigment", "islands"),
)
EXPERIMENTAL_PRESETS = (
    (141421, "Broken ink arch", "charcoal", "arch"),
    (173205, "Low red crescent", "vermilion", "crescent"),
    (244949, "Radiating pigment branches", "pigment", "branches"),
)


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def noise(x, y, seed, scale):
    """Smooth, coordinate-addressed noise; independent of traversal order."""
    gx, fx = divmod(x, scale)
    gy, fy = divmod(y, scale)

    def corner(a, b):
        value = (a * 374761393 + b * 668265263 + seed * 1442695041) & 0xFFFFFFFF
        value = ((value ^ (value >> 13)) * 1274126177) & 0xFFFFFFFF
        return (value ^ (value >> 16)) & 255

    a = corner(gx, gy) * (scale - fx) + corner(gx + 1, gy) * fx
    b = corner(gx, gy + 1) * (scale - fx) + corner(gx + 1, gy + 1) * fx
    return (a * (scale - fy) + b * fy) // (scale * scale)


def organic_png(seed, style="charcoal", size=SIZE, layout="classic"):
    if style not in {"charcoal", "vermilion", "pigment"}:
        raise ValueError("Unknown pigment style")
    if size != SIZE:
        raise ValueError("This version fixes the stimulus size at 640 pixels")
    if layout not in {"classic", "wide", "vertical", "islands", "arch", "crescent", "branches"}:
        raise ValueError("Unknown composition layout")
    rng = random.Random(seed)
    roughness = [
        (noise(x, y, seed, 11) - 128) / 420 + (noise(x, y, seed + 1, 37) - 128) / 360
        for y in range(SIZE) for x in range(HALF)
    ]

    def layer(paths):
        field = bytearray(HALF * SIZE)
        for path, radius, strength in paths:
            for cx, cy in path:
                rx = radius * rng.uniform(0.6, 1.2)
                ry = radius * rng.uniform(0.7, 1.45)
                angle = rng.uniform(-1.0, 1.0)
                cosine, sine = math.cos(angle), math.sin(angle)
                bound = int(max(rx, ry) * 1.5) + 2
                for y in range(max(0, int(cy - bound)), min(SIZE, int(cy + bound))):
                    for x in range(max(0, int(cx - bound)), min(HALF, int(cx + bound))):
                        dx, dy = x - cx, y - cy
                        u, v = (dx * cosine + dy * sine) / rx, (-dx * sine + dy * cosine) / ry
                        index = y * HALF + x
                        pressure = 1 - u * u - v * v + roughness[index]
                        if pressure > 0:
                            # Soft wet edges, concentrated interiors, irregular
                            # dry-paper gaps; no hard geometric ellipse borders.
                            value = min(255, int(strength * min(1, pressure * 2.8)))
                            field[index] = max(field[index], value)
        return field

    def trail(points, steps=4):
        result = []
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            for step in range(steps):
                t = step / steps
                result.append((ax + t * (bx - ax) + rng.uniform(-8, 8), ay + t * (by - ay) + rng.uniform(-8, 8)))
        return result + [points[-1]]

    # Asymmetric half-gestures become bilateral only through simulated folding.
    shift = rng.randrange(-22, 23)
    main = [
        (trail([(316, 160), (278, 200), (220, 192 + shift), (161, 154), (116, 210)]), 34, 235),
        (trail([(303, 223), (251, 262), (184, 250), (140, 299), (112, 320)]), 42, 245),
        (trail([(318, 266), (291, 326), (239, 355), (191, 389), (218, 431)]), 42, 250),
        (trail([(310, 347), (296, 415), (271, 457), (236, 478)]), 28, 225),
        (trail([(310, 186), (306, 133), (282, 102)]), 17, 240),
        (trail([(170, 266), (115, 255), (86, 226)]), 13, 225),
        (trail([(170, 355), (124, 394), (105, 436)]), 13, 220),
        (trail([(308, 421), (301, 478), (286, 530)]), 12, 230),
    ]
    if layout == "wide":
        main = [
            (trail([(319, 289), (265, 247), (207, 215), (143, 189), (94, 208), (58, 262)]), 34, 244),
            (trail([(298, 291), (245, 283), (191, 275), (127, 275), (65, 303)]), 30, 240),
            (trail([(304, 318), (263, 342), (209, 366), (155, 378), (90, 354)]), 29, 234),
            (trail([(317, 303), (309, 342), (291, 393)]), 25, 251),
            (trail([(166, 207), (139, 157), (108, 134)]), 11, 219),
            (trail([(210, 364), (188, 406), (151, 438)]), 12, 214),
        ]
    elif layout == "vertical":
        main = [
            (trail([(319, 83), (295, 119), (301, 173), (283, 219)]), 20, 240),
            (trail([(309, 237), (282, 267), (259, 304), (278, 340)]), 26, 246),
            (trail([(309, 354), (284, 398), (294, 439), (310, 476), (297, 547)]), 23, 248),
            (trail([(276, 298), (241, 270), (219, 222)]), 12, 220),
            (trail([(286, 376), (253, 413), (230, 437)]), 10, 213),
        ]
    elif layout == "islands":
        main = [
            (trail([(298, 176), (277, 193)]), 16, 180),
            (trail([(239, 312), (216, 330)]), 20, 185),
            (trail([(292, 460), (272, 483)]), 17, 180),
            ([(164, 163), (112, 379), (201, 492)], 6, 175),
        ]
    elif layout == "arch":
        main = [
            (trail([(318, 120), (267, 110), (219, 147), (181, 206), (157, 282)]), 29, 245),
            (trail([(151, 310), (137, 367), (159, 421), (202, 467)]), 24, 236),
            (trail([(222, 151), (181, 122), (144, 133)]), 9, 213),
            (trail([(157, 282), (104, 299), (83, 330)]), 11, 222),
            (trail([(178, 440), (151, 478), (137, 514)]), 10, 218),
            ([(275, 528), (256, 540)], 15, 226),
        ]
    elif layout == "crescent":
        main = [
            (trail([(318, 438), (262, 427), (205, 394), (146, 350), (101, 288)]), 30, 243),
            (trail([(302, 465), (248, 469), (188, 444), (133, 405), (93, 356)]), 25, 235),
            (trail([(318, 438), (310, 390), (286, 368)]), 15, 245),
            (trail([(139, 341), (102, 315), (72, 328)]), 10, 212),
            ([(252, 219), (237, 202)], 13, 215),
        ]
    elif layout == "branches":
        main = [
            (trail([(317, 303), (285, 292), (250, 272)]), 21, 200),
            (trail([(283, 282), (251, 233), (226, 179), (195, 129)]), 10, 205),
            (trail([(267, 295), (210, 284), (153, 253), (102, 228)]), 9, 210),
            (trail([(282, 319), (234, 350), (183, 384), (128, 407)]), 10, 212),
            (trail([(303, 331), (279, 389), (259, 446), (226, 500)]), 11, 208),
            (trail([(312, 275), (297, 219), (299, 170)]), 8, 200),
        ]
    if style == "pigment":
        main = [(path, radius * .78, strength * .64) for path, radius, strength in main]
    dark = layer(main)
    colors = []
    if style == "vermilion":
        red_paths = [
            (trail([(300, 342), (264, 374), (229, 397)]), 38, 220),
            (trail([(302, 218), (275, 235)]), 21, 190),
        ]
        if layout == "vertical":
            red_paths = [
                (trail([(311, 209), (298, 228)]), 15, 235),
                (trail([(302, 400), (277, 424), (291, 444)]), 18, 230),
            ]
        elif layout == "crescent":
            red_paths = [
                (trail([(310, 455), (263, 447), (211, 425), (165, 390)]), 24, 238),
                (trail([(248, 214), (230, 193)]), 17, 221),
            ]
        colors.append((layer(red_paths), (145, 44, 33)))
    elif style == "pigment":
        pigment_paths = (
            ([(213, 173), (158, 142), (120, 183)], (181, 117, 61)),
            ([(170, 286), (118, 320), (146, 359)], (72, 117, 122)),
            ([(253, 405), (214, 441), (252, 485)], (128, 94, 136)),
            ([(308, 235), (281, 274)], (115, 133, 83)),
        )
        if layout == "islands":
            pigment_paths = (
                ([(193, 130), (159, 108), (132, 132)], (191, 131, 56)),
                ([(119, 251), (81, 280), (109, 314)], (64, 119, 137)),
                ([(246, 319), (215, 344)], (137, 81, 111)),
                ([(191, 449), (155, 477), (179, 513)], (104, 130, 79)),
                ([(306, 172), (280, 191)], (154, 98, 60)),
            )
        elif layout == "branches":
            pigment_paths = (
                ([(230, 181), (209, 144), (187, 116)], (161, 106, 63)),
                ([(153, 256), (114, 236), (82, 218)], (66, 119, 128)),
                ([(186, 382), (151, 397), (118, 418)], (146, 89, 116)),
                ([(257, 449), (239, 478), (213, 512)], (115, 138, 64)),
                ([(312, 298), (292, 306)], (120, 99, 151)),
            )
        for points, pigment in pigment_paths:
            colors.append((layer([(trail(points), 27 if layout == "islands" else 33, 220)]), pigment))
    pixels = bytearray()
    for y in range(SIZE):
        pixels.append(0)
        half = bytearray()
        for x in range(HALF):
            index = y * HALF + x
            grain = (noise(x, y, seed + 9, 1) - 128) / 40
            paper = [int(246 + grain), int(243 + grain), int(234 + grain)]
            # Fine granulation and pooled pigment vary inside the silhouette.
            granulation = .76 + noise(x, y, seed + 4, 5) / 1060
            opacity = min(.97, dark[index] / 255 * granulation)
            rgb = [paper[channel] * (1 - opacity) + (30, 29, 27)[channel] * opacity for channel in range(3)]
            for field, pigment in colors:
                alpha = field[index] / 255 * .82 * granulation
                rgb = [rgb[channel] * (1 - alpha) + pigment[channel] * alpha for channel in range(3)]
            # A subtle fold on the paper, not a heavy artificial center line.
            crease = .985 if x == HALF - 1 else 1
            half.extend(max(0, min(255, round(value * crease))) for value in rgb)
        pixels.extend(half)
        for x in range(HALF - 1, -1, -1):
            pixels.extend(half[x * 3:x * 3 + 3])
    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(pixels), 9)) + chunk(b"IEND", b"")


def write_if_unchanged(path, content):
    if path.exists() and path.read_bytes() != content:
        raise RuntimeError(f"Refusing to overwrite modified stimulus or metadata: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", choices=("original-v1", "diverse-v2", "experimental-v3"), default="original-v1")
    args = parser.parse_args(argv)
    diverse = args.series == "diverse-v2"
    experimental = args.series == "experimental-v3"
    version = "folded-ink-experimental-v3" if experimental else "folded-ink-diverse-v2" if diverse else VERSION
    directory = "blots-organic-v3" if experimental else "blots-organic-v2" if diverse else "blots-organic-v1"
    presets = EXPERIMENTAL_PRESETS if experimental else DIVERSE_PRESETS if diverse else [(seed, title, style, "classic") for seed, title, style in PRESETS]
    manifest = {"generator": version, "width": SIZE, "height": SIZE, "stimuli": []}
    for index, (seed, title, style, layout) in enumerate(presets, 1):
        filename = f"organic-{index + (6 if experimental else 3 if diverse else 0):03d}.png"
        content = organic_png(seed, style, layout=layout)
        source = ROOT / "assets/blots-organic" / filename
        public = ROOT / "site/assets" / directory / filename
        write_if_unchanged(source, content)
        write_if_unchanged(public, content)
        manifest["stimuli"].append({"id": filename[:-4], "title": title, "seed": seed, "style": style,
            "file": str(source.relative_to(ROOT)), "url": f"/assets/{directory}/" + filename,
            "sha256": hashlib.sha256(content).hexdigest()})
        if diverse or experimental:
            manifest["stimuli"][-1].update(layout=layout, generator=version)
    content = (json.dumps(manifest, indent=2) + "\n").encode()
    write_if_unchanged(ROOT / "assets/blots-organic" / ("manifest-v3.json" if experimental else "manifest-v2.json" if diverse else "manifest.json"), content)
    print(f"Prepared {len(manifest['stimuli'])} new folded-ink illustrations. No experiments executed.")


if __name__ == "__main__":
    main()
