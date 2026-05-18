# ML-Ask Official — Changelog

All notable changes to the official Python rewrite of ML-Ask are documented here.
Versions live in self-contained folders: `mlask-official_0.X/`.

---

## [0.5.0] — 2026-05-17

A large milestone release that productises most of the IMPROVEMENTS.md roadmap.
The analyzer gains optional tokeniser/dependency backends, an on-disk cache,
a streaming + multiprocessing batch API, fuzzy emoteme matching, and modern
internet-Japanese dictionary entries.  A new CLI and an extraction tool ship
alongside.  The Streamlit app gets a JA/EN language toggle, a time-series view
for timestamped batches, and a mobile-friendly layout.

### Added

#### Matching quality
- **1.2 — On-disk lemma cache.** Dictionary entries are MeCab-tokenised once
  per dictionary file content (MD5-keyed) and pickled to
  `$XDG_CACHE_HOME/mlask_official/`.  Cold start of the analyzer drops from
  ~25 ms to sub-millisecond after the first run.  Override with
  ``MLAskOfficial(use_cache=False)`` or ``MLASK_CACHE_DIR``.
- **1.3 — Optional fugashi + UniDic backend.** Pass
  ``MLAskOfficial(backend="fugashi")`` to use UniDic via fugashi for finer
  verb-boundary coverage.  Requires ``pip install 'mlask-official[fugashi]'``.
  Default remains mecab-python3 + IPADIC for backward compatibility.
- **1.4 — Optional GiNZA dependency-tree CVS.** Pass
  ``use_dependency_cvs=True`` to run a third pass that flips emotion class
  via spaCy/GiNZA dependency traversal — catches long-distance negation that
  the local regex misses (``彼が悲しそうなのは本当ではない``).  Matches are
  labelled ``*depCVS``.  Requires ``pip install 'mlask-official[deps]'``.
- **1.5 — Fuzzy emoteme matching.** ``やばーーーい`` is now normalised to
  ``やばーい`` (collapse runs >2) before emoteme scanning, so stretched-vowel
  internet writing matches the dictionary form.  Toggle with
  ``fuzzy_emoteme=False``.

#### Dictionary
- **2.2 — Modern Japanese additions.** Each of the 10 classes gets a
  ``<emotion>_modern.txt`` companion file containing emoji, kaomoji,
  gyaru-go / wasei-go and katakana borrowings classified to their most
  common emotional meaning.  Examples: ``😭`` → aware, ``ガチ`` → takaburi,
  ``ムカつく`` → ikari, ``ぴえん`` → aware, ``草`` → yorokobi, ``ガクブル`` → kowa.

#### API + integration
- **3.2 — Proper CLI.** A new ``mlask`` command (entry-point) backed by
  ``typer``.  Subcommands: ``analyze``, ``batch``, ``benchmark``, ``extract``.
  All accept ``--backend mecab|fugashi``, ``--format csv|json|pipe``, and
  stdin/stdout piping (``echo "腹が立つ" | mlask analyze``).
- **3.3 — Streaming generator API.** ``MLAskOfficial.analyze_stream(iterable)``
  yields one result at a time without buffering the full corpus.
- **3.4 — Multiprocessing batch.** ``MLAskOfficial.analyze_parallel()`` spawns
  a pool of worker processes (each with its own MeCab tagger — safe under
  spawn).  ``analyze_batch()`` automatically switches to multiprocessing when
  the corpus is ≥ 50,000 sentences (override via ``parallel_threshold`` /
  ``workers`` constructor args, or ``parallel=`` keyword on the call).

#### Streamlit app
- **JA/EN language toggle** in the sidebar.  All UI strings + emotion labels
  switch between English (``Yorokobi (joy)``) and pure Japanese (``喜び``)
  on selection.  i18n table lives in ``mlask_official/i18n.py``.
- **5.3 — Time-series view.** If ≥ 70 % of the input lines are prefixed with
  an ISO-style timestamp (``2024-05-17T13:40 嬉しい!``), a per-emotion
  sentence-count time-series chart is added to the batch view, auto-resampled
  by span (1-min → 10-min → 1-h → 1-day).
- **5.5 — Mobile-responsive layout.** CSS media query at 768 px collapses
  side-by-side columns vertically; badges wrap; KPI cards stack.

#### Packaging
- **6.1 — PyPI metadata polish.** Added ``CITATION.cff`` (two-paper Citation
  File Format) and Python 3.13 to the classifier list.  ``pyproject.toml``
  gains ``Changelog`` / ``Citation`` URLs and an ``[all]`` extra.
