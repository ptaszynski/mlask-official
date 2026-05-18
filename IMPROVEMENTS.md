# ML-Ask Official — Future Improvements

Ideas for the next development cycles, grouped by theme and roughly ordered by
implementation priority within each group. Each item includes a short rationale
explaining *why* it matters, not just *what* it would do.

---

## 1. Matching quality

### 1.1 Reading-level (yomi) normalisation [HIGH PRIORITY]
**Problem**: kanji/kana variants of the same word (`腹が立つ` vs `腹たつ`) are not
matched. MeCab's IPADIC dictionary provides a reading (yomi) field in katakana for
every token.  
**Solution**: build a third automaton keyed on the hiragana reading of each dictionary
entry. Scan the input's reading string (obtained from MeCab yomi output, converted to
hiragana). Mark yomi matches with `≋` (double tilde) to distinguish from ≈ content
matches.  
**Caveat**: reading-based matching may collide across homophonous kanji with different
meanings. Apply it only to tokens whose surface and reading differ (kana-already-written
entries have equal surface and reading, so no gain and no risk).

### 1.2 Lemma cache on disk
**Problem**: at startup the analyzer runs MeCab on ~4,700 dictionary entries to build
full-lemma and content-lemma keys. At ~25 ms total this is already fast, but it will
grow with dictionary size.  
**Solution**: on first run, serialise the `(raw_word, full_lemma, content_lemma)` table
to a `.msgpack` or `.pkl` file beside the dictionary text files. Invalidate by comparing
the dictionary file's mtime and MD5 checksum. Subsequent cold starts skip MeCab
pre-processing entirely.  
**Expected gain**: sub-millisecond dictionary build for cached runs.

### 1.3 N-best MeCab parsing for ambiguous tokens
**Problem**: certain words are tokenised differently depending on context. `腹がたった`
is parsed as `腹 が たった(adv)` rather than `腹 が たっ(verb) た(aux)` by IPADIC,
causing a miss. MeCab supports N-best output (`-N 5`).  
**Solution**: for input sentences that produce zero emotion matches, re-analyse with
N=5 and union the results. This doubles latency for the zero-match case but has no
effect on the (more common) positive-match case.  
**Alternative**: switch the underlying dictionary from IPADIC to **UniDic** (via
`fugashi`), which has better coverage of verb conjugation boundaries.

### 1.4 Longer-context CVS (dependency-tree based)
**Problem**: the current CVS implementation is a suffix regex applied to the lemma
string directly after a match. This is fragile for long-distance negation and complex
sentence structures: `彼が悲しそうなのは本当ではない` (he does not appear sad) may
not trigger CVS depending on tokenisation.  
**Solution**: parse the sentence with CaboCha or GiNZA (both wrap MeCab) to get a
dependency tree. Locate the governing negation of each emotion word by tree traversal
rather than string proximity. This makes CVS detection scope-aware.  
**Complexity**: medium-high. GiNZA gives a modern neural dependency parser and retains
MeCab compatibility.

### 1.5 Fuzzy emoteme matching for repeated characters
**Problem**: internet Japanese stretches characters for emphasis (`やばーーーい`,
`嬉しすぎるーー`). These are emotive but the stretched surface form is not in the
emoteme database.  
**Solution**: pre-normalise the input by collapsing runs of the same character longer
than 2 to exactly 2 before emoteme matching (`ーーー` → `ーー`). Apply this to the
`no_emotem` string only, keeping the original text for display.

---

## 2. Dictionary

### 2.1 Automatic extraction pipeline (Wang/Isomura method, productised)
The Wang & Isomura (2024) paper describes a semi-automatic extraction of new emotive
expressions from corpora using POS-pattern mining and frequency filtering. This pipeline
currently exists only as research code.  
**Goal**: package it as a `mlask-official extract-expressions --corpus corpus.txt`
CLI command that outputs candidate expressions per emotion class for human review.
This would let the dictionary grow with new internet language without waiting for a
manual curation cycle.

### 2.2 Internet language and social-media vocabulary
The Nakamura and Hiejima/Murakami dictionaries were compiled from pre-internet prose.
Large classes of modern emotive expression are absent:
- **Internet slang**: `草 (lol)`, `ｗｗｗ`, `乙`, `神`, `尊い`, `萌え`, `推し`
- **Emoji and emoticons**: single-character emoji (😭, 🥺, 🔥) that carry strong
  emotion signal in contemporary text
- **Gyaru-go / wasei-go**: `まじ`, `やば`, `きつい` in their modern colloquial senses
- **Katakana borrowings**: `ショック`, `テンション`, `ムカつく`

A crowd-sourcing round on Japanese Twitter/X data (similar to Wang/Isomura's corpus
approach) would cover this gap efficiently.

### 2.3 Dialect coverage (Kansai-ben and others)
Kansai dialect has distinct emotive vocabulary and negation patterns:
- `あかん` (no good / forbidden) — already in CVS but rare in dictionaries
- `おもろい/おもいろい` (funny/interesting)
- `しんどい` (exhausted / emotionally drained)
- Negation: `〜へん`, `〜ひん`, `〜ちゃう`

A Kansai-ben emotion sub-dictionary and CVS extension would improve accuracy on
any corpus with western-Japan speakers (YouTube, regional news, etc.).

---

## 3. API and integration

### 3.1 FastAPI REST service
A thin FastAPI wrapper would make ML-Ask Official accessible from any language or
pipeline:
```
POST /analyze          { "text": "..." }        → full result dict
POST /analyze/batch    { "texts": [...] }        → list of results
GET  /emotions                                   → emotion metadata
GET  /health                                     → version + status
```
Add OpenAPI docs automatically. Pair with a Docker image for one-command deployment.
This is the single change that would most expand the potential user base.

