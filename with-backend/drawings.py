"""Simple drawings for the made-up posts, made with only the Python standard library.

A picture is a grid of pixels, each a red, green and blue amount from 0 to 255. We fill shapes
row by row (a circle is, row by row, a line from its left edge to its right edge), then save the
grid as a PNG file: a short header, then the rows, squeezed with zlib.

Everything is drawn twice as big and then shrunk, mixing each 2×2 square of pixels into one,
so that the edges of the shapes come out smooth instead of jagged.

These are illustrations, not photos: seed.py gives them to its made-up posts.
"""

import math
import random
import struct
import zlib

WIDTH, HEIGHT = 600, 400   # the size of each picture
SCALE = 2                  # drawn this many times bigger, then shrunk, for smooth edges


class Canvas:
    """A grid of pixels to draw on. Sizes and places are given in final pixels (600 × 400)."""

    def __init__(self, colour):
        self.width, self.height = WIDTH * SCALE, HEIGHT * SCALE
        self.pixels = bytearray(bytes(colour) * (self.width * self.height))

    def span(self, y, x0, x1, colour):
        """Colour one row, from x0 to x1 (in the big grid)."""
        if not 0 <= y < self.height:
            return
        x0, x1 = max(0, int(round(x0))), min(self.width, int(round(x1)))
        if x1 > x0:
            start = (y * self.width + x0) * 3
            self.pixels[start:start + (x1 - x0) * 3] = bytes(colour) * (x1 - x0)

    def gradient(self, y0, y1, top, bottom):
        """Rows from y0 to y1, changing smoothly from one colour to another."""
        y0, y1 = int(y0 * SCALE), int(y1 * SCALE)
        for y in range(y0, y1):
            t = (y - y0) / max(1, y1 - y0 - 1)
            colour = [round(a + (b - a) * t) for a, b in zip(top, bottom)]
            self.span(y, 0, self.width, colour)

    def rect(self, x0, y0, x1, y1, colour):
        for y in range(int(y0 * SCALE), int(y1 * SCALE)):
            self.span(y, x0 * SCALE, x1 * SCALE, colour)

    def ellipse(self, cx, cy, rx, ry, colour):
        cx, cy, rx, ry = cx * SCALE, cy * SCALE, rx * SCALE, ry * SCALE
        for y in range(int(cy - ry), int(cy + ry) + 1):
            rest = 1 - ((y + 0.5 - cy) / ry) ** 2
            if rest > 0:
                half = rx * math.sqrt(rest)
                self.span(y, cx - half, cx + half, colour)

    def polygon(self, points, colour):
        """Any shape with straight sides: for each row, find where the sides cross it, and fill
        between each pair of crossings."""
        points = [(x * SCALE, y * SCALE) for x, y in points]
        top = int(min(y for _, y in points))
        bottom = int(max(y for _, y in points)) + 1
        for y in range(top, bottom):
            middle = y + 0.5
            crossings = []
            for (xa, ya), (xb, yb) in zip(points, points[1:] + points[:1]):
                if (ya <= middle < yb) or (yb <= middle < ya):
                    crossings.append(xa + (middle - ya) * (xb - xa) / (yb - ya))
            crossings.sort()
            for x0, x1 in zip(crossings[::2], crossings[1::2]):
                self.span(y, x0, x1, colour)

    def line(self, x0, y0, x1, y1, thickness, colour):
        """A thick straight line, drawn as a long thin four-sided shape."""
        length = math.hypot(x1 - x0, y1 - y0) or 1
        nx, ny = -(y1 - y0) / length * thickness / 2, (x1 - x0) / length * thickness / 2
        self.polygon([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], colour)

    def png(self):
        """Shrink the big grid to the final size, mixing each 2×2 square, and save it as PNG."""
        row = self.width * 3
        small = bytearray()
        for y in range(0, self.height, 2):
            upper, lower = self.pixels[y * row:(y + 1) * row], self.pixels[(y + 1) * row:(y + 2) * row]
            small.append(0)   # each PNG row starts with a 0: "no filter"
            for x in range(0, row, 6):
                small += bytes(((upper[x + c] + upper[x + 3 + c] + lower[x + c] + lower[x + 3 + c]) >> 2)
                               for c in range(3))
        return png_file(WIDTH, HEIGHT, bytes(small))