- **6.2 — Conda recipe.**  ``conda-recipe/meta.yaml`` ready for
  conda-forge submission.

### Changed
- `EMOTION_LABELS_EN` and `EMOTION_LABELS_JA` are now exported from the package.
- `analyze_batch` now accepts `parallel=`/`workers=` keyword arguments.

### Documentation
- New top-level files: ``CITATION.cff``, ``conda-recipe/meta.yaml``.
- README updated with v0.5 features section and CLI usage.

### Notes on partial / deferred items
- **2.1 extract-expressions CLI.** Initial implementation in
  ``mlask_official/extract.py``: POS-pattern mining + co-occurrence +
  frequency filtering.  This is the productised version of the Wang & Isomura
  corpus pipeline; the manual-review TSV it emits is intended as input to the
  human curation step, not as a fully-automatic dictionary builder.
- **1.4 dependency-tree CVS** is opt-in only because GiNZA is a ~100 MB
  install.  Surface-regex CVS continues to be the default path.

---

## [0.4.0] — 2026-05-17

### Breaking changes
- **API rename `orientation` → `valence`** in `analyze()` output, `format_original()`,
  CSV column, badge label, pie title. *Why*: aligns with the original Russell
  circumplex terminology — `valence` is the canonical name; `orientation` was a
  legacy carry-over from the Perl reference. No alias is kept.
- **CSV `emotive` column simplified to binary `yes` / `no`** (previously
  `yes` / `emotive_noclass` / `no`). The analyzer's internal
  `result["emotive"]: bool` is unchanged; only the DataFrame / CSV representation
  collapses any emotive signal (emotion word OR emoteme / interjection / emoticon)
  to `yes`.

### Fixed
- **Batch tab `TypeError: Failed to fetch dynamically imported module Metric.*.js`**.
  Replaced `st.metric` cards with static HTML KPI cards rendered via
  `st.markdown(unsafe_allow_html=True)` — no Streamlit lazy component load, so the
  failure mode is structurally impossible to recur.

### Changed
- App icon and title emoji `🧠` → `❤️` (page favicon + sidebar header + main title).
- Sidebar "About" reduced to the one-sentence definition; the previous list of
  features (Nakamura, Russell, Plutchik, dual Aho-Corasick, CVS) moved to a new
  **Features** section in README.md.
- Sidebar Citation block now lists the two canonical papers:
  Ptaszynski et al. (2017, *JORS*) and Wang et al. (2024, *Applied Sciences*),
  with each shown as a separate `st.code` block.
- Single-text tab: quick-sample buttons moved from a side column to two full-width
  rows beneath the text-area; all 10 samples are now visible (previously 5).
- Removed decorative emoji from button labels (`🔍 Analyze`, `⚡ Analyze all`, etc.)
  in favour of plain text for a more academic presentation.

### Visualization
- Russell 2D circumplex: square aspect (`scaleanchor='y'`), serif title family,
  sqrt-scaled marker sizes (prevents one high-count emotion from dominating),
  axis labels include the (−1 … +1) unit hint, full English emotion names
  (was: Japanese name only — harder for international reviewers to read).
- Batch heatmap: when >20 sentences, the previously-hidden bar chart is replaced
  by an annotated emotion × sentence heatmap with a sequential `YlOrRd`
  colorscale. Stacked bar is retained for ≤20 sentences.
- All charts now expose a PNG download button at 2× scale via Plotly's
  `toImageButtonOptions`. Optional SVG export by installing `kaleido`.
- Plotly modebar pruned to image-export + reset only (no zoom/pan/lasso clutter).

### Documentation
- README: new **Representative emotion** subsection explaining the
  longest-match heuristic with a worked example.
- README: new **Features** section consolidating the dictionary, Russell model,
  Plutchik palette, dual Aho-Corasick, and CVS notes that previously crowded
  the sidebar.
- README: **About ML-Ask** is now the concise one-sentence definition.
- README: **Citation** section rewritten with the two canonical references
  + BibTeX blocks for each.

---

## [0.3.0] — 2026-05-17

### Added

#### Expanded emotion dictionaries (Nakamura + Wang & Isomura 2024)
- Merged the original Nakamura *Dictionary of Emotive Expressions* with the
  two-dictionary expansion compiled by Wang, Isomura, Ptaszynski et al. (2024)
  — Hiejima's and Murakami's emotion dictionaries, mapped to ML-Ask's
  10-category schema and supplemented with automatically extracted expressions.
