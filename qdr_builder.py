#!/usr/bin/env python3
"""
QDR static site builder.

Reads:
  qdr/data/qdr.1.1.biblical.json
  qdr/data/qdr.1.1.non_biblical.json
  qdr/data/qdr.1.0.english.json    (stubbed in v1; wired later)
  qdr/template/qdr_template.html

Writes:
  qdr/public_html/biblical/<scroll>/index.html
  qdr/public_html/non_biblical/<scroll>/index.html
  qdr/public_html/<book>/index.html       (e.g. /isaiah/, /genesis/)
  qdr/public_html/sitemap.xml

Word tuple in source is 6-element: [surface, surface_full, lemma, morpho, sp, ref]
Template's JS expects 3-element: [display, lemma/translit, type]
Projection: [surface_full, lemma, morpho]  (surface_full carries editorial markers
that the template's cleanHebrewText() toggles off via the damage-marks button).
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'
TEMPLATE_PATH = ROOT / 'template' / 'qdr_template.html'
LEX_PATH = DATA_DIR / 'qdr.lexicon.json'
OUT = ROOT / 'public_html'
SOURCE_VERSION = '1.1'
SITE_BASE = 'https://qumran.dev'

CANONICAL_ORDER = {
    'Gen': 1, 'Ex': 2, 'Lev': 3, 'Num': 4, 'Deut': 5,
    'Josh': 6, 'Judg': 7, 'Ruth': 8, 'Job': 9, 'Ps': 10,
    'Prov': 11, 'Eccl': 12, 'Song': 13, 'Is': 14, 'Jer': 15,
    'Lam': 16, 'Ezek': 17, 'Dan': 18, 'Hos': 19, 'Joel': 20,
    'Amos': 21, 'Obad': 22, 'Jonah': 23, 'Mic': 24, 'Nah': 25,
    'Hab': 26, 'Zeph': 27, 'Hag': 28, 'Zech': 29, 'Mal': 30,
    'Ezra': 31,
}

BOOK_DISPLAY = {
    'Gen': 'Genesis', 'Ex': 'Exodus', 'Lev': 'Leviticus', 'Num': 'Numbers',
    'Deut': 'Deuteronomy', 'Josh': 'Joshua', 'Judg': 'Judges', 'Ruth': 'Ruth',
    'Job': 'Job', 'Ps': 'Psalms', 'Prov': 'Proverbs', 'Eccl': 'Ecclesiastes',
    'Song': 'Song of Songs', 'Is': 'Isaiah', 'Jer': 'Jeremiah', 'Lam': 'Lamentations',
    'Ezek': 'Ezekiel', 'Dan': 'Daniel', 'Hos': 'Hosea', 'Joel': 'Joel',
    'Amos': 'Amos', 'Obad': 'Obadiah', 'Jonah': 'Jonah', 'Mic': 'Micah',
    'Nah': 'Nahum', 'Hab': 'Habakkuk', 'Zeph': 'Zephaniah', 'Hag': 'Haggai',
    'Zech': 'Zechariah', 'Mal': 'Malachi', 'Ezra': 'Ezra',
}

BOOK_SLUGS = {
    'Gen': 'genesis', 'Ex': 'exodus', 'Lev': 'leviticus', 'Num': 'numbers',
    'Deut': 'deuteronomy', 'Josh': 'joshua', 'Judg': 'judges', 'Ruth': 'ruth',
    'Job': 'job', 'Ps': 'psalms', 'Prov': 'proverbs', 'Eccl': 'ecclesiastes',
    'Song': 'song-of-songs', 'Is': 'isaiah', 'Jer': 'jeremiah', 'Lam': 'lamentations',
    'Ezek': 'ezekiel', 'Dan': 'daniel', 'Hos': 'hosea', 'Joel': 'joel',
    'Amos': 'amos', 'Obad': 'obadiah', 'Jonah': 'jonah', 'Mic': 'micah',
    'Nah': 'nahum', 'Hab': 'habakkuk', 'Zeph': 'zephaniah', 'Hag': 'haggai',
    'Zech': 'zechariah', 'Mal': 'malachi', 'Ezra': 'ezra',
}


def safe_id(scroll):
    return scroll.replace('/', '_')


def cave_prefix(scroll_id):
    m = re.match(r'^(\d+Q)', scroll_id)
    return m.group(1) if m else '?'


def natural_key(s):
    parts = re.findall(r'(\d+|\D+)', s)
    return [(0, int(p)) if p.isdigit() else (1, p.lower()) for p in parts]


def js_str(s):
    return (s or '').replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')


def group_by_ref(scroll, include_scroll=False):
    """Walk scroll → fragments → lines → words; emit verse blocks grouped by ref.
    For words with empty ref (non-biblical), synthesize "<scroll> <frag>:<line>".
    Word output: [surface_full, lemma, morpho] — matches template's 3-tuple contract.
    frag field: '<frag_id>:<line>' on per-scroll pages; '<scroll> <frag_id>:<line>'
    on gathered book pages (include_scroll=True). Empty for non-biblical synthesized refs."""
    out = []
    last_ref = None
    current = None
    prefix = (scroll['scroll'] + ' ') if include_scroll else ''
    for frag in scroll['fragments']:
        for ln in frag['lines']:
            for w in ln['words']:
                surface, surface_full, lemma, morpho, sp, ref = w
                has_real_ref = bool(ref)
                if not ref:
                    ref = f"{scroll['scroll']} {frag['id']}:{ln['n']}"
                if ref != last_ref:
                    frag_label = f"{prefix}{frag['id']}:{ln['n']}" if has_real_ref else ''
                    current = {'reference': ref, 'frag': frag_label, 'words': []}
                    out.append(current)
                    last_ref = ref
                current['words'].append([surface_full, lemma, morpho])
    return out


def hebrew_data_js(verses):
    """Render verses as JS object-literal entries for inline <script> embedding."""
    items = []
    for v in verses:
        words = ', '.join(
            '["{}","{}","{}"]'.format(js_str(w[0]), js_str(w[1]), js_str(w[2]))
            for w in v['words']
        )
        frag = js_str(v.get('frag', ''))
        items.append('{{ reference: "{}", frag: "{}", words: [{}] }}'.format(
            js_str(v['reference']), frag, words))
    return ',\n            '.join(items)


def fill_template(template, scroll_name, prev_link, next_link, hebrew_js, nav_current='{}'):
    return (template
            .replace('{{{SCROLL NAME}}}', scroll_name)
            .replace('{{{PREVIOUS SCROLL LINK}}}', prev_link)
            .replace('{{{NEXT SCROLL LINK}}}', next_link)
            .replace('{{{HEBREW DATA}}}', hebrew_js)
            .replace('{{{NAV CURRENT}}}', nav_current))


def render_scroll_page(scroll, kind, prev, nxt, template):
    sid = safe_id(scroll['scroll'])
    verses = group_by_ref(scroll)
    prev_link = f'../{safe_id(prev["scroll"])}/' if prev else '#'
    next_link = f'../{safe_id(nxt["scroll"])}/' if nxt else '#'
    cave = cave_prefix(scroll['scroll'])
    nav_current = json.dumps({
        'type': 'biblical' if kind == 'biblical' else 'non_biblical',
        'mode': 'cave',
        'cave': cave,
        'scroll': scroll['scroll'],
        'url': f'/{kind}/{sid}/',
    })
    html = fill_template(
        template, scroll['scroll'], prev_link, next_link, hebrew_data_js(verses), nav_current
    )
    out_dir = OUT / kind / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'index.html').write_text(html, encoding='utf-8')
    return f'/{kind}/{sid}/'


def verse_sort_key(v):
    m = re.match(r'^[A-Za-z]+\s+(\d+):(\d+)', v['reference'])
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (9999, 9999)


def collect_book_data(bib_scrolls):
    """Return {book_code: [(scroll_name, [verses_in_that_book])]}."""
    by_book = {}
    for sc in bib_scrolls:
        verses = group_by_ref(sc, include_scroll=True)
        scroll_books = {}
        for v in verses:
            m = re.match(r'^([A-Za-z]+)\s', v['reference'])
            if m:
                scroll_books.setdefault(m.group(1), []).append(v)
        for book, vs in scroll_books.items():
            by_book.setdefault(book, []).append((sc['scroll'], vs))
    return by_book


def render_book_page(book, scrolls_in_book, template):
    """Render gathered book page: scroll-by-scroll, each scroll's verses in canonical order,
    separated by header markers (verse entries with empty words array)."""
    scrolls_sorted = sorted(scrolls_in_book, key=lambda x: natural_key(x[0]))
    combined = []
    for scroll_name, verses in scrolls_sorted:
        combined.append({'reference': f'— {scroll_name} —', 'words': []})
        combined.extend(sorted(verses, key=verse_sort_key))

    slug = BOOK_SLUGS.get(book, book.lower())
    display = BOOK_DISPLAY.get(book, book)
    nav_current = json.dumps({
        'type': 'biblical',
        'mode': 'book',
        'book': display,
        'url': f'/{slug}/',
    })
    out_dir = OUT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    html = fill_template(template, display, '#', '#', hebrew_data_js(combined), nav_current)
    (out_dir / 'index.html').write_text(html, encoding='utf-8')
    return f'/{slug}/'


def build_nav_data(bib_sorted, nbib_sorted, book_keys_sorted):
    bib_caves = {}
    for sc in bib_sorted:
        c = cave_prefix(sc['scroll'])
        bib_caves.setdefault(c, []).append({'id': sc['scroll'], 'url': f'/biblical/{safe_id(sc["scroll"])}/'})
    nbib_caves = {}
    for sc in nbib_sorted:
        c = cave_prefix(sc['scroll'])
        nbib_caves.setdefault(c, []).append({'id': sc['scroll'], 'url': f'/non_biblical/{safe_id(sc["scroll"])}/'})
    cave_sort = lambda c: natural_key(c)
    books = [
        {'name': BOOK_DISPLAY[b], 'url': f'/{BOOK_SLUGS[b]}/'}
        for b in book_keys_sorted if b in BOOK_DISPLAY
    ]
    return {
        'biblical': {
            'caves': {k: bib_caves[k] for k in sorted(bib_caves, key=cave_sort)},
            'books': books,
        },
        'non_biblical': {
            'caves': {k: nbib_caves[k] for k in sorted(nbib_caves, key=cave_sort)},
        },
    }


def write_nav_js(nav_data):
    static_dir = OUT / 'static'
    static_dir.mkdir(parents=True, exist_ok=True)
    js = 'const QDR_NAV = ' + json.dumps(nav_data, ensure_ascii=False) + ';\n'
    (static_dir / 'nav.js').write_text(js, encoding='utf-8')


def write_lex_js():
    static_dir = OUT / 'static'
    static_dir.mkdir(parents=True, exist_ok=True)
    lex = json.loads(LEX_PATH.read_text(encoding='utf-8')) if LEX_PATH.exists() else {}
    js = 'const QDR_LEX = ' + json.dumps(lex, ensure_ascii=False) + ';\n'
    (static_dir / 'lex.js').write_text(js, encoding='utf-8')


def write_sitemap(paths):
    urls = '\n'.join(f'  <url><loc>{SITE_BASE}{p}</loc></url>' for p in sorted(paths))
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{urls}\n'
        '</urlset>\n'
    )
    (OUT / 'sitemap.xml').write_text(xml, encoding='utf-8')


def wipe_output():
    """Remove generated dirs/files but preserve static/ and any hand-written landing pages."""
    if not OUT.exists():
        return
    preserve = {'static', 'index.html', 'about', 'privacy', 'terms', 'license', 'pagefind'}
    for item in OUT.iterdir():
        if item.name in preserve:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def strip_niqqud(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')


def clean_for_search(text):
    return re.sub(r'[\[\]#?ε]', '', strip_niqqud(text))


def build_search_pages(temp_dir, bib_sorted, nbib_sorted):
    """Write niqqud-stripped HTML pages to temp_dir for Pagefind.
    Hebrew text is placed directly in the DOM (not in JS arrays) so Pagefind
    can index it. data-pagefind-meta sets the canonical URL for each result."""
    tmp = Path(temp_dir)

    def write_page(scroll, kind):
        sid = safe_id(scroll['scroll'])
        canonical = f'/{kind}/{sid}/'
        verses = group_by_ref(scroll)
        parts = [
            '<!DOCTYPE html><html><head><meta charset="UTF-8">',
            f'<title>{scroll["scroll"]}</title></head><body>',
            f'<article data-pagefind-body data-pagefind-meta="url:{canonical}">',
            f'<h1>{scroll["scroll"]}</h1>',
        ]
        for v in verses:
            if not v['words']:
                continue
            parts.append(f'<h3>{v["reference"]}</h3>')
            words = ' '.join(
                clean_for_search(w[0]) for w in v['words'] if w[0] and w[0].strip()
            )
            if words.strip():
                parts.append(f'<p dir="rtl">{words}</p>')
        parts.append('</article></body></html>')
        out_dir = tmp / kind / sid
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'index.html').write_text('\n'.join(parts), encoding='utf-8')

    for sc in bib_sorted:
        write_page(sc, 'biblical')
    for sc in nbib_sorted:
        write_page(sc, 'non_biblical')


def run_pagefind(temp_dir):
    """Run npx pagefind against temp_dir and copy output to public_html/pagefind/."""
    cmd = f'npx --yes pagefind --site "{temp_dir}"'
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        print(f'pagefind stderr: {result.stderr[:500]}')
    pf_src = Path(temp_dir) / 'pagefind'
    pf_dst = OUT / 'pagefind'
    if pf_src.exists():
        if pf_dst.exists():
            shutil.rmtree(pf_dst)
        shutil.copytree(pf_src, pf_dst)
        print('pagefind index written to public_html/pagefind/')
    else:
        print('WARNING: pagefind output not found — run: npx pagefind --site qdr/public_html')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scroll', help='build only this scroll (fast iteration)')
    ap.add_argument('--no-wipe', action='store_true', help='skip the wipe-and-rebuild step')
    ap.add_argument('--no-search', action='store_true', help='skip Pagefind search index rebuild')
    args = ap.parse_args()

    t0 = time.time()
    if not TEMPLATE_PATH.exists():
        sys.exit(f'template not found: {TEMPLATE_PATH}')
    template = TEMPLATE_PATH.read_text(encoding='utf-8')

    bib = load(DATA_DIR / f'qdr.{SOURCE_VERSION}.biblical.json')
    nbib = load(DATA_DIR / f'qdr.{SOURCE_VERSION}.non_biblical.json')

    bib_sorted = sorted(bib, key=lambda s: natural_key(s['scroll']))
    nbib_sorted = sorted(nbib, key=lambda s: natural_key(s['scroll']))

    if args.scroll:
        target = next((s for s in bib_sorted + nbib_sorted if s['scroll'] == args.scroll), None)
        if not target:
            sys.exit(f'scroll not found: {args.scroll}')
        kind = 'biblical' if target in bib_sorted else 'non_biblical'
        scrolls = bib_sorted if kind == 'biblical' else nbib_sorted
        i = scrolls.index(target)
        prev = scrolls[i - 1] if i > 0 else None
        nxt = scrolls[i + 1] if i < len(scrolls) - 1 else None
        path = render_scroll_page(target, kind, prev, nxt, template)
        print(f'wrote {path} in {time.time()-t0:.1f}s')
        return

    if not args.no_wipe:
        wipe_output()
    OUT.mkdir(parents=True, exist_ok=True)

    written = []

    print(f'rendering {len(bib_sorted)} biblical scrolls...')
    for i, sc in enumerate(bib_sorted):
        prev = bib_sorted[i - 1] if i > 0 else None
        nxt = bib_sorted[i + 1] if i < len(bib_sorted) - 1 else None
        written.append(render_scroll_page(sc, 'biblical', prev, nxt, template))

    print(f'rendering {len(nbib_sorted)} non-biblical scrolls...')
    for i, sc in enumerate(nbib_sorted):
        prev = nbib_sorted[i - 1] if i > 0 else None
        nxt = nbib_sorted[i + 1] if i < len(nbib_sorted) - 1 else None
        written.append(render_scroll_page(sc, 'non_biblical', prev, nxt, template))

    print('collecting biblical book gathered views...')
    by_book = collect_book_data(bib_sorted)
    book_keys_sorted = sorted(by_book.keys(), key=lambda b: CANONICAL_ORDER.get(b, 9999))
    for book in book_keys_sorted:
        if book not in BOOK_DISPLAY:
            continue
        written.append(render_book_page(book, by_book[book], template))

    print('writing nav.js + lex.js...')
    nav_data = build_nav_data(bib_sorted, nbib_sorted, book_keys_sorted)
    write_nav_js(nav_data)
    write_lex_js()

    write_sitemap(written)

    # Re-render 1Q1 for the root page with absolute next link.
    # A direct copy of biblical/1Q1/index.html would have a relative next link
    # (../1Q2/) that resolves correctly from /biblical/1Q1/ but breaks at /.
    first = bib_sorted[0]
    second = bib_sorted[1] if len(bib_sorted) > 1 else None
    root_next = f'/biblical/{safe_id(second["scroll"])}/' if second else '#'
    root_nav = json.dumps({
        'type': 'biblical', 'mode': 'cave', 'cave': cave_prefix(first['scroll']),
        'scroll': first['scroll'], 'url': f'/biblical/{safe_id(first["scroll"])}/',
    })
    root_html = fill_template(
        template, first['scroll'], '#', root_next,
        hebrew_data_js(group_by_ref(first)), root_nav,
    )
    (OUT / 'index.html').write_text(root_html, encoding='utf-8')
    print('wrote root index.html (1Q1, absolute nav links)')

    if not args.no_search:
        import tempfile
        print('building search index...')
        with tempfile.TemporaryDirectory() as tmp:
            build_search_pages(tmp, bib_sorted, nbib_sorted)
            run_pagefind(tmp)

    print(f'wrote {len(written)} pages + sitemap.xml in {time.time()-t0:.1f}s')
    print(f'  biblical scrolls: {len(bib_sorted)}')
    print(f'  non-biblical scrolls: {len(nbib_sorted)}')
    print(f'  book pages: {sum(1 for b in book_keys_sorted if b in BOOK_DISPLAY)}')
    skipped = [b for b in book_keys_sorted if b not in BOOK_DISPLAY]
    if skipped:
        print(f'  skipped non-canonical book codes: {skipped}')


if __name__ == '__main__':
    main()
