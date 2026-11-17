from ptx.render import title_block, _use_font_for_cjk, _paper_units, PAPER


def test_title_block_contents_and_escaping():
    head = title_block('日落计数器', 'Sunset Counter', 'A & B', '声不可测')
    assert '<pgHead func="first">' in head and '<pgHead func="all">' in head
    assert '日落计数器' in head and 'Sunset Counter' in head
    assert 'A &amp; B' in head                      # XML-escaped
    assert 'Arr. 声不可测' in head                   # "Arr." added once
    assert 'Arr. arr.' not in title_block(arranger='arr. X')
    assert '<num label="page">' in head            # page numbers on later pages


def test_cjk_runs_get_a_cjk_font_only():
    svg = '<text><tspan class="text">日落 Sunset</tspan><tspan class="text">= 200</tspan></text>'
    out = _use_font_for_cjk(svg, 'Noto Serif CJK SC')
    assert out.count('font-family="Noto Serif CJK SC"') == 1
    assert '<tspan class="text">= 200</tspan>' in out


def test_pdf_page_is_physical_paper_size():
    w, h = PAPER['a4']
    out = _paper_units('<svg width="840px" height="1188px" version="1.1"><svg viewBox="0 0 1 1"></svg></svg>', w, h)
    assert out.startswith('<svg width="210mm" height="297mm"')