- Total: **4,725 unique entries** across 10 emotion classes (up from ~50 samples
  per class in v0.1 / ~2,700 in v0.2).

  | Emotion | Entries |
  |---------|---------|
  | iya (disgust) | 1,489 |
  | yorokobi (joy) | 613 |
  | ikari (anger) | 507 |
  | suki (affection) | 494 |
  | aware (pathos) | 456 |
  | takaburi (excitement) | 378 |
  | odoroki (surprise) | 248 |
  | kowa (fear) | 209 |
  | yasu (ease) | 226 |
  | haji (shame) | 105 |

  Reference: Wang L., Isomura S., Ptaszynski M., Dybala P., Urabe Y., Rzepka R.,
  Masui F. *The Limits of Words: Expanding a Word-Based Emotion Analysis System with
  Multiple Emotion Dictionaries and the Automatic Extraction of Emotive Expressions.*
  Applied Sciences 2024, 14, 4439. https://doi.org/10.3390/app14114439

#### Dual Aho-Corasick matching (full-lemma + content-lemma)
- **Dictionary entries are now MeCab-lemmatised at build time**, normalising any
  accidentally inflected forms to their canonical base form before indexing.
- **Automaton 1 — full-lemma**: indexes all tokens; scans the fully lemmatised
  input string. Transparently handles verb inflections (`よだった → よだつ`,
  `なった → なる`, `たっている → たつ`, polite `〜ます` forms, etc.).
- **Automaton 2 — content-lemma**: strips particles (助詞) and auxiliaries (助動詞)
  from both dictionary entries and the input string before indexing. Covers
  particle-omission variants: `腹が立つ ↔ 腹立つ`, `胸がいっぱいになる ↔ 胸いっぱいになる`.
  CVS negation detection is intentionally disabled for this pass because most CVS
  patterns rely on particles that are absent in the stripped string.
- Content-lemma matches are labelled **≈** in all output to signal approximate matching.
- Startup time for full dual-automaton build: ~25 ms (measured on Apple Silicon).

#### Emotive / non-emotive distinction when no emotion word is found
- `analyze()` now **always** returns `intensifier` and `emotive` (bool), even when
  `emotion` is `None`. This allows callers and the UI to distinguish three states:

  | State | `emotion` | `emotive` | Meaning |
  |-------|-----------|-----------|---------|
  | Classified | dict | True/False | Normal emotion detection |
  | Emotive, unclassified | `None` | **True** | Emotemes/interjections found; emotion unclear |
  | Non-emotive | `None` | **False** | Sentence appears factual / neutral |

- Streamlit UI: the no-emotion result panel now shows a coloured banner:
  - 🟡 **EMOTIVE** — emotional intensity markers detected (lists them with counts)
  - ⚫ **NON-EMOTIVE** — no emotional markers or emotion words at all
- Results table `emotive` column now uses three values: `yes`, `emotive_noclass`, `no`.

### Changed
- Streamlit `render_emotion_details` now renders ≈-marked words with the label
  *(particle-stripped match)* instead of treating them as plain matches.
- Version string updated to `0.3.0` in all files.

### Known limitations
- **Kanji/kana variants** (`腹たつ` hiragana vs `腹が立つ` kanji) are not yet covered.
  Requires reading-level normalisation using MeCab's yomi field; deferred to v0.4.
- The content automaton can emit spurious near-duplicates when a dictionary entry
  contains a suffix (`嬉しいさ`) whose content form is a common word (`嬉しい`).
  Deduplication by lemma key rather than raw word is planned for v0.4.

---

## [0.2.0] — 2026-05-17

### Added

