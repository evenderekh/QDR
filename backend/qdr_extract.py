#!/usr/bin/env python3
"""
QDR data extractor — pulls DSS from Text-Fabric (ETCBC/dss v1.9) and emits
QDR's source JSON preserving scroll → fragment → line → word structure.

Output:
  qdr/data/qdr.1.1.biblical.json
  qdr/data/qdr.1.1.non_biblical.json

Word tuple shape: [surface, surface_full, lemma, morpho, sp, ref]
  surface       glyph     (Hebrew, clean)
  surface_full  full      (Hebrew with editorial markers: [ ] # ? etc.)
  lemma         lex       (Hebrew with vowels)
  morpho        morpho    (compact code, e.g. "vqw3ms", "ncmsc", "Pp")
  sp            sp        (coarse speech-part: ptcl|subs|verb|suff|pron|adjv|numr|unknown)
  ref           "Book Chapter:Verse" for biblical scrolls; empty for non-biblical
"""

import json
import os
import sys
import time
from pathlib import Path

from tf.fabric import Fabric

TF_DIR = os.path.expanduser('~/text-fabric-data/github/ETCBC/dss/tf/1.9')
OUT_DIR = Path(__file__).resolve().parent.parent / 'data'
VERSION = '1.1'

FEATURES = 'otype scroll biblical fragment line book chapter verse glyph full lex morpho sp'


def main():
    t0 = time.time()
    print(f'Loading TF from {TF_DIR}')
    TF = Fabric(locations=TF_DIR, modules=[''], silent='terse')
    api = TF.load(FEATURES, silent='terse')
    if api is None:
        sys.exit('TF load failed')
    F = api.F
    L = api.L
    print(f'  loaded in {time.time()-t0:.1f}s')

    biblical_out = []
    non_biblical_out = []
    word_count_b = 0
    word_count_nb = 0

    scrolls = list(F.otype.s('scroll'))
    print(f'walking {len(scrolls)} scrolls...')

    for i, sc in enumerate(scrolls):
        name = F.scroll.v(sc) or f'scroll_{sc}'
        is_biblical = bool(F.biblical.v(sc))

        fragments_out = []
        for frag in L.d(sc, otype='fragment'):
            frag_id = F.fragment.v(frag) or ''
            lines_out = []
            for ln in L.d(frag, otype='line'):
                line_n = F.line.v(ln) or ''
                words_out = []
                for w in L.d(ln, otype='word'):
                    surface = F.glyph.v(w) or ''
                    surface_full = F.full.v(w) or ''
                    lemma = F.lex.v(w) or ''
                    morpho = F.morpho.v(w) or ''
                    sp = F.sp.v(w) or ''
                    book = F.book.v(w)
                    chap = F.chapter.v(w)
                    vers = F.verse.v(w)
                    if book and chap and vers:
                        ref = f'{book} {chap}:{vers}'
                    else:
                        ref = ''
                    words_out.append([surface, surface_full, lemma, morpho, sp, ref])
                if words_out:
                    lines_out.append({'n': line_n, 'words': words_out})
            if lines_out:
                fragments_out.append({'id': frag_id, 'lines': lines_out})

        scroll_obj = {'scroll': name, 'fragments': fragments_out}
        if is_biblical:
            biblical_out.append(scroll_obj)
            word_count_b += sum(len(ln['words']) for fr in fragments_out for ln in fr['lines'])
        else:
            non_biblical_out.append(scroll_obj)
            word_count_nb += sum(len(ln['words']) for fr in fragments_out for ln in fr['lines'])

        if (i + 1) % 100 == 0:
            print(f'  {i+1}/{len(scrolls)}')

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bib_path = OUT_DIR / f'qdr.{VERSION}.biblical.json'
    nb_path = OUT_DIR / f'qdr.{VERSION}.non_biblical.json'

    print(f'writing {bib_path}  ({len(biblical_out)} scrolls, {word_count_b} words)')
    with open(bib_path, 'w', encoding='utf-8') as f:
        json.dump(biblical_out, f, ensure_ascii=False, separators=(',', ':'))

    print(f'writing {nb_path}  ({len(non_biblical_out)} scrolls, {word_count_nb} words)')
    with open(nb_path, 'w', encoding='utf-8') as f:
        json.dump(non_biblical_out, f, ensure_ascii=False, separators=(',', ':'))

    print(f'done in {time.time()-t0:.1f}s')


if __name__ == '__main__':
    main()
