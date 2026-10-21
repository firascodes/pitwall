"""Build the Pitwall logo SVGs. Run: uv run --with fonttools python brand/build.py TitilliumWeb-Black.ttf"""

import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

OUT = Path(__file__).parent
RED, WHITE, SHADE = "#E10600", "#FFFFFF", "#FFD0CB"


def word_path(font_file: str, word: str, tracking: float = -20) -> tuple[str, float]:
    """The word as one SVG path in 1/1000 em units, baseline at y=0."""
    font = TTFont(font_file)
    scale = 1000 / font["head"].unitsPerEm
    cmap, glyphs, hmtx = font.getBestCmap(), font.getGlyphSet(), font["hmtx"]
    x, parts = 0.0, []
    for ch in word:
        name = cmap[ord(ch)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, 0)))
        parts.append(pen.getCommands())
        x += hmtx[name][0] * scale + tracking
    return " ".join(parts), x - tracking


def bars(x: int, specs: list[tuple[float, int, str, str]]) -> str:
    return "".join(
        f'<rect x="{x}" y="{y}" height="3" rx="1.5" width="{w}" fill="{WHITE}">'
        f'<animate attributeName="width" values="{vals}" dur="{dur}" repeatCount="indefinite"/>'
        "</rect>"
        for y, w, vals, dur in specs
    )


def stool(cx: int, bob: bool) -> str:
    anim = (
        '<animateTransform attributeName="transform" type="translate" '
        'values="0 0;0 -2.5;0 0" dur="1.8s" repeatCount="indefinite"/>'
        if bob
        else ""
    )
    return (
        f"<g>{anim}"
        f'<rect x="{cx - 15}" y="84" width="30" height="30" rx="11" fill="{WHITE}" '
        f'stroke="{RED}" stroke-width="4"/>'
        f'<rect x="{cx - 9}" y="90" width="18" height="17" rx="7" fill="{SHADE}"/>'
        f'<rect x="{cx - 3}" y="122" width="6" height="22" fill="{WHITE}"/>'
        f'<rect x="{cx - 15}" y="143" width="30" height="6" rx="3" fill="{WHITE}"/>'
        f'<rect x="{cx - 19}" y="113" width="38" height="9" rx="4.5" fill="{WHITE}" '
        f'stroke="{RED}" stroke-width="3"/></g>'
    )


def mark(checkered_canopy: bool = False) -> str:
    """The reversed mark (white pit wall for a red ground), viewBox 0 -8 200 164."""
    canopy_checks = (
        '<rect x="8" y="16" width="184" height="22" rx="11" fill="url(#canopy)" mask="url(#fade)"/>'
        if checkered_canopy
        else ""
    )
    screens = "".join(
        f'<rect x="{x}" y="44" width="38" height="30" rx="8" fill="{WHITE}"/>'
        f'<rect x="{x + 4}" y="48" width="30" height="22" rx="5" fill="{RED}"/>'
        for x in (39, 81, 123)
    )
    return f"""
<path d="M149 -3 Q145 2 149 7 M168 -3 Q172 2 168 7" fill="none" stroke="{WHITE}" stroke-width="2.6"
 stroke-linecap="round"><animate attributeName="opacity" values="0;1;0" dur="1.6s"
 repeatCount="indefinite"/></path>
<rect x="156" y="2" width="5" height="16" rx="2.5" fill="{WHITE}"/>
<circle cx="158.5" cy="2" r="5" fill="{WHITE}"/>
<circle cx="158.5" cy="2" r="2.2" fill="{RED}"><animate attributeName="opacity" values="1;.1;1"
 dur="1.2s" repeatCount="indefinite"/></circle>
<rect x="8" y="16" width="184" height="22" rx="11" fill="{WHITE}"/>
<rect x="22" y="21" width="56" height="4" rx="2" fill="{RED}" opacity=".5"/>{canopy_checks}
<rect x="24" y="34" width="9" height="116" rx="4.5" fill="{WHITE}"/>
<rect x="167" y="34" width="9" height="116" rx="4.5" fill="{WHITE}"/>{screens}
{bars(47, [(52, 18, "6;20;12;6", "2.2s"), (57.5, 12, "14;6;20;14", "1.8s"),
           (63, 20, "20;10;16;20", "2.6s")])}
<polyline points="89,64 94,60 98,62 102,55 106,58 111,53" fill="none" stroke="{WHITE}"
 stroke-width="3" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="30"
 stroke-dashoffset="30"><animate attributeName="stroke-dashoffset" values="30;0;0;30" dur="2.4s"
 repeatCount="indefinite"/></polyline>
{bars(131, [(52, 12, "10;20;6;10", "2s"), (57.5, 20, "20;12;18;20", "2.4s"),
            (63, 8, "8;16;10;8", "1.6s")])}
<rect x="55" y="72" width="6" height="8" fill="{WHITE}"/>
<rect x="97" y="72" width="6" height="8" fill="{WHITE}"/>
<rect x="139" y="72" width="6" height="8" fill="{WHITE}"/>
<rect x="14" y="78" width="172" height="13" rx="6.5" fill="{WHITE}"/>
<rect x="24" y="86" width="152" height="3" rx="1.5" fill="{SHADE}"/>
<rect x="4" y="149" width="192" height="6" rx="3" fill="{WHITE}"/>
{stool(58, False)}{stool(100, True)}{stool(142, False)}"""


