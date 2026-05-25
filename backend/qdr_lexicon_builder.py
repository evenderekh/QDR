#!/usr/bin/env python3
"""
Build qdr/data/qdr.lexicon.json from THB's MT lexicon.

Matching strategy:
  1. Strip niqqud from THB's `hebrew` field → lookup key
  2. Strip niqqud + disambiguation suffix (_N) from DSS lemma → lookup key
  3. 80% match rate on real Hebrew lemmas; remainder are proper nouns,
     DSS-specific terms, and damaged forms (# noise) — flagged for AI fill.

Output format (keyed by niqqud-stripped lemma):
  {
    "ברא": {
      "strongs_id": "H1254 — bara",
      "thb_def":    "To create...",
      "strongs_def": "1) to create..."
    },
    ...
  }
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT     = Path(__file__).resolve().parent.parent
THB_LEX  = ROOT.parent / 'thb' / 'backend' / 'thb.1.3.lexicon.json'
BIB_DATA = ROOT / 'data' / 'qdr.1.1.biblical.json'
NBIB_DATA = ROOT / 'data' / 'qdr.1.1.non_biblical.json'
OUT_LEX  = ROOT / 'data' / 'qdr.lexicon.json'

sys.stdout.reconfigure(encoding='utf-8')


def strip_niqqud(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def clean_lemma(raw: str) -> str:
    """Normalize a DSS lemma for lookup.
    - Remove _N disambiguation suffix
    - Take first segment of # compound
    - Strip niqqud
    - Strip whitespace
    """
    s = raw.strip()
    s = re.sub(r'_\d+$', '', s)
    s = s.split('#')[0].strip()
    return strip_niqqud(s).strip()


def has_hebrew(s: str) -> bool:
    return bool(re.search(r'[א-ת]', s))


def build():
    if not THB_LEX.exists():
        sys.exit(f'THB lexicon not found: {THB_LEX}')

    print('Loading THB lexicon...')
    raw = json.loads(THB_LEX.read_text(encoding='utf-8'))
    mt = raw['mt']

    # Build lookup: stripped_hebrew → entry
    by_hebrew: dict[str, dict] = {}
    for entry in mt.values():
        heb = entry.get('hebrew', '')
        if not heb:
            continue
        key = strip_niqqud(heb).strip()
        if not key:
            continue
        by_hebrew[key] = {
            'strongs_id':  entry.get('strongs_id', ''),
            'thb_def':     entry.get('thb_def', ''),
            'strongs_def': entry.get('strongs_def', ''),
            'bdb_def':     entry.get('bdb_def', ''),
        }

    print(f'THB MT entries indexed: {len(by_hebrew)}')

    # Collect all unique DSS lemmas
    print('Scanning DSS corpus for lemmas...')
    all_lemmas: set[str] = set()
    for path in [BIB_DATA, NBIB_DATA]:
        data = json.loads(path.read_text(encoding='utf-8'))
        for sc in data:
            for f in sc['fragments']:
                for ln in f['lines']:
                    for w in ln['words']:
                        if w[2]:
                            all_lemmas.add(w[2])

    real_lemmas = {l for l in all_lemmas if has_hebrew(l)}
    print(f'Unique lemmas total: {len(all_lemmas)}  |  with Hebrew: {len(real_lemmas)}')

    # Build output lexicon and track coverage
    lexicon: dict[str, dict] = {}
    matched: set[str] = set()
    unmatched: set[str] = set()

    for lemma in real_lemmas:
        key = clean_lemma(lemma)
        if not key or not has_hebrew(key):
            continue
        if key in by_hebrew:
            lexicon[key] = by_hebrew[key]
            matched.add(lemma)
        else:
            unmatched.add(lemma)

    # Write lexicon
    OUT_LEX.write_text(json.dumps(lexicon, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nWrote {len(lexicon)} entries → {OUT_LEX.name}')

    # Coverage report
    pct = 100 * len(matched) // len(real_lemmas) if real_lemmas else 0
    print(f'\n── Coverage Report ──────────────────────────────')
    print(f'Real Hebrew lemmas:  {len(real_lemmas):>6}')
    print(f'Matched to THB lex:  {len(matched):>6}  ({pct}%)')
    print(f'Unmatched (gap):     {len(unmatched):>6}  ({100-pct}%)')

    # Categorise unmatched
    proper    = sorted(l for l in unmatched if l and not re.search(r'[#]', l) and l[0].isupper())
    damaged   = sorted(l for l in unmatched if '#' in l)
    other     = sorted(l for l in unmatched if l not in proper and l not in damaged)

    print(f'\n  Proper nouns (unpointed, likely in MT): {len(proper)}')
    print(f'  Damaged / partial (#-noise):            {len(damaged)}')
    print(f'  DSS-specific / no match:                {len(other)}')

    report_path = OUT_LEX.with_suffix('.coverage_report.txt')
    with report_path.open('w', encoding='utf-8') as fh:
        fh.write(f'QDR Lexicon Coverage Report\n{"="*50}\n\n')
        fh.write(f'Real Hebrew lemmas:    {len(real_lemmas)}\n')
        fh.write(f'Matched:               {len(matched)} ({pct}%)\n')
        fh.write(f'Unmatched:             {len(unmatched)}\n\n')
        fh.write(f'── DSS-specific / no match ({len(other)}) ──\n')
        for l in other:
            fh.write(f'  {l}\n')
        fh.write(f'\n── Proper nouns ({len(proper)}) ──\n')
        for l in proper:
            fh.write(f'  {l}\n')
        fh.write(f'\n── Damaged (#-noise) ({len(damaged)}) ──\n')
        for l in damaged[:200]:
            fh.write(f'  {l}\n')
        if len(damaged) > 200:
            fh.write(f'  ... ({len(damaged)-200} more)\n')
    print(f'\nDetailed report → {report_path.name}')


if __name__ == '__main__':
    build()