def png_file(width, height, rows):
    """A PNG file: the signature, a header (size, 8 bits, colour), the squeezed rows, an end."""
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


# ---- The colours ----

VERMILION, VERMILION_DARK = (214, 58, 36), (160, 38, 24)
BLACK = (34, 30, 30)
WHITE, CREAM = (250, 249, 245), (240, 230, 205)
WOOD, WOOD_DARK = (176, 128, 84), (150, 104, 66)


def table(canvas):
    """A wooden table: brown, with darker lines between the boards."""
    canvas.gradient(0, HEIGHT, (186, 138, 92), (160, 112, 70))
    for y in range(40, HEIGHT, 72):
        canvas.rect(0, y, WIDTH, y + 3, WOOD_DARK)


def plate(canvas, cx, cy, rx, ry):
    canvas.ellipse(cx + 6, cy + 10, rx, ry, (120, 86, 56))   # its shadow on the table
    canvas.ellipse(cx, cy, rx, ry, (214, 214, 210))
    canvas.ellipse(cx, cy - 2, rx * 0.86, ry * 0.84, WHITE)


# ---- The drawings ----

def torii_gates():
    """Fushimi Inari: rows of vermilion gates, getting smaller into the forest."""
    canvas = Canvas((30, 60, 40))
    canvas.gradient(0, HEIGHT, (36, 70, 46), (20, 44, 30))
    canvas.polygon([(260, 150), (340, 150), (WIDTH + 80, HEIGHT), (-80, HEIGHT)], (156, 150, 138))  # the path
    canvas.polygon([(285, 150), (315, 150), (420, HEIGHT), (180, HEIGHT)], (176, 170, 158))
    for step in range(14, -1, -1):           # far away first, so the near gates cover them
        size = 1 / (1 + step * 0.42)          # each gate further away is smaller
        cx, base = 300, 150 + 260 * size
        half, tall = 230 * size, 330 * size
        pillar = 26 * size
        top = base - tall
        shade = VERMILION if step % 2 == 0 else VERMILION_DARK
        canvas.rect(cx - half, top + 30 * size, cx - half + pillar, base, shade)       # left pillar
        canvas.rect(cx + half - pillar, top + 30 * size, cx + half, base, shade)       # right pillar
        canvas.rect(cx - half - 22 * size, top, cx + half + 22 * size, top + 16 * size, BLACK)          # top beam
        canvas.rect(cx - half - 12 * size, top + 16 * size, cx + half + 12 * size, top + 34 * size, shade)
        canvas.rect(cx - half, top + 74 * size, cx + half, top + 90 * size, shade)     # lower beam
        canvas.rect(cx - half - 4 * size, base - 18 * size, cx - half + pillar + 4 * size, base, BLACK)  # feet
        canvas.rect(cx + half - pillar - 4 * size, base - 18 * size, cx + half + 4 * size, base, BLACK)
    return canvas.png()