CANOPY_DEFS = f"""
<pattern id="canopy" x="8" y="16" width="11" height="11" patternUnits="userSpaceOnUse">
 <rect width="5.5" height="5.5" fill="{RED}"/><rect x="5.5" y="5.5" width="5.5" height="5.5"
 fill="{RED}"/></pattern>
<linearGradient id="fadeR" x1="0" x2="1"><stop offset=".42" stop-color="#fff" stop-opacity="0"/>
 <stop offset=".95" stop-color="#fff"/></linearGradient>
<mask id="fade" maskUnits="userSpaceOnUse" x="0" y="0" width="200" height="60">
 <rect x="8" y="16" width="184" height="22" fill="url(#fadeR)"/></mask>"""


def lockup(word: str, width: float) -> str:
    """Stacked lockup E: mark over PITWALL; the last letters turn into a checkered flag."""
    w, h, word_w = 480, 330, 360
    s = word_w / width
    x0, base = (w - word_w) / 2 - 8, 282
    word_tf = f"translate({x0:.1f} {base}) skewX(-14) scale({s:.5f})"
    c = 5 / s  # 5 px checks, in font units because the pattern lives in the path's space
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"
 role="img" aria-label="Pitwall">
<defs>
<pattern id="flag" width="{c * 2:.1f}" height="{c * 2:.1f}" patternUnits="userSpaceOnUse">
 <rect width="{c:.1f}" height="{c:.1f}" fill="{WHITE}"/>
 <rect x="{c:.1f}" y="{c:.1f}" width="{c:.1f}" height="{c:.1f}" fill="{WHITE}"/>
</pattern>
<linearGradient id="solid" x1="0" x2="1"><stop offset=".77" stop-color="#fff"/>
 <stop offset=".93" stop-color="#fff" stop-opacity="0"/></linearGradient>
<mask id="wordfade" maskUnits="userSpaceOnUse" x="0" y="0" width="{w}" height="{h}">
 <rect x="{x0:.1f}" y="200" width="{word_w + 20}" height="100" fill="url(#solid)"/></mask>
</defs>
<rect width="{w}" height="{h}" rx="44" fill="{RED}"/>
<g transform="translate({(w - 190) / 2} 34) scale(.95)">{mark()}</g>
<path transform="{word_tf}" fill="url(#flag)" d="{word}"/>
<g mask="url(#wordfade)"><path transform="{word_tf}" fill="{WHITE}" d="{word}"/></g>
</svg>
"""


def square(size: int, checkered_canopy: bool, round_: bool) -> str:
    """App icon or bot avatar: the mark centred on red."""
    inner = size * 0.68
    s = inner / 200
    ground = (
        f'<circle cx="{size / 2}" cy="{size / 2}" r="{size / 2}" fill="{RED}"/>'
        if round_
        else f'<rect width="{size}" height="{size}" rx="{size * 0.22:.0f}" fill="{RED}"/>'
    )
    defs = f"<defs>{CANOPY_DEFS}</defs>" if checkered_canopy else ""
    y = (size - 164 * s) / 2 + 6 * s
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}"
 height="{size}" role="img" aria-label="Pitwall">{defs}{ground}
<g transform="translate({(size - inner) / 2:.1f} {y:.1f}) scale({s:.4f})">{mark(checkered_canopy)}</g>
</svg>
"""


if __name__ == "__main__":
    word, width = word_path(sys.argv[1], "PITWALL")
    (OUT / "pitwall-logo.svg").write_text(lockup(word, width))
    (OUT / "pitwall-icon.svg").write_text(square(512, checkered_canopy=False, round_=False))
    (OUT / "telegram-avatar.svg").write_text(square(640, checkered_canopy=True, round_=True))
    print("wrote", ", ".join(p.name for p in sorted(OUT.glob("*.svg"))))
