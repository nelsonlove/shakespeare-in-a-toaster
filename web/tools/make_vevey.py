#!/usr/bin/env python3
"""Regenerate web/public/fonts/Vevey.{ttf,woff2} from a classic Mac System file.

Vevey is a pixel-outline conversion of the 9 pt Geneva bitmap strike
(FONT resource 393) from a Macintosh System 7.5.5 suitcase. Bitmap
typeface designs are not subject to copyright in the US; the name avoids
Apple's "Geneva" trademark (Vevey is another town on Lake Geneva, in the
spirit of Kreative Korp's Urban Renewal renames).

Usage:
    uv run --with fonttools,brotli python make_vevey.py <System.bin> [outdir]

<System.bin> is a MacBinary copy of the System suitcase, e.g. extracted
with hfsutils:  hmount disk.dsk && hcopy -m ":System Folder:System" System.bin

The System file itself is Apple's and is NOT distributed with this repo;
only the generated outline font is.
"""

import struct
import sys
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

PX = 100           # font units per bitmap pixel
POINT_SIZE = 9      # the strike's point size (from the FOND association table)
FONT_RES_ID = 393   # Geneva 9 plain, per the Geneva FOND association table


def resource_fork(macbinary: bytes) -> bytes:
    dlen = struct.unpack(">I", macbinary[83:87])[0]
    rlen = struct.unpack(">I", macbinary[87:91])[0]
    off = 128 + ((dlen + 127) // 128) * 128
    return macbinary[off:off + rlen]


def find_font_resource(rsrc: bytes, res_id: int) -> bytes:
    data_off, map_off, _, map_len = struct.unpack(">IIII", rsrc[:16])
    m = rsrc[map_off:map_off + map_len]
    type_list_off, _ = struct.unpack(">HH", m[24:28])
    ntypes = struct.unpack(">H", m[type_list_off:type_list_off + 2])[0] + 1
    for i in range(ntypes):
        e = m[type_list_off + 2 + 8 * i: type_list_off + 10 + 8 * i]
        if e[:4] != b"FONT":
            continue
        count = struct.unpack(">H", e[4:6])[0] + 1
        ref_off = struct.unpack(">H", e[6:8])[0]
        for j in range(count):
            r = m[type_list_off + ref_off + 12 * j:][:12]
            rid = struct.unpack(">h", r[0:2])[0]
            if rid != res_id:
                continue
            doff = struct.unpack(">I", b"\0" + r[5:8])[0]
            size = struct.unpack(">I", rsrc[data_off + doff:data_off + doff + 4])[0]
            return rsrc[data_off + doff + 4: data_off + doff + 4 + size]
    raise SystemExit(f"FONT {res_id} not found")


def decode_strike(d: bytes) -> dict:
    (fontType, firstChar, lastChar, widMax, kernMax, nDescent,
     fRectWidth, fRectHeight, owTLoc, ascent, descent, leading,
     rowWords) = struct.unpack(">HhhhhhHHHhhhH", d[:26])
    nchars = lastChar - firstChar + 2  # includes the missing glyph
    bit_len = rowWords * 2 * fRectHeight
    strike = d[26:26 + bit_len]
    loc_start = 26 + bit_len
    loc = [struct.unpack(">H", d[loc_start + 2 * i:loc_start + 2 * i + 2])[0]
           for i in range(nchars + 1)]
    ow_start = 16 + owTLoc * 2  # owTLoc is in words from its own field

    def bit(x, y):
        row = strike[y * rowWords * 2:(y + 1) * rowWords * 2]
        return (row[x // 8] >> (7 - (x % 8))) & 1

    glyphs = {}
    for i in range(nchars):
        o, w = d[ow_start + 2 * i], d[ow_start + 2 * i + 1]
        if o == 0xFF and w == 0xFF:
            continue
        c0, c1 = loc[i], loc[i + 1]
        rows = ["".join("#" if bit(x, y) else "." for x in range(c0, c1))
                for y in range(fRectHeight)]
        code = firstChar + i if i < nchars - 1 else -1
        glyphs[code] = {"offset": o + kernMax, "width": w, "rows": rows}
    return {"ascent": ascent, "descent": descent, "glyphs": glyphs}


def build(font: dict, outdir: Path):
    asc, desc = font["ascent"], font["descent"]
    # The em of a bitmap strike equals its point size (9 px for Geneva 9),
    # NOT ascent+descent (this strike's fRect is 12 px tall to fit accents).
    # upm = 900 -> CSS font-size 9px renders 1:1, 18px renders 2x.
    upm = POINT_SIZE * PX
    src = font["glyphs"]

    def gname(code):
        if code == -1:
            return ".notdef"
        return f"uni{ord(bytes([code]).decode('mac_roman')):04X}"

    order = [".notdef"] + [gname(c) for c in sorted(src) if c >= 0]
    fb = FontBuilder(upm, isTTF=True)
    fb.setupGlyphOrder(order)

    cmap, glyf, metrics = {}, {}, {}
    for code, g in src.items():
        name = gname(code)
        pen = TTGlyphPen(None)
        for y, row in enumerate(g["rows"]):
            x = 0
            while x < len(row):
                if row[x] == "#":
                    x0 = x
                    while x < len(row) and row[x] == "#":
                        x += 1
                    left, right = (g["offset"] + x0) * PX, (g["offset"] + x) * PX
                    top, bot = (asc - y) * PX, (asc - y - 1) * PX
                    pen.moveTo((left, bot)); pen.lineTo((left, top))
                    pen.lineTo((right, top)); pen.lineTo((right, bot))
                    pen.closePath()
                else:
                    x += 1
        glyf[name] = pen.glyph()
        metrics[name] = (g["width"] * PX, g["offset"] * PX)
        if code >= 0:
            cmap[ord(bytes([code]).decode("mac_roman"))] = name

    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyf)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=asc * PX, descent=-desc * PX, lineGap=0)
    fb.setupOS2(sTypoAscender=asc * PX, sTypoDescender=-desc * PX,
                sTypoLineGap=0, usWinAscent=asc * PX, usWinDescent=desc * PX)
    fb.setupNameTable({
        "familyName": "Vevey",
        "styleName": "Regular",
        "fullName": "Vevey Regular",
        "psName": "Vevey-Regular",
        "version": "Version 1.0",
        "description": "Pixel-outline conversion of the 9 pt bitmap strike "
                       "from a Macintosh System 7.5.5 suitcase, for the "
                       "Shakespeare in a Toaster preservation project (2026).",
    })
    fb.setupPost()
    fb.save(outdir / "Vevey.ttf")
    woff = TTFont(outdir / "Vevey.ttf")
    woff.flavor = "woff2"
    woff.save(outdir / "Vevey.woff2")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    outdir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent.parent / "public" / "fonts"
    macbin = Path(sys.argv[1]).read_bytes()
    font = decode_strike(find_font_resource(resource_fork(macbin), FONT_RES_ID))
    build(font, outdir)
    print(f"wrote {outdir}/Vevey.ttf and Vevey.woff2 ({len(font['glyphs'])} glyphs)")
