"""Builds the optional printables for every activity on the wheel.

    pip install reportlab svglib
    python3 tools/make_printables.py

Reads the games, icons and word lists straight out of index.html (via extract.js, needs node)
and writes printables/<game>.pdf, printables/all-printables.pdf and printables/printables.js.
Every PDF starts with a rules poster; games that use materials get cards, signs, sheets or certificates after it.
"""
import io, json, os, re, subprocess, tempfile
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "printables")
DATA = json.loads(subprocess.check_output(["node", os.path.join(HERE, "extract.js")]))
ACTS, ICONS, L, SCREENS = DATA["ACTIVITIES"], DATA["ICON_PATHS"], DATA["L"], DATA["SCREENS"]

pdfmetrics.registerFont(TTFont("Pixel", os.path.join(HERE, "fonts", "PressStart2P-Regular.ttf")))
PIX, BODY, BOLD = "Pixel", "Helvetica", "Helvetica-Bold"

MIDNIGHT, SUNSHINE, ORANGE, CREAM, PACIFIC = (HexColor(x) for x in ("#1D2A44", "#FFBC0D", "#FF4C00", "#FFF7ED", "#0094C7"))
GREY, LIGHT = HexColor("#555555"), HexColor("#BBBBBB")
COLORS = [HexColor(x) for x in ("#FF4C00", "#0094C7", "#FFBC0D", "#6FB300", "#E75CAE", "#00AFAB", "#A973DF", "#FF9B0D", "#4FD2FF", "#F27179")]
# darker partners for text that has to read on white paper
INK = [HexColor(x) for x in ("#D93F00", "#0077A3", "#B37F00", "#4E8000", "#C2408D", "#00807D", "#7B45B5", "#D97700", "#0077A3", "#D04A54")]
M = 36  # page margin


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("&", "and")).strip("-")


