"""MusicXML -> SVG pages (verovio) -> PDF / PNG (cairosvg)."""
from pathlib import Path


def ensure_music_font(name='Leipzig'):
    """Register verovio's SMuFL font with fontconfig so cairo can draw text glyphs
    (e.g. the note symbol in a tempo mark). verovio only ships it inside a CSS file."""
    import base64, re, subprocess, verovio
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


def render(musicxml_path, pdf_path=None, png_prefix=None, png_pages=(1,), scale=40):
    import verovio, cairosvg
    ensure_music_font()
    tk = verovio.toolkit()
    tk.setOptions({'pageWidth': 2100, 'pageHeight': 2970, 'scale': scale,
                   'adjustPageHeight': False, 'footer': 'none', 'breaks': 'auto'})
    if not tk.loadData(Path(musicxml_path).read_text(encoding='utf-8')):
        raise RuntimeError('verovio could not load ' + str(musicxml_path))
    n = tk.getPageCount()
    pdf_parts = []
    for i in range(1, n + 1):
        svg = tk.renderToSVG(i).encode()
        if pdf_path:
            pdf_parts.append(cairosvg.svg2pdf(bytestring=svg))
        if png_prefix and (png_pages is None or i in png_pages):
            cairosvg.svg2png(bytestring=svg, write_to=f'{png_prefix}{i}.png',
                             output_width=1400, background_color='white')
    if pdf_path:
        from pypdf import PdfWriter, PdfReader
        import io
        w = PdfWriter()
        for b in pdf_parts:
            for pg in PdfReader(io.BytesIO(b)).pages:
                w.add_page(pg)
        with open(pdf_path, 'wb') as f:
            w.write(f)
    return n