def autumn_tree():
    """Autumn on campus: a maple tree in red, orange and yellow under a blue sky."""
    chance = random.Random(7)
    canvas = Canvas((150, 200, 240))
    canvas.gradient(0, 300, (110, 170, 230), (205, 228, 245))
    canvas.ellipse(140, 330, 330, 80, (120, 150, 90))     # far hills
    canvas.ellipse(520, 340, 300, 70, (100, 135, 80))
    canvas.rect(0, 320, WIDTH, HEIGHT, (150, 120, 70))     # the ground
    canvas.polygon([(285, 330), (315, 330), (308, 200), (292, 200)], (92, 62, 42))        # the trunk
    canvas.line(300, 240, 230, 170, 10, (92, 62, 42))
    canvas.line(300, 230, 370, 160, 10, (92, 62, 42))
    leaves = [(200, 40, 30), (225, 80, 30), (238, 130, 40), (245, 180, 60), (180, 30, 40)]
    for _ in range(420):
        angle, distance = chance.uniform(0, math.tau), chance.random() ** 0.6
        x, y = 300 + math.cos(angle) * 170 * distance, 150 + math.sin(angle) * 105 * distance
        canvas.ellipse(x, y, chance.uniform(7, 15), chance.uniform(6, 12), chance.choice(leaves))
    for _ in range(70):   # leaves on the ground, and some still falling
        canvas.ellipse(chance.uniform(0, WIDTH), chance.uniform(325, HEIGHT), 7, 4, chance.choice(leaves))
    for _ in range(12):
        canvas.ellipse(chance.uniform(80, 520), chance.uniform(230, 310), 6, 4, chance.choice(leaves))
    return canvas.png()


def sauce_crossings(x_middle, direction, cx=300, cy=200, rx=150, ry=96):
    """Where a slanted line through (x_middle, cy) enters and leaves the ellipse of sauce."""
    dx, dy = 1.0, 0.75 * direction          # the slant of the line
    # Points on the line: (x_middle + t·dx, cy + t·dy). Put them into the ellipse's equation.
    a = (dx / rx) ** 2 + (dy / ry) ** 2
    b = 2 * (x_middle - cx) * dx / rx ** 2
    c = ((x_middle - cx) / rx) ** 2 - 1
    inside = b * b - 4 * a * c
    if inside <= 0:
        return None
    t0, t1 = (-b - math.sqrt(inside)) / (2 * a), (-b + math.sqrt(inside)) / (2 * a)
    return (x_middle + t0 * dx, cy + t0 * dy), (x_middle + t1 * dx, cy + t1 * dy)


def okonomiyaki():
    """Okonomiyaki on a plate: brown sauce, white mayonnaise in zigzags, green aonori."""
    chance = random.Random(3)
    canvas = Canvas(WOOD)
    table(canvas)
    plate(canvas, 300, 210, 250, 165)
    canvas.ellipse(300, 205, 175, 118, (196, 140, 70))    # the pancake
    canvas.ellipse(300, 200, 165, 110, (92, 48, 24))      # the sauce
    # Mayonnaise in a criss-cross, each line ending at the edge of the sauce.
    for direction in (1, -1):
        for i in range(-4, 5):
            ends = sauce_crossings(300 + i * 42, direction)
            if ends:
                (x0, y0), (x1, y1) = ends
                canvas.line(x0, y0, x1, y1, 4, CREAM)
    for _ in range(140):                                    # aonori and katsuobushi
        x, y = chance.uniform(170, 430), chance.uniform(120, 280)
        if ((x - 300) / 160) ** 2 + ((y - 200) / 105) ** 2 < 1:
            if chance.random() < 0.7:
                canvas.ellipse(x, y, 2.5, 2.5, (70, 120, 50))
            else:
                canvas.ellipse(x, y, 6, 3.5, (226, 170, 150))
    return canvas.png()


def curry_rice():
    """Japanese curry: white rice on one side, brown curry with carrot and potato on the other."""
    chance = random.Random(5)
    canvas = Canvas(WOOD)
    table(canvas)
    plate(canvas, 300, 210, 260, 160)
    canvas.ellipse(300, 205, 215, 125, (150, 86, 30))     # curry under everything
    canvas.ellipse(225, 195, 125, 100, (246, 244, 236))   # the rice
    canvas.ellipse(215, 185, 100, 78, WHITE)
    for _ in range(14):                                     # carrot and potato
        x, y = chance.uniform(330, 470), chance.uniform(140, 290)
        colour = (232, 120, 40) if chance.random() < 0.5 else (232, 196, 120)
        canvas.polygon([(x, y), (x + 22, y - 4), (x + 26, y + 18), (x + 4, y + 22)], colour)
    canvas.line(440, 330, 560, 380, 14, (200, 200, 205))  # the spoon
    canvas.ellipse(430, 325, 26, 17, (215, 215, 220))
    return canvas.png()