### 3.2 Proper CLI with pipe support
The original Perl ML-Ask was a Unix pipe tool (`perl mlask.pl < input.txt`).
The Python rewrite should restore this:
```bash
echo "腹が立つ" | mlask analyze
mlask analyze --file corpus.txt --output results.csv
mlask analyze --format original   # pipe-delimited original format
mlask benchmark --sentences 10000
```
Implement with `typer` or `click`. A good CLI also enables shell scripting and
integration with existing NLP workflows.

### 3.3 Python-native streaming / generator API
For large corpora (millions of sentences), loading all results into memory is
impractical. Add a generator API:
```python
for result in analyzer.analyze_stream(open("big_corpus.txt")):
    process(result)
```
The MeCab tagger is not fork-safe, but a single-threaded generator adds no overhead
beyond what already exists.

### 3.4 Multiprocessing batch for large corpora
MeCab is not fork-safe, but multiple *processes* (not threads) can each maintain
their own tagger. For corpora over ~50,000 sentences:
```python
results = analyzer.analyze_parallel(texts, workers=4)
```
Use `multiprocessing.Pool` with a per-process `MLAskOfficial()` initialiser.
Expected speedup: near-linear with core count.

---

## 4. Evaluation and research tools

### 4.1 Formal benchmark suite
The system has no published accuracy figures for the v0.2/v0.3 dictionary. A
reproducible benchmark should:
1. Use the WRIME dataset (Kajiwara et al., 2021) or a subset of the 2channel corpus
   used in the original ML-Ask papers.
2. Report precision, recall, F1 per emotion class.
3. Compare against the Perl ML-Ask 4.3 and pymlask as baselines.
4. Run as a CI job so regressions are caught automatically.

This is the single most important step before a PyPI release, because it establishes
the claim that v0.3 is meaningfully better than what came before.

### 4.2 Agreement / diff mode vs pymlask
A `--compare-pymlask` flag that runs both engines on the same input and shows
where they disagree, which words each found, and which CVS decisions differed.
Useful for users migrating from pymlask and for identifying dictionary gaps.

### 4.3 Annotation / correction UI in Streamlit
Add an **Annotate** tab where a user can:
- Accept or reject each detected emotion
- Add missing emotions
- Export the corrected annotations as a gold-standard evaluation set

Over time this accumulates a labelled corpus that can be used for the benchmark
above and for active learning of new dictionary entries.

---

## 5. Streamlit app

### 5.1 Session history panel
Keep a sidebar list of the last N analyzed sentences in the session, each showing
its representative emotion and orientation badge. Click any to reload it. Enables
quick comparison without re-typing.

### 5.2 Side-by-side comparison
A sub-tab under **Single text** that accepts two inputs and renders them on the same
Russell 2D chart with different markers. Useful for comparing e.g. two responses to
the same question, or the same sentence before and after a CVS.

### 5.3 Corpus-level trend view in Batch
When a batch input is sorted by time (one sentence per line, with a timestamp prefix),
render a time-series line chart of emotion prevalence. This is the most common
real-world use case: tracking public sentiment over a period of social media posts.

### 5.4 Explanation panel ("why this emotion?")
For each detected emotion, show:
- The exact substring in the *original* (pre-lemmatised) sentence that triggered the match
- The dictionary entry that matched
- Whether it was a full, content (≈), or yomi (≋) match
- Whether CVS was applied and which pattern

This demystifies the system for new users and helps researchers debug edge cases.

### 5.5 Mobile-responsive layout
The current two-column layout breaks on narrow screens. Use `st.columns` width ratios
that collapse gracefully, and make the Russell chart taller than it is wide on mobile.

---

## 6. Packaging and distribution

### 6.1 PyPI release
Before publishing:
- Add a `README.md` badge with accuracy figures (from §4.1)
- Add Python 3.13 to the classifier list; test under 3.9–3.13
- Run `twine check` and fix any metadata issues
- Register `mlask-official` on PyPI (the name is currently unclaimed)
- Add a `CITATION.cff` so GitHub auto-generates a citation block

### 6.2 Conda package
Many Japanese NLP researchers use conda environments. A `conda-forge` recipe would
make installation of MeCab and the Python bindings seamless on all platforms.

### 6.3 Docker image
```dockerfile
FROM python:3.12-slim
RUN apt-get install -y mecab mecab-ipadic-utf8 libmecab-dev
RUN pip install mlask-official[app]
CMD ["mlask", "serve"]           # launches FastAPI
```
Publish to Docker Hub / GitHub Container Registry alongside each tagged release.

---

## 7. Long-term research directions

### 7.1 Hybrid rule + neural approach
The system is purely lexical. A lightweight neural re-ranking layer (e.g., a small
BERT classifier fine-tuned on a Japanese emotion corpus) could be used as a
post-processing step: when the rule system is uncertain (multiple emotion classes,
CVS triggered, or content-only matches), ask the neural model to break the tie.
This preserves the interpretability of the rule layer while improving precision
on hard cases.

### 7.2 Cross-lingual projection
The Wang/Isomura paper maps Hiejima's English-Japanese dictionary to ML-Ask categories.
The same mapping logic could be applied to **SentiWordNet**, **NRC Emotion Lexicon**,
or **WordNet Affect** to automatically generate candidate Japanese translations via
a bilingual dictionary or MT system, with human post-filtering.

### 7.3 Document-level emotion aggregation
ML-Ask analyses sentences. Documents (articles, blog posts, reviews) contain multiple
sentences, often expressing different emotions in different parts. A document-level
module could:
- Aggregate sentence-level results with position weighting (conclusions matter more)
- Detect emotion *shifts* (e.g., starts sad, ends hopeful)
- Model the *dominant* vs *background* emotion
