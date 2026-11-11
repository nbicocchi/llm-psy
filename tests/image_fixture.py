"""Deterministic grayscale PNG fixture; test data are generated in memory only."""
import binascii
import random
import struct

WIDTH = HEIGHT = 320


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)


def png(seed):
    rng = random.Random(seed)
    ellipses = [(rng.randrange(65, 160), rng.randrange(65, 255), rng.randrange(15, 49), rng.randrange(18, 56), rng.randrange(20, 100)) for _ in range(15)]
    pixels = bytearray()
    for y in range(HEIGHT):
        pixels.append(0)  # PNG filter: none
        for x in range(WIDTH):
            mirrored_x = min(x, WIDTH - 1 - x)
            shade = 255
            for cx, cy, rx, ry, color in ellipses:
                if (mirrored_x - cx)**2 * ry**2 + (y - cy)**2 * rx**2 <= rx**2 * ry**2:
                    shade = min(shade, color)
            pixels.append(shade)
    # zlib wrapper, stored DEFLATE blocks, Adler-32 (implemented explicitly).
    compressed = bytearray(b"\x78\x01")
    for offset in range(0, len(pixels), 65535):
        block = pixels[offset:offset + 65535]
        compressed.extend(bytes([int(offset + len(block) == len(pixels))]))
        compressed.extend(struct.pack("<HH", len(block), 65535 - len(block)))
        compressed.extend(block)
    a, b = 1, 0
    for byte in pixels:
        a = (a + byte) % 65521
        b = (b + a) % 65521
    compressed.extend(struct.pack(">I", (b << 16) | a))
    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", bytes(compressed)) + chunk(b"IEND", b"")