def miso_soup():
    """A red lacquer bowl of miso soup, with tofu, wakame and green onion."""
    chance = random.Random(11)
    canvas = Canvas(WOOD)
    table(canvas)
    canvas.ellipse(306, 222, 205, 150, (110, 76, 50))     # shadow
    canvas.ellipse(300, 210, 205, 150, (120, 24, 24))     # the bowl
    canvas.ellipse(300, 200, 180, 128, (60, 12, 14))      # its inside edge
    canvas.ellipse(300, 205, 170, 118, (206, 150, 84))    # the soup
    canvas.ellipse(285, 190, 120, 70, (218, 166, 100))
    for _ in range(9):                                      # tofu
        x, y = chance.uniform(180, 400), chance.uniform(140, 260)
        canvas.polygon([(x, y), (x + 26, y - 6), (x + 32, y + 18), (x + 6, y + 24)], (250, 246, 232))
    for _ in range(6):                                      # wakame
        canvas.ellipse(chance.uniform(190, 410), chance.uniform(150, 270), 22, 9, (40, 70, 40))
    for _ in range(26):                                     # green onion
        x, y = chance.uniform(180, 420), chance.uniform(130, 280)
        canvas.ellipse(x, y, 7, 6, (90, 160, 60))
        canvas.ellipse(x, y, 3.5, 3, (206, 150, 84))
    return canvas.png()


def gyoza():
    """Five golden gyoza on a long plate, with a small bowl of dipping sauce."""
    canvas = Canvas(WOOD)
    table(canvas)
    canvas.rect(70, 140, 470, 300, (130, 96, 64))         # shadow of the plate
    canvas.rect(60, 128, 460, 288, (232, 232, 228))
    canvas.rect(72, 140, 448, 276, WHITE)

    def half_moon(x, bottom, half_width, height):
        # A gyoza seen from the side: the top half of an ellipse, standing on its flat side.
        angles = [k * math.pi / 24 for k in range(25)]
        return [(x + half_width * math.cos(a), bottom - height * math.sin(a)) for a in angles]

    for i in range(5):
        x, bottom = 112 + i * 74, 250 - (i % 2) * 6
        canvas.polygon(half_moon(x, bottom + 2, 38, 60), (168, 128, 72))     # a darker edge
        canvas.polygon(half_moon(x, bottom, 35, 57), (240, 218, 166))
        canvas.polygon([(x - 34, bottom - 2), (x + 34, bottom - 2), (x + 30, bottom + 10),
                        (x - 30, bottom + 10)], (176, 108, 38))               # the browned bottom
        for k in range(4):                                                     # the folds
            fx = x - 15 + k * 10
            canvas.line(fx, bottom - 52 + abs(1.5 - k) * 4, fx + 3, bottom - 40 + abs(1.5 - k) * 4,
                        2.5, (206, 172, 112))
    canvas.ellipse(530, 300, 56, 40, (60, 30, 30))        # the sauce bowl
    canvas.ellipse(530, 294, 46, 30, (120, 60, 30))
    canvas.ellipse(518, 288, 9, 5, (220, 150, 60))         # a drop of chili oil
    return canvas.png()


# Which drawing goes with which made-up post (by its key in seed.POSTS).
FOR_POSTS = {
    "inari": torii_gates,
    "leaves": autumn_tree,
    "okonomiyaki": okonomiyaki,
    "curry": curry_rice,
    "miso": miso_soup,
    "gyoza": gyoza,
}
