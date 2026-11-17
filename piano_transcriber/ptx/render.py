"""MusicXML -> print-ready PDF / PNG.

verovio lays out the score (paper size, margins, title block, page numbers, evenly spaced
systems) as SVG pages; cairosvg turns them into vector PDF pages that pypdf merges.
"""
import io
import re
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

# page size in tenths of a millimetre (verovio's page units)
PAPER = {'a4': (2100, 2970), 'letter': (2159, 2794)}
CJK = re.compile('[⺀-鿿　-〿豈-﫿＀-￯]')
CJK_FONTS = ('Noto Serif CJK SC', 'Noto Sans CJK SC', 'WenQuanYi Zen Hei')


def ensure_music_font(name='Leipzig'):
    """Register verovio's SMuFL font with fontconfig so cairo can draw text glyphs
    (e.g. the note symbol in a tempo mark). verovio only ships it inside a CSS file."""
    import base64
    import verovio
    d = Path.home() / '.local/share/fonts'
    f = d / f'{name}.woff2'
    if f.exists():
        return
    css = (Path(verovio.__file__).parent / 'data' / f'{name}.css').read_text()
    m = re.search(r'base64,([A-Za-z0-9+/=]+)', css)
    if not m:
        return
    d.mkdir(parents=True, exist_ok=True)
    f.write_bytes(base64.b64decode(m.group(1)))
    subprocess.run(['fc-cache', '-f', str(d)], capture_output=True)


def cjk_font():
    """First installed CJK font (cairo draws nothing for glyphs its font lacks)."""
    for fam in CJK_FONTS:
        out = subprocess.run(['fc-list', f':family={fam}'], capture_output=True, text=True).stdout
        if out.strip():
            return fam
    return None


def title_block(title=None, subtitle=None, composer=None, arranger=None):
    """MEI page headers: a centred title/subtitle and right-aligned credits on page 1,
    and a centred page number on the following pages."""
    def rend(text, **attrs):
        a = ''.join(f' {k}="{v}"' for k, v in attrs.items())
        return f'<rend{a}>{escape(text)}</rend>'

    centre = []
    if title:
        centre.append(rend(title, fontsize='xx-large', fontweight='bold'))
    if subtitle:
        centre.append(rend(subtitle, fontsize='large', fontstyle='italic'))
    right = []
    if composer:
        right.append(rend(composer, fontsize='small'))
    if arranger:
        right.append(rend(arranger if arranger.lower().startswith('arr') else f'Arr. {arranger}',
                          fontsize='small'))
    first = '<pgHead func="first">'
    if centre:
        # a small blank line keeps the subtitle clear of the bold CJK title (verovio spaces
        # lines with Times metrics, which are shallower than CJK glyphs)
        spacer = '<lb/><rend fontsize="x-small">\u00a0</rend><lb/>'
        first += '<rend halign="center" valign="top">' + spacer.join(centre) + '</rend>'
    if right:
        first += '<rend halign="right" valign="bottom">' + '<lb/>'.join(right) + '</rend>'
    first += '</pgHead>'
    others = ('<pgHead func="all"><rend halign="center" valign="top">'
              '<rend fontsize="small">– <num label="page">#</num> –</rend></rend></pgHead>')
    return first + others


def _use_font_for_cjk(svg, family):
    """verovio ignores MEI @fontfam, so give every text run containing CJK an explicit font."""
    if not family:
        return svg
    return re.sub(r'<tspan([^>]*)>([^<]*)</tspan>',
                  lambda m: (f'<tspan{m.group(1)} font-family="{family}">{m.group(2)}</tspan>'
                             if CJK.search(m.group(2)) else m.group(0)),
                  svg)


def _paper_units(svg, width, height):
    """Give the outer <svg> its physical size so PDF pages are exactly the paper size
    (verovio writes pixels, which cairosvg would convert at 96 dpi)."""
    return re.sub(r'<svg width="[^"]*" height="[^"]*"',
                  f'<svg width="{width / 10:g}mm" height="{height / 10:g}mm"', svg, count=1)


def render(musicxml_path, pdf_path=None, png_prefix=None, png_pages=(1,), paper='a4',
           title=None, subtitle=None, composer=None, arranger=None, scale=40):
    """Lay out and render a MusicXML score. Returns the number of pages."""
    import verovio
    import cairosvg
    ensure_music_font()
    width, height = PAPER[paper]
    opts = {
        'pageWidth': width, 'pageHeight': height,
        'pageMarginLeft': 150, 'pageMarginRight': 150,        # 15 mm
        'pageMarginTop': 150, 'pageMarginBottom': 150,       # 15 mm all round
        'adjustPageHeight': False, 'breaks': 'auto',
        'justifyVertically': True,                            # spread systems over each page
        'header': 'encoded', 'footer': 'none',
        'scale': scale,
    }
    tk = verovio.toolkit()
    tk.setOptions(opts)
    if not tk.loadData(Path(musicxml_path).read_text(encoding='utf-8')):
        raise RuntimeError('verovio could not load ' + str(musicxml_path))
    # swap whatever header verovio built from the MusicXML credits for our own title block
    mei = re.sub(r'<pgHead\b.*?</pgHead>', '', tk.getMEI(), flags=re.S)
    m = re.search(r'<scoreDef\b[^>]*>', mei)
    mei = mei[:m.end()] + title_block(title, subtitle, composer, arranger) + mei[m.end():]
    tk = verovio.toolkit()
    tk.setOptions(opts)
    if not tk.loadData(mei):
        raise RuntimeError('verovio could not reload the score with its title block')

    family = cjk_font()
    n = tk.getPageCount()
    pdf_parts = []
    for i in range(1, n + 1):
        svg = _use_font_for_cjk(tk.renderToSVG(i), family)
        if pdf_path:
            pdf_parts.append(cairosvg.svg2pdf(bytestring=_paper_units(svg, width, height).encode()))
        svg = svg.encode()
        if png_prefix and (png_pages is None or i in png_pages):
            cairosvg.svg2png(bytestring=svg, write_to=f'{png_prefix}{i}.png',
                             output_width=1400, background_color='white')
    if pdf_path:
        from pypdf import PdfWriter, PdfReader
        w = PdfWriter()
        for b in pdf_parts:
            for pg in PdfReader(io.BytesIO(b)).pages:
                w.add_page(pg)
        meta = {'/Creator': 'piano_transcriber (verovio)'}
        if title:
            meta['/Title'] = title + (f' – {subtitle}' if subtitle else '')
        if composer:
            meta['/Author'] = composer
        if arranger:
            meta['/Subject'] = arranger if arranger.lower().startswith('arr') else f'Arr. {arranger}'
        w.add_metadata(meta)
        with open(pdf_path, 'wb') as f:
            w.write(f)
    return n