#### Plutchik's wheel of emotions — colour palette
- All 10 emotion classes are now colour-coded following the hue angles of
  Plutchik's published emotion wheel.
  Mapping: joy→yellow (#FFD700), trust/affection→yellow-green (#9ACD32),
  fear→green (#3CB371), surprise→teal-cyan (#20B2AA), pathos→royal-blue (#4169E1),
  disgust→dark-orchid (#9932CC), anger→crimson (#DC143C),
  anticipation/excitement→dark-orange (#FF8C00), shame→rose-purple (#8B0057),
  ease→green-yellow (#ADFF2F).
- Radar chart markers are now coloured individually per spoke rather than using a
  single fill colour.

#### Russell's 2D circumplex model visualisation
- New interactive scatter plot on the single-text tab (side-by-side with the radar).
- Background: four softly coloured quadrants (Active Positive, Active Negative,
  Passive Positive, Passive Negative).
- All 10 emotions plotted at empirically motivated (valence, arousal) coordinates.
- Detected emotions: filled circles, sized proportional to word count, Plutchik colour.
- Non-detected emotions: hollow ghost markers (22 % opacity).
- Representative emotion: ★ star marker.
- Hover tooltip shows exact coordinates, word count, and representative flag.
- In batch mode: aggregate Russell chart (summed word counts) alongside the
  orientation pie chart.
- `RUSSELL_COORDS` is now public API, exported from `mlask_official.__init__`.

#### Versioned folder structure
- Each release now lives in its own self-contained folder (`mlask-official_0.X/`),
  holding source code, dictionaries, Streamlit app, pyproject.toml, and README.
  A shared venv is referenced from `mlask43-simple-noregex/.venv/`.

### Fixed

#### Emoteme duplicate detection (critical bug fix)
- **Root cause**: `_find_emotem` used `w in set` (presence check), which collapsed
  any number of identical emoteme occurrences in a sentence into a single hit.
  A sentence with three `！` reported only one.
- **Fix**: replaced the set lookup with a dedicated Aho-Corasick automaton
  (`_emoteme_automaton`) built over the full emoteme list. `automaton.iter()` yields
  every match position independently, so three `！` characters produce three hits.
- **Verified**: `嬉しい！嬉しい！嬉しい！` → `intensifier: {emotemes: ['！','！','！']}` ✓

### Changed
- Streamlit sidebar: replaced broken placeholder image URL with styled HTML header.
- `run_app.sh` now passes `--server.headless true` for reliable non-interactive launch.
- `render_emotion_details` splits reported words into plain / approximate / negated
  categories with per-category labels.

---

## [0.1.0] — 2026-05-17

### Added — initial Python rewrite

#### Core engine (`mlask_official/_analyzer.py`)
- Full rewrite of ML-Ask 4.3 from Perl to Python, preserving identical semantics
  while replacing the O(n × m) nested-loop dictionary scan with Aho-Corasick.
- **`MLAskOfficial` class** — single public entry point.
- MeCab integration via `mecab-python3`; tagger created once and reused across all
  calls (eliminates the per-sentence `MeCab::Tagger->new()` overhead of the Perl version).
- **Aho-Corasick automaton** (`pyahocorasick`) built over all emotion dictionary words.
  Single O(n + k) scan replaces O(n × m) per-sentence loop.
- **Lemma-word boundary enforcement**: matches are validated against MeCab token
  boundaries, preventing substring false positives while still allowing multi-word
  phrases to match across token boundaries.
- **Contextual Valence Shifters (CVS)**: 108 syntactic negation patterns, compiled once
  at module import; reverses emotion polarity per the original ML-Ask CVS table.
- **Emoteme detection**: set-based O(1) lookup for 886 emotemes and 462 interjections.
- **Emoticon detection**: pre-compiled regex covering the full ASCII/Unicode emoticon
  character repertoire used in Japanese internet text.
- **Russell's two-dimensional model**: `VALENCE` and `ACTIVATION` dicts map each emotion
  to its P/N/A/P dimension; `_estimate_orientation` and `_estimate_activation` implement
  the original Perl majority-vote logic.
- **`format_original()`**: pipe-delimited output format compatible with ML-Ask 4.x.
- **`analyze_batch()`**: sequential batch API; warm parser and compiled automaton
  amortise fixed costs across all sentences.
- **Auto-detection of `mecabrc`** via `mecab-config --sysconfdir`, with fallbacks to
  common macOS/Linux paths.

#### Data
- Emotion dictionaries: 10 files sourced from pymlask (Nakamura's dictionary),
  full entries per class.
- Emoteme database: 886 emotemes + 462 interjections.

#### Streamlit web application (`streamlit_app.py`)
- Two-tab layout: **Single text** and **Batch analysis**.
- Single-text tab: interactive radar chart, orientation/activation badges, emotion word
  detail cards, intensifier display, raw dict output, original pipe-format output.
- Batch tab: file upload or paste input, throughput metric, orientation pie chart,
  stacked emotion bar chart (≤ 20 sentences), results table, CSV download.
- `@st.cache_resource` caches the analyzer across sessions.
- Quick sample buttons for 10 representative Japanese sentences.

#### Packaging
- `pyproject.toml` with `setuptools`, optional `[app]` and `[dev]` extras.
- `run_app.sh` launcher script.

---

## Authorship

**ML-Ask** — original system: Michal Ptaszynski, Pawel Dybala, Rafal Rzepka, Kenji Araki.  
**ML-Ask Official** Python rewrite: Michal Ptaszynski.  
**Dictionary expansion (v0.3)**: Lu Wang, Sho Isomura, Michal Ptaszynski et al.
