# Qumran Digital Reader (QDR)

**Free, open, static-site reader for the Dead Sea Scrolls.**

QDR is a structured, open dataset covering the entire Qumran corpus — 266 biblical scrolls and 735 non-biblical texts — with word-level morphological analysis based on Martin Abegg's transcriptions and lexical definitions from three reference sources. The included builder turns that data into a fully static site that runs entirely in the browser. Hover any word and get the data: root, POS, full morphological parse, definition.

**Live site:** [qumran.dev](https://qumran.dev)

---

## The Corpus

| Type | Scrolls | Notes |
|------|---------|-------|
| **Biblical** | 266 | Overlap with the Hebrew Bible; presented by cave, scroll, and canonical book |
| **Non-Biblical** | 735 | 1QS, CD, 1QH, 1QM, pesharim, liturgical texts, wisdom literature |

Every word carries: lemma, Abegg morphological parsing decoded to full English fields (no abbreviations), and inline lexical definitions from up to three sources (THB → Strong's → BDB).

---

## How It Works

QDR is a **build-once, serve-forever** static site. The builder reads structured JSON data from `data/`, fills a single HTML template, and writes one `index.html` per scroll plus gathered per-book views (1,032 pages total).

```
qdr/
├── qdr_builder.py          ← the entire site builder
├── template/
│   └── qdr_template.html   ← HTML/CSS/JS shell (all inline, no external deps)
├── data/
│   ├── qdr.1.1.biblical.json     ← 266 biblical scrolls, fragment/line structure
│   ├── qdr.1.1.non_biblical.json ← 735 non-biblical scrolls
│   └── qdr.lexicon.json          ← Unified lexicon: THB / Strong's / BDB definitions
├── backend/
│   ├── qdr_extractor.py    ← Text-Fabric → JSON (requires TF + DSS corpus)
│   └── qdr_lexicon_builder.py ← THB lexicon → qdr.lexicon.json
└── public_html/            ← Builder output (committed)
    ├── static/             ← Fonts, icons, images
    ├── about/ license/ privacy/ terms/  ← Static pages
    ├── biblical/<scroll>/  ← Per-scroll pages (e.g. biblical/1Q1/)
    ├── non_biblical/<scroll>/  ← Non-biblical pages (e.g. non_biblical/CD/)
    ├── genesis/ isaiah/ ...    ← Gathered per-book views
    └── index.html          ← Copy of biblical/1Q1/index.html
```

---

## Building

**Requirements:** Python 3 (stdlib only).

```bash
# Full build — all 1,001 scrolls, 1,032 pages
python qdr/qdr_builder.py

# Single scroll — fast iteration
python qdr/qdr_builder.py --scroll 1QIsaa

# Skip wipe step (incremental, faster)
python qdr/qdr_builder.py --no-wipe
```

Output goes to `public_html/`. The root `index.html` is automatically copied from `biblical/1Q1/index.html` after each full build.

### Search Indexing (Pagefind)

After a full build, run Pagefind to generate the search index:

```bash
npx pagefind --site qdr/public_html
```

The `pagefind/` directory is committed alongside the generated pages and served statically.

---

## Data & Licensing

The **platform software** (builder, template, tooling) is © 2026 Michael Muzar, released under the **MIT License**.

The underlying text and morphology data carries its own licensing from upstream sources:

| Source | License |
|--------|---------|
| Dead Sea Scrolls — ETCBC/Naaijer (Abegg transcriptions) | CC-BY-NC 4.0 |
| Strong's Hebrew concordance — openscriptures | Public Domain |
| BDB Enhanced lexicon — unfoldingWord | Public Domain + CC-BY 4.0 |
| THB curated definitions | MIT |

Full attribution and source links: [qumran.dev/license](https://qumran.dev/license)

**Note on redistribution:** The CC-BY-NC 4.0 DSS corpus prohibits commercial redistribution. The platform MIT license applies only to the code.

---

## Issues & Contact

Found a bug, data error, or transcription question? Open an issue on this repo.

For licensing or attribution questions: support AT qumran.dev