def wrap(text, font, size, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(t, font, size) <= width or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


def fit(text, font, size, width, min_size=6):
    while size > min_size and pdfmetrics.stringWidth(text, font, size) > width:
        size -= 0.5
    return size


_icon_cache = {}
def icon(c, name, x, y, size, color="#1D2A44"):
    key = (name, color)
    if key not in _icon_cache:
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" '
               f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')
        with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as f:
            f.write(svg); p = f.name
        _icon_cache[key] = p
    d = svg2rlg(_icon_cache[key])
    s = size / 24.0
    d.width *= s; d.height *= s; d.scale(s, s)
    renderPDF.draw(d, c, x - size / 2, y - size / 2)


# ---------------------------------------------------------------- page frame
class Doc:
    """Draws the same pages into the game's own PDF and the all-in-one PDF."""
    def __init__(self, *canvases):
        self.cs = canvases

    def page(self, fn, land=False):
        for c in self.cs:
            w, h = landscape(letter) if land else letter
            c.setPageSize((w, h))
            fn(c, w, h)
            c.showPage()


def frame(c, w, h, game, label):
    band = 30
    c.setFillColor(MIDNIGHT); c.rect(0, h - band, w, band, stroke=0, fill=1)
    c.setFillColor(SUNSHINE); c.setFont(PIX, 8); c.drawString(M, h - 19, "INDOOR RECESS-O-MATIC")
    c.setFillColor(CREAM); c.setFont(PIX, 7); c.drawRightString(w - M, h - 19, label.upper())
    seg = w / len(COLORS)
    for k, col in enumerate(COLORS):
        c.setFillColor(col); c.rect(k * seg, h - band - 4, seg + 0.5, 4, stroke=0, fill=1)
    c.setFillColor(GREY); c.setFont(BODY, 8)
    c.drawCentredString(w / 2, 16, f"{game}  •  Indoor Recess-O-Matic  •  mrpiercey.github.io/indoor-recess-o-matic")
    return h - band - 4  # top of the usable area


def pixel_title(c, text, cx, y, size, width, color=PACIFIC, shadow=SUNSHINE):
    size = fit(text, PIX, size, width)
    c.setFont(PIX, size)
    off = max(1.5, size * 0.08)
    c.setFillColor(shadow); c.drawCentredString(cx + off, y - off, text)
    c.setFillColor(color); c.drawCentredString(cx, y, text)
    return size


def cut_note(c, w, y, text="Print, then cut along the dashed lines."):
    c.setFillColor(GREY); c.setFont(BODY, 10); c.drawCentredString(w / 2, y, "✂  " + text)


def name_line(c, x, y, w, label="Name"):
    c.setFillColor(MIDNIGHT); c.setFont(BOLD, 12); c.drawString(x, y, label)
    lw = pdfmetrics.stringWidth(label, BOLD, 12)
    c.setStrokeColor(MIDNIGHT); c.setLineWidth(1); c.line(x + lw + 6, y - 2, x + w, y - 2)


def checkbox(c, x, y, s=11):
    c.setStrokeColor(MIDNIGHT); c.setLineWidth(1.2); c.rect(x, y, s, s, stroke=1, fill=0)


# ---------------------------------------------------------------- page types
def poster(act, idx, packet):
    name = act["n"]
    steps = [s for s in re.split(r"(?:(?<=[.!?])|(?<=[.!?]['’\"]))\s+(?=[A-Z0-9'\"])", act["d"]) if s]
    needs = NEEDS.get(name, [])
    scr = SCREENS.get(name)
    screen_line = None
    if scr:
        screen_line = ("Tap LET'S PLAY! on the wheel to roll a prompt." if scr["kind"] == "reel"
                       else "Tap LET'S PLAY! on the wheel for the timer and sounds.")

    def draw(c, w, h):
        top = frame(c, w, h, name, "Rules poster")
        col, ink = COLORS[idx % len(COLORS)], INK[idx % len(INK)]
        cy = top - 78
        c.setFillColor(MIDNIGHT); c.circle(w / 2 + 4, cy - 4, 52, stroke=0, fill=1)
        c.setFillColor(col); c.setStrokeColor(MIDNIGHT); c.setLineWidth(3); c.circle(w / 2, cy, 52, stroke=1, fill=1)
        c.setFillColor(CREAM); c.circle(w / 2, cy, 40, stroke=0, fill=1)
        icon(c, act["i"], w / 2, cy, 50)
        y = cy - 98
        pixel_title(c, name.upper(), w / 2, y, 30, w - 2 * M)
        y -= 44
        c.setFillColor(ORANGE); c.setFont(PIX, 13); c.drawString(M + 10, y, "HOW TO PLAY")
        # two boxes along the bottom
        bw, gap = (w - 2 * M - 16) / 2, 16
        boxes = [("YOU'LL NEED", needs or ["Nothing! Just the class."]),
                 ("IN THIS PACKET", ["This rules poster"] + packet)]
        heights = []
        for title, items in boxes:
            n = sum(len(wrap(t, BODY, 12, bw - 34)) for t in items)
            heights.append(34 + n * 15 + len(items) * 3 + 8)
        bh = max(heights)
        by = 40 + (26 if screen_line else 0)
        # biggest step text that fits between the heading and the boxes (readable from across the room)
        avail = y - 30 - (by + bh + 24)
        tw = w - 2 * M - 62
        for fs in range(30, 13, -1):
            lead, sgap = fs * 1.28, fs * 0.8
            blocks = [wrap(s, BODY, fs, tw) for s in steps]
            if sum(len(b) * lead + sgap for b in blocks) <= avail: break
        y -= 22 + fs
        sq = fs * 1.55
        for k, lines in enumerate(blocks, 1):
            c.setFillColor(ink); c.rect(M + 10, y - sq * 0.5 + fs * 0.32, sq, sq, stroke=0, fill=1)
            c.setFillColor(HexColor("#FFFFFF")); c.setFont(PIX, fs * 0.7); c.drawCentredString(M + 10 + sq / 2, y - fs * 0.02, str(k))
            c.setFillColor(MIDNIGHT); c.setFont(BODY, fs)
            for ln in lines:
                c.drawString(M + 22 + sq, y, ln); y -= lead
            y -= sgap
        for k, (title, items) in enumerate(boxes):
            bx = M + k * (bw + gap)
            c.setFillColor(MIDNIGHT); c.rect(bx + 4, by - 4, bw, bh, stroke=0, fill=1)
            c.setFillColor(HexColor("#FFFFFF")); c.setStrokeColor(MIDNIGHT); c.setLineWidth(2); c.rect(bx, by, bw, bh, stroke=1, fill=1)
            c.setFillColor(col if k == 0 else SUNSHINE); c.rect(bx, by + bh - 22, bw, 22, stroke=1, fill=1)
            c.setFillColor(MIDNIGHT); c.setFont(PIX, 8); c.drawString(bx + 10, by + bh - 15, title)
            yy = by + bh - 40
            for t in items:
                c.setFillColor(ink); c.rect(bx + 12, yy + 1, 6, 6, stroke=0, fill=1)
                c.setFillColor(MIDNIGHT); c.setFont(BODY, 12)
                for ln in wrap(t, BODY, 12, bw - 34):
                    c.drawString(bx + 26, yy, ln); yy -= 15
                yy -= 3
        if screen_line:
            c.setFillColor(PACIFIC); c.setFont(BOLD, 12); c.drawCentredString(w / 2, 42, "ON THE BIG SCREEN: " + screen_line)
    return draw


def cards(game, idx, items, label, cols=3, rows=4, size=22, title="Cut-out cards", note=None):
    pages = []
    per = cols * rows
    for start in range(0, len(items), per):
        chunk = items[start:start + per]

        def draw(c, w, h, chunk=chunk):
            top = frame(c, w, h, game, title)
            cut_note(c, w, top - 18, note or "Print, then cut along the dashed lines.")
            gx, gy, gw, gh = M, 34, w - 2 * M, top - 30 - 34
            cw, ch = gw / cols, gh / rows
            col, ink = COLORS[idx % len(COLORS)], INK[idx % len(INK)]
            for k, item in enumerate(chunk):
                r, q = divmod(k, cols)
                x, y = gx + q * cw, gy + gh - (r + 1) * ch
                c.setFillColor(col); c.rect(x + 8, y + ch - 14, cw - 16, 6, stroke=0, fill=1)
                c.setFillColor(ink); c.setFont(PIX, 6); c.drawString(x + 10, y + ch - 26, label.upper())
                text = item if isinstance(item, str) else item[0]
                fs = size
                lines = wrap(text, BOLD, fs, cw - 24)
                while (len(lines) > 3 or len(lines) * fs * 1.2 > ch - 50) and fs > 9:
                    fs -= 1; lines = wrap(text, BOLD, fs, cw - 24)
                ty = y + ch / 2 + (len(lines) - 1) * fs * 0.6 - fs * 0.35 - 4
                c.setFillColor(MIDNIGHT); c.setFont(BOLD, fs)
                for ln in lines:
                    c.drawCentredString(x + cw / 2, ty, ln); ty -= fs * 1.2
                if not isinstance(item, str) and item[1]:
                    c.setFillColor(GREY); c.setFont(BODY, 9)
                    c.drawCentredString(x + cw / 2, y + 12, item[1])
            c.setStrokeColor(LIGHT); c.setLineWidth(1); c.setDash(5, 4)
            for q in range(cols + 1): c.line(gx + q * cw, gy, gx + q * cw, gy + gh)
            for r in range(rows + 1): c.line(gx, gy + r * ch, gx + gw, gy + r * ch)
            c.setDash()
        pages.append((draw, False))
    return pages


def signs(game, idx, items, title="Room signs"):
    """items: list of (big, small). One landscape page each."""
    pages = []
    for k, (big, small) in enumerate(items):
        def draw(c, w, h, big=big, small=small, k=k):
            top = frame(c, w, h, game, title)
            col = COLORS[(idx + k) % len(COLORS)]
            c.setFillColor(col); c.setStrokeColor(MIDNIGHT); c.setLineWidth(6)
            c.rect(M + 10, 50, w - 2 * M - 20, top - 80, stroke=1, fill=0)
            fs = fit(big, PIX, 230, w - 2 * M - 80)
            c.setFillColor(MIDNIGHT); c.setFont(PIX, fs); c.drawCentredString(w / 2 + 8, 210 - 8, big)
            c.setFillColor(col); c.drawCentredString(w / 2, 210, big)
            sf = fit(small, PIX, 34, w - 2 * M - 80)
            c.setFillColor(MIDNIGHT); c.setFont(PIX, sf); c.drawCentredString(w / 2, 110, small)
        pages.append((draw, True))
    return pages


def certificates(game, idx, title, reason):
    def draw(c, w, h):
        frame(c, w, h, game, "Winner certificates")
        cut_note(c, w, h / 2 - 3, "Two per page. Cut on the dashed line.")
        col, ink = COLORS[idx % len(COLORS)], INK[idx % len(INK)]
        for half in (0, 1):
            y0 = 40 if half == 0 else h / 2 + 10
            hh = h / 2 - 60
            x0, ww = M + 6, w - 2 * M - 12
            c.setStrokeColor(MIDNIGHT); c.setLineWidth(4); c.rect(x0, y0, ww, hh, stroke=1, fill=0)
            c.setStrokeColor(col); c.setLineWidth(3); c.rect(x0 + 8, y0 + 8, ww - 16, hh - 16, stroke=1, fill=0)
            for cx_, cy_ in ((x0, y0), (x0 + ww, y0), (x0, y0 + hh), (x0 + ww, y0 + hh)):
                c.setFillColor(SUNSHINE); c.setStrokeColor(MIDNIGHT); c.setLineWidth(2); c.rect(cx_ - 9, cy_ - 9, 18, 18, stroke=1, fill=1)
            icon(c, ACTS[idx]["i"], w / 2, y0 + hh - 40, 34, ink.hexval().replace("0x", "#"))
            pixel_title(c, title, w / 2, y0 + hh - 92, 26, ww - 60)
            c.setFillColor(GREY); c.setFont(BODY, 13); c.drawCentredString(w / 2, y0 + hh - 122, "is proudly awarded to")
            c.setStrokeColor(MIDNIGHT); c.setLineWidth(1.2); c.line(w / 2 - 170, y0 + hh - 160, w / 2 + 170, y0 + hh - 160)
            c.setFillColor(MIDNIGHT); c.setFont(BOLD, 14); c.drawCentredString(w / 2, y0 + hh - 186, reason)
            c.setFont(BODY, 11); c.setFillColor(GREY)
            c.drawString(x0 + 40, y0 + 30, "Date"); c.line(x0 + 72, y0 + 28, x0 + 220, y0 + 28)
            c.drawString(x0 + ww - 270, y0 + 30, "Teacher"); c.line(x0 + ww - 222, y0 + 28, x0 + ww - 40, y0 + 28)
        c.setStrokeColor(LIGHT); c.setDash(5, 4); c.line(M, h / 2 - 15, w - M, h / 2 - 15); c.setDash()
    return [(draw, False)]


def table_sheet(game, idx, title, headers, widths, rows, intro=None, row_h=34, label="Student sheet", name=True, first_col=None):
    def draw(c, w, h):
        top = frame(c, w, h, game, label)
        y = top - 50
        pixel_title(c, title, w / 2, y, 22, w - 2 * M)
        y -= 34
        if name:
            name_line(c, M, y, 300); c.setFont(BOLD, 12); c.drawString(M + 330, y, "Date"); c.line(M + 365, y - 2, w - M, y - 2)
            y -= 28
        if intro:
            c.setFillColor(GREY); c.setFont(BODY, 12)
            for ln in wrap(intro, BODY, 12, w - 2 * M):
                c.drawString(M, y, ln); y -= 15
            y -= 6
        tw = w - 2 * M
        xs = [M]
        for f in widths: xs.append(xs[-1] + f * tw)
        hh = 24
        c.setFillColor(COLORS[idx % len(COLORS)]); c.setStrokeColor(MIDNIGHT); c.setLineWidth(1.5)
        c.rect(M, y - hh, tw, hh, stroke=1, fill=1)
        c.setFillColor(MIDNIGHT); c.setFont(PIX, 7)
        for k, t in enumerate(headers): c.drawString(xs[k] + 6, y - 15, t.upper())
        y -= hh
        n = min(rows, int((y - 40) // row_h))
        for r in range(n):
            c.setStrokeColor(MIDNIGHT); c.setLineWidth(1); c.rect(M, y - row_h, tw, row_h, stroke=1, fill=0)
            for x in xs[1:-1]: c.line(x, y, x, y - row_h)
            if first_col:
                c.setFillColor(MIDNIGHT); c.setFont(BOLD, 12); c.drawString(M + 6, y - row_h / 2 - 4, first_col(r))
            y -= row_h
    return [(draw, False)]


# ---------------------------------------------------------------- one-off sheets
def doodle_sheet(game, idx):
    def draw(c, w, h):
        top = frame(c, w, h, game, "Student sheet")
        pixel_title(c, "SPEED DOODLE", w / 2, top - 44, 22, w - 2 * M)
        name_line(c, M, top - 74, w - 2 * M)
        bw, bh = (w - 2 * M - 16) / 2, (top - 100 - 40 - 16) / 2
        for k in range(4):
            r, q = divmod(k, 2)
            x, y = M + q * (bw + 16), 40 + (1 - r) * (bh + 16)
            c.setFillColor(INK[idx % len(INK)]); c.setFont(PIX, 8); c.drawString(x, y + bh - 12, f"ROUND {k + 1}")
            c.setFillColor(MIDNIGHT); c.setFont(BODY, 10); c.drawString(x + 70, y + bh - 12, "Draw:")
            c.setStrokeColor(MIDNIGHT); c.setLineWidth(0.8); c.line(x + 100, y + bh - 14, x + bw, y + bh - 14)
            c.setLineWidth(2.5); c.rect(x, y, bw, bh - 24, stroke=1, fill=0)
    return [(draw, False)]


def book_menu(game, idx):
    def draw(c, w, h):
        top = frame(c, w, h, game, "Student sheet")
        pixel_title(c, "BOOK TASTING MENU", w / 2, top - 44, 22, w - 2 * M)
        name_line(c, M, top - 74, w - 2 * M)
        n = 5
        bh = (top - 96 - 34) / n
        for k in range(n):
            y = top - 96 - (k + 1) * bh
            c.setStrokeColor(MIDNIGHT); c.setLineWidth(1.8); c.rect(M, y + 6, w - 2 * M, bh - 10, stroke=1, fill=0)
            c.setFillColor(COLORS[(idx + k) % len(COLORS)]); c.rect(M, y + 6, 26, bh - 10, stroke=0, fill=1)
            c.saveState(); c.translate(M + 17, y + 6 + (bh - 10) / 2); c.rotate(90)
            c.setFillColor(MIDNIGHT); c.setFont(PIX, 7); c.drawCentredString(0, 0, f"TASTE {k + 1}"); c.restoreState()
            x0, yy = M + 38, y + bh - 24
            c.setFillColor(MIDNIGHT); c.setFont(BOLD, 11)
            c.drawString(x0, yy, "Title"); c.setLineWidth(0.8); c.line(x0 + 32, yy - 2, w - M - 10, yy - 2)
            yy -= 24
            c.drawString(x0, yy, "Author"); c.line(x0 + 44, yy - 2, x0 + 250, yy - 2)
            c.drawString(x0 + 262, yy, "Genre"); c.line(x0 + 300, yy - 2, w - M - 10, yy - 2)
            yy -= 26
            c.drawString(x0, yy, "My rating")
            for s in range(5): star(c, x0 + 80 + s * 22, yy + 4, 8)
            c.drawString(x0 + 210, yy, "Want seconds?"); checkbox(c, x0 + 300, yy - 1); c.drawString(x0 + 315, yy, "Yes")
            checkbox(c, x0 + 350, yy - 1); c.drawString(x0 + 365, yy, "No")
            yy -= 24
            c.drawString(x0, yy, "Tastes like"); c.line(x0 + 66, yy - 2, w - M - 10, yy - 2)
    return [(draw, False)]


def star(c, x, y, r):
    import math
    p = c.beginPath()
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        (p.moveTo if k == 0 else p.lineTo)(x + rr * math.cos(a), y + rr * math.sin(a))
    p.close(); c.setStrokeColor(MIDNIGHT); c.setLineWidth(1); c.drawPath(p, stroke=1, fill=0)


def two_truths(game, idx):
    def draw(c, w, h):
        frame(c, w, h, game, "Student sheet")
        cut_note(c, w, h / 2 - 3, "Two per page. Cut on the dashed line, then fold the bottom strip under to hide your lie!")
        for half in (0, 1):
            y0 = 30 if half == 0 else h / 2 + 8
            top = y0 + h / 2 - 74
            pixel_title(c, "TWO TRUTHS & A LIE", w / 2, top - 6, 18, w - 2 * M)
            name_line(c, M, top - 34, w - 2 * M)
            y = top - 66
            for k in range(3):
                c.setFillColor(INK[idx % len(INK)]); c.setFont(PIX, 12); c.drawString(M, y, f"{k + 1}")
                c.setStrokeColor(MIDNIGHT); c.setLineWidth(0.8)
                c.line(M + 24, y - 2, w - M, y - 2); c.line(M + 24, y - 24, w - M, y - 24)
                y -= 52
            c.setStrokeColor(LIGHT); c.setDash(2, 3); c.line(M, y + 18, w - M, y + 18); c.setDash()
            c.setFillColor(GREY); c.setFont(BODY, 9); c.drawString(M, y + 22, "fold here")
            c.setFillColor(MIDNIGHT); c.setFont(BOLD, 13); c.drawString(M, y, "Psst... my lie is number")
            for k in range(3):
                checkbox(c, M + 175 + k * 50, y - 2, 13); c.drawString(M + 192 + k * 50, y, str(k + 1))
        c.setStrokeColor(LIGHT); c.setDash(5, 4); c.line(M, h / 2 - 15, w - M, h / 2 - 15); c.setDash()
    return [(draw, False)]


def story_sheet(game, idx):
    def draw(c, w, h):
        top = frame(c, w, h, game, "Story recorder")
        pixel_title(c, "OUR ONE-WORD STORY", w / 2, top - 44, 22, w - 2 * M)
        c.setFillColor(GREY); c.setFont(BODY, 12)
        c.drawCentredString(w / 2, top - 68, "One student writes the story down as the class builds it. Read it back at the end!")
        name_line(c, M, top - 96, w - 2 * M, "Title")
        c.setStrokeColor(MIDNIGHT); c.setLineWidth(2.5); c.rect(M, top - 330, w - 2 * M, 210, stroke=1, fill=0)
        c.setFillColor(GREY); c.setFont(BODY, 10); c.drawString(M + 8, top - 136, "Draw the best part:")
        y = top - 360
        c.setLineWidth(0.8)
        while y > 44:
            c.line(M, y, w - M, y); y -= 28
    return [(draw, False)]


def statue_placards(game, idx):
    def draw(c, w, h):
        top = frame(c, w, h, game, "Museum placards")
        cut_note(c, w, top - 18, "Each statue fills one in and sets it at their feet. Cut on the dashed lines.")
        gx, gy, gw, gh = M, 34, w - 2 * M, top - 30 - 34
        cw, ch = gw / 2, gh / 2
        for k in range(4):
            r, q = divmod(k, 2)
            x, y = gx + q * cw + 14, gy + gh - (r + 1) * ch + 14
            ww, hh = cw - 28, ch - 28
            c.setFillColor(HexColor("#F3EBDD")); c.setStrokeColor(MIDNIGHT); c.setLineWidth(3); c.rect(x, y, ww, hh, stroke=1, fill=1)
            c.setStrokeColor(HexColor("#B08D57")); c.setLineWidth(1.5); c.rect(x + 6, y + 6, ww - 12, hh - 12, stroke=1, fill=0)
            c.setFillColor(MIDNIGHT); c.setFont(PIX, 9); c.drawCentredString(x + ww / 2, y + hh - 28, "RECESS MUSEUM OF ART")
            c.setFont(BODY, 8); c.setFillColor(GREY); c.drawCentredString(x + ww / 2, y + hh - 42, "PLEASE DO NOT TOUCH THE STATUES")
            yy = y + hh - 74
            for lab in ("Title", "Artist", "Year"):
                c.setFillColor(MIDNIGHT); c.setFont(BOLD, 12); c.drawString(x + 16, yy, lab)
                c.setStrokeColor(MIDNIGHT); c.setLineWidth(0.8); c.line(x + 62, yy - 2, x + ww - 16, yy - 2)
                yy -= 34
            c.setFont(BOLD, 11); c.drawString(x + 16, yy, "Made of:")
            for j, m in enumerate(("marble", "bronze", "clay")):
                checkbox(c, x + 16 + j * 74, yy - 22, 10); c.setFont(BODY, 11); c.drawString(x + 30 + j * 74, yy - 21, m)
            c.setFont(BOLD, 11)
        c.setStrokeColor(LIGHT); c.setLineWidth(1); c.setDash(5, 4)
        c.line(gx + cw, gy, gx + cw, gy + gh); c.line(gx, gy + ch, gx + gw, gy + ch); c.setDash()
    return [(draw, False)]


def scoreboard(game, idx):
    def draw(c, w, h):
        top = frame(c, w, h, game, "Team scoreboard")
        pixel_title(c, "SCOREBOARD", w / 2, top - 50, 30, w - 2 * M)
        c.setFillColor(GREY); c.setFont(BODY, 12); c.drawCentredString(w / 2, top - 76, "Tape it next to the board. One tally mark per point.")
        bw = (w - 2 * M - 20) / 2
        for k, t in enumerate(("TEAM 1", "TEAM 2")):
            x = M + k * (bw + 20)
            c.setFillColor(COLORS[(idx + k * 3) % len(COLORS)]); c.setStrokeColor(MIDNIGHT); c.setLineWidth(3)
            c.rect(x, top - 150, bw, 50, stroke=1, fill=1)
            c.setFillColor(MIDNIGHT); c.setFont(PIX, 16); c.drawCentredString(x + bw / 2, top - 132, t)
            c.setFont(BODY, 10); c.drawString(x + 8, top - 164 , "Team name:"); c.setLineWidth(0.8); c.line(x + 66, top - 166, x + bw - 8, top - 166)
            c.setLineWidth(3); c.rect(x, 50, bw, top - 230, stroke=1, fill=0)
    return [(draw, False)]


# ---------------------------------------------------------------- per-game content
SIMON = ["touch your toes", "pat your head", "hop on one foot", "rub your tummy", "flap your arms like a bird", "touch your nose",
         "spin around once", "do five jumping jacks", "freeze like a statue", "wiggle your fingers", "stand on your tiptoes",
         "make a silly face", "clap three times", "touch your knees", "march in place", "pretend to swim", "do a superhero pose",
         "shake your hands out", "touch your ears", "stomp your feet", "give a thumbs up", "hug yourself", "jump like a frog",
         "balance like a flamingo", "wave to a friend", "point to the ceiling", "sit down", "stand up", "pretend to row a boat",
         "whisper your name"]

NEEDS = {
    "Hot Potato": ["A soft ball or beanbag", "Music (or the wheel's beat)"],
    "Four Corners": ["Four corners of the room", "The 1-4 corner signs (optional)"],
    "Heads Up, 7 Up": ["Desks or tables to put heads down on"],
    "Charades": ["Prompt cards or the wheel", "A timer"],
    "Would You Rather": ["Open space to walk left and right", "A and B signs (optional)"],
    "Simon Says": ["Open space", "Command cards for Simon (optional)"],
    "Whiteboard Pictionary": ["Whiteboard and markers", "Word cards or the wheel"],
    "Speed Doodle": ["Paper or a doodle sheet", "Pencils or crayons"],
    "Human Knot": ["Groups of 6 to 10", "Open floor space"],
    "Telephone": ["A circle of chairs or carpet space", "Sentence cards (optional)"],
    "Rock Paper Scissors": ["Open space to roam"],
    "Silent Ball": ["A soft ball", "Very quiet voices"],
    "Book Tasting": ["One book per student", "Tasting menu sheets (optional)"],
    "Two Truths & a Lie": ["Planning sheets or scrap paper"],
    "Stretch & Yoga": ["Space to stretch out", "Pose cards (optional)"],
    "One-Word Story": ["A circle", "A volunteer recorder (optional)"],
    "20 Questions": ["A secret answer", "Tally sheet to count questions"],
    "Mystery Trash": ["A messy room!", "A small prize"],
    "Musical Chairs": ["Chairs, one fewer than players", "Music or clapping"],
    "Board Games & Puzzles": ["Board games, cards and puzzles"],
    "Silent Line-Up": ["Open space to line up", "A timer"],
    "Categories": ["A circle", "Answer sheets for written rounds (optional)"],
    "Sparkle": ["A list of spelling words"],
    "Who Started It?": ["A spot in the hall for the guesser"],
    "Museum Statues": ["Open space", "One or two night guards"],
}


def extras(name, idx):
    """Returns (pages, packet description list)."""
    g = name
    if g == "Hot Potato":
        return certificates(g, idx, "HOT POTATO SURVIVOR", "for keeping cool under pressure!"), ["2 winner certificates"]
    if g == "Four Corners":
        return signs(g, idx, [(str(k), f"CORNER {k}") for k in range(1, 5)], "Corner signs"), ["4 corner signs (1-4) to tape up"]
    if g == "Heads Up, 7 Up":
        return cards(g, idx, [f"#{k}" for k in range(1, 8)] + ["HEADS DOWN, THUMBS UP!"], "Heads up, 7 up", cols=2, rows=4, size=48,
                     title="Picker cards", note="Hand one to each of the seven pickers. Cut along the dashed lines."), ["7 picker cards for the seven up front"]
    if g == "Charades":
        return cards(g, idx, L["CHARADES"], "Act out..."), ["30 cut-out prompt cards"]
    if g == "Would You Rather":
        qs = [f"Would you rather {a} OR {b}?" for a, b in zip(L["WYR_A"], L["WYR_B"])]
        return (signs(g, idx, [("A", "LEFT SIDE"), ("B", "RIGHT SIDE")], "Side signs") +
                cards(g, idx, qs, "Would you rather", cols=2, rows=5, size=16)), ["A and B side-of-the-room signs", "30 question cards"]
    if g == "Simon Says":
        return cards(g, idx, ["Simon says " + s for s in SIMON], "Simon's command", size=18,
                     note="Simon reads these. Leave off \"Simon says\" sometimes to catch people!"), ["30 command cards for Simon"]
    if g == "Whiteboard Pictionary":
        return cards(g, idx, L["PICT"], "Draw this") + scoreboard(g, idx), ["30 secret word cards", "Two-team scoreboard"]
    if g == "Speed Doodle":
        return doodle_sheet(g, idx), ["Four-round doodle sheet for each student"]
    if g == "Human Knot":
        return table_sheet(g, idx, "KNOT TIMES", ["Team", "Try 1", "Try 2", "Try 3", "Best time"], [0.32, 0.17, 0.17, 0.17, 0.17], 12,
                           intro="Use the wheel's stopwatch and write each team's untangle time. Can you beat your best?", label="Time tracker", name=False), ["Team time tracker"]
    if g == "Telephone":
        n = len(L["TEL_WHO"])
        sents = [f'{L["TEL_WHO"][k]} {L["TEL_DID"][(k * 7) % n]} {L["TEL_WHERE"][(k * 11) % n]}.' for k in range(n)]
        return (cards(g, idx, sents, "Whisper this", cols=2, rows=5, size=16) +
                table_sheet(g, idx, "WHAT DID IT BECOME?", ["Round", "We started with...", "It ended up as..."], [0.12, 0.44, 0.44], 10,
                            row_h=52, label="Record sheet", name=False, first_col=lambda r: str(r + 1))), ["30 sentence cards", "Start-vs-finish record sheet"]
    if g == "Rock Paper Scissors":
        return certificates(g, idx, "RPS CHAMPION", "for winning the whole class tournament!"), ["2 champion certificates"]
    if g == "Silent Ball":
        return certificates(g, idx, "SILENT BALL MASTER", "for the quietest hands in the room!"), ["2 winner certificates"]
    if g == "Book Tasting":
        return book_menu(g, idx), ["Book tasting menu (one per student)"]
    if g == "Two Truths & a Lie":
        return two_truths(g, idx), ["Planning sheets, two per page"]
    if g == "Stretch & Yoga":
        return cards(g, idx, [(p, "Hold for 30 seconds") for p in L["YOGA"]], "Pose", size=20), ["30 pose cards for student leaders"]
    if g == "One-Word Story":
        return story_sheet(g, idx), ["Story recorder sheet"]
    if g == "20 Questions":
        return (cards(g, idx, L["TWENTY"], "The secret thing is") +
                table_sheet(g, idx, "20 QUESTIONS", ["#", "Question", "Yes", "No"], [0.07, 0.69, 0.12, 0.12], 20, row_h=27,
                            label="Question tracker", name=False, first_col=lambda r: str(r + 1))), ["30 secret answer cards", "Question tracker (1-20)"]
    if g == "Mystery Trash":
        return certificates(g, idx, "MYSTERY TRASH FINDER", "for finding the mystery trash!"), ["2 winner certificates"]
    if g == "Musical Chairs":
        return certificates(g, idx, "MUSICAL CHAIRS CHAMP", "for grabbing the very last seat!"), ["2 winner certificates"]
    if g == "Board Games & Puzzles":
        return table_sheet(g, idx, "GAME TIME SIGN-UP", ["Game or puzzle", "Players", "Cleaned up?"], [0.42, 0.36, 0.22], 14,
                           intro="Write the game, who is playing, and check the box when every piece is back in the box.", label="Sign-up sheet", name=False), ["Game sign-up and clean-up sheet"]
    if g == "Silent Line-Up":
        return cards(g, idx, ["Line up by " + s for s in L["LINEUP"]], "Silent line-up", size=18), ["30 line-up challenge cards"]
    if g == "Categories":
        return (table_sheet(g, idx, "CATEGORIES", ["Category", "Letter", "My answer"], [0.36, 0.14, 0.5], 14,
                            intro="Written round: the teacher rolls a category and letter, everyone writes an answer. Points for answers nobody else wrote!") +
                certificates(g, idx, "CATEGORY CHAMP", "for the quickest brain in the circle!")), ["Answer sheet for written rounds", "2 winner certificates"]
    if g == "Sparkle":
        return (cards(g, idx, L["SPELL"], "Spell", size=24) +
                certificates(g, idx, "SPARKLE SPELLER", "for spelling like a star!")), ["30 spelling word cards", "2 winner certificates"]
    if g == "Who Started It?":
        return certificates(g, idx, "SUPER SLEUTH", "for finding the secret leader!"), ["2 detective certificates"]
    if g == "Museum Statues":
        return (statue_placards(g, idx) +
                certificates(g, idx, "LAST STATUE STANDING", "for being the stillest statue in the museum!")), ["Museum placards for the statues", "2 winner certificates"]
    return [], []


def main():
    os.makedirs(OUT, exist_ok=True)
    allc = canvas.Canvas(os.path.join(OUT, "all-printables.pdf"), pagesize=letter)
    allc.setTitle("Indoor Recess-O-Matic: All Printables"); allc.setAuthor("Indoor Recess-O-Matic")
    manifest = {}
    for idx, act in enumerate(ACTS):
        name = act["n"]
        if name not in NEEDS: raise SystemExit(f"No printable info for {name!r}. Add it to NEEDS and extras().")
        fn = slug(name) + ".pdf"
        c = canvas.Canvas(os.path.join(OUT, fn), pagesize=letter)
        c.setTitle(f"{name}: Indoor Recess-O-Matic printables"); c.setAuthor("Indoor Recess-O-Matic")
        pages, packet = extras(name, idx)
        doc = Doc(c, allc)
        doc.page(poster(act, idx, packet))
        for draw, land in pages: doc.page(draw, land)
        c.save()
        manifest[name] = {"file": "printables/" + fn, "what": ["Rules poster"] + packet, "pages": 1 + len(pages)}
        print(f"{fn:32s} {1 + len(pages):2d} pages")
    allc.save()
    with open(os.path.join(OUT, "printables.js"), "w") as f:
        f.write("// Generated by tools/make_printables.py. Do not edit by hand.\n")
        f.write("window.PRINTABLES = " + json.dumps(manifest, indent=1) + ";\n")


if __name__ == "__main__":
    main()
