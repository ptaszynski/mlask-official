# ML-Ask Official — Future Improvements

Roadmap for the next development cycles, grouped by theme and roughly ordered by
implementation priority within each group.  Each item includes a short rationale
explaining *why* it matters, not just *what* it would do.

> Items already shipped in v0.5 (on-disk lemma cache, fugashi/UniDic backend,
> GiNZA dep-tree CVS, fuzzy emoteme, modern dict, `mlask` CLI, streaming +
> multiprocessing APIs, Streamlit JA/EN toggle, time-series view, mobile CSS,
> `CITATION.cff`, conda recipe) are recorded in `CHANGELOG.md` and removed
> from this list.

---

## 1. Matching quality

### 1.1 Reading-level (yomi) normalisation [HIGH PRIORITY]
**Problem**: kanji/kana variants of the same word (`腹が立つ` vs `腹たつ`) are not
matched.  v0.5 confirmed this hurts in practice — IPADIC's lemma for the kana
writing `たつ` is the unrelated verb `経つ` ("to elapse"), so the kana-only input
`腹たつ` never reaches the `腹が立つ` dictionary entry even with particle omission.

**Solution**: build a third Aho-Corasick automaton keyed on the **hiragana reading**
of each dictionary entry (obtained from MeCab's yomi field, converted to hiragana).
Scan the input's reading string in parallel with the lemma string.  Mark yomi
matches with `≋` (double tilde) to distinguish from `≈` content matches.

**Caveat**: reading-based matching may collide across homophonous kanji with
different meanings.  Apply it only to dict tokens whose surface and reading
differ (kana-already-written entries gain nothing and risk nothing).

### 1.2 N-best MeCab parsing for ambiguous tokens
**Problem**: certain compounds tokenise differently depending on context.
`腹がたった` parses as `腹 が たった(adv)` rather than `腹 が たっ(verb) た(aux)`,
causing a miss.  MeCab supports N-best output (`-N 5`).

**Solution**: for input sentences that produce **zero emotion matches**,
re-parse with N=5 and union the boundary sets.  This doubles latency for the
zero-match case but has no effect on the (more common) positive-match case.
Combine with §1.1 for best coverage.

### 1.3 Particle-class learning from the dictionary itself
**Problem**: the CVS suffix regex enumerates particles by hand
(`[だとはでがはもならじゃちってんすあ]`); v0.4 had to be patched twice
(missing `だ`, missing `に`).  Each gap is a silent CVS miss.

**Solution**: at startup, scan the dictionary entries and extract every particle
that appears between content tokens.  Use that learned set to build the CVS
particle character class dynamically.  Removes a class of regex-maintenance bugs.

---

## 2. Dictionary

### 2.1 Wang/Isomura extraction — full productisation
v0.5 ships `mlask extract` as an initial POS-pattern miner.  Open items:
- Add the n-gram statistical-significance filter from the published paper
  (currently we only do frequency).
- Include a feedback loop: a Streamlit "review candidates" UI that lets the
  user accept / reject extracted candidates per class, writing accepted ones
  back to `<emotion>_extracted.txt`.
- Auto-rebuild the lemma cache after acceptance.

### 2.2 Dialect coverage (Kansai-ben and others)
Kansai dialect has distinct emotive vocabulary and negation patterns:
- `あかん` (no good / forbidden) — in CVS but rare in dictionaries
- `おもろい / おもいろい` (funny / interesting)
- `しんどい` (exhausted / emotionally drained)
- Negation: `〜へん`, `〜ひん`, `〜ちゃう`

A Kansai-ben emotion sub-dictionary and CVS extension would improve accuracy
on any corpus with western-Japan speakers (YouTube, regional news, etc.).
Domain analogues (medical Japanese, legal Japanese, gaming slang) would
benefit from the same opt-in extension mechanism.

### 2.3 User-supplied custom dictionaries [NEW]
**Problem**: researchers and product teams routinely have domain-specific
emotion vocabulary (game-genre slang, brand-specific sentiment, custom emoji
sets) that doesn't belong in the shipped dictionary but needs first-class
matching.

**Solution**: accept user dictionaries at construction time:
```python
MLAskOfficial(extra_dicts={"yorokobi": ["最高だぜ", "GG"]})
# or
MLAskOfficial(extra_dicts_path="my_dict/")
```
Honour the same `_modern.txt` file convention so users can drop a folder in
and load it.  Cache key includes the MD5 of the extra dicts.

### 2.4 Crowd-sourced internet-language pass [NEW]
v0.5 added a curated batch of emoji / kaomoji / gyaru-go / katakana borrowings,
but real internet Japanese moves faster than a single author can keep up with.
A community pass — opening an issue template inviting Japanese-fluent
contributors to PR new entries with rationale + example sentences — would
broaden coverage cheaply.

---

## 3. API and integration

### 3.1 FastAPI REST service + `mlask serve` subcommand
A thin FastAPI wrapper would make ML-Ask Official accessible from any
language or pipeline:
```
POST /analyze          { "text": "..." }        → full result dict
POST /analyze/batch    { "texts": [...] }       → list of results
GET  /emotions                                  → emotion metadata
GET  /health                                    → version + status
```
Wire it into the CLI as `mlask serve --port 8000` (the CLI already has
`typer`, the rest is one `FastAPI()` app).  Pair with the §6.3 Docker image
for one-command deployment.  Single change that would most expand the
potential user base.

### 3.2 JSON Schema for the result dict [NEW]
The `analyze()` return dict has stabilised at 9 keys across v0.3–v0.5.
Formalise it as a published JSON Schema (`mlask_official/schemas/result.json`)
and add a `--validate` flag to the CLI's `batch` subcommand.  Downstream
pipelines can lock their contract to a schema version.

### 3.3 Pre-tokenised input support [NEW]
**Problem**: users with an existing NLP pipeline (e.g. spaCy / GiNZA in a
larger app) waste cycles re-tokenising every sentence through MeCab.

**Solution**: an `analyze_tokens(tokens)` method that accepts a list of
`(surface, pos, lemma)` tuples (matching `_parse_tokens()` output) and skips
the MeCab step.  Zero overhead for callers who already have tokens; identical
matching semantics.

---

## 4. Evaluation and research tools

### 4.1 Formal benchmark suite [HIGH PRIORITY]
The system has no published accuracy figures for the v0.3+ dictionaries.
A reproducible benchmark should:
1. Use the **WRIME** dataset (Kajiwara et al., 2021) or a subset of the
   2channel corpus used in the original ML-Ask papers.
2. Report precision, recall, F1 per emotion class.
3. Compare against the Perl ML-Ask 4.3 and pymlask as baselines.
4. Run as a CI job so regressions are caught automatically.

This is the single most important step before claiming v0.5 is meaningfully
better than what came before — and it provides the F1 numbers needed for the
README badge / paper update.

### 4.2 Agreement / diff mode vs pymlask
A `--compare-pymlask` flag that runs both engines on the same input and
shows where they disagree, which words each found, and which CVS decisions
differed.  Useful for users migrating from pymlask and for identifying
dictionary gaps in either engine.

### 4.3 Annotation / correction UI in Streamlit
Add an **Annotate** tab where a user can:
- Accept or reject each detected emotion
- Add missing emotions
- Export the corrected annotations as a gold-standard evaluation set

Accumulates a labelled corpus over time, usable for the §4.1 benchmark and
for active learning of new dictionary entries (loop with §2.1).

---

## 5. Streamlit app

### 5.1 Session history panel
Keep a sidebar list of the last *N* analyzed sentences in the session, each
showing its representative emotion and valence badge.  Click any to reload it.
Enables quick comparison without re-typing.

### 5.2 Side-by-side comparison
A sub-tab under **Single text** that accepts two inputs and renders them on the
same Russell 2D chart with different markers.  Useful for A/B testing rewrites,
or comparing the same sentence before and after a CVS pattern.

### 5.3 Explanation panel ("why this emotion?")
For each detected emotion, show:
- The exact substring in the **original** (pre-lemmatised) sentence that
  triggered the match
- The dictionary entry that matched + the file it came from
- Whether it was a full, content (≈), yomi (≋), or dep-CVS (`*depCVS`) match
- Whether CVS was applied and which pattern fired

Demystifies the system for new users and helps researchers debug edge cases.

### 5.4 Live token-by-token highlighting [NEW]
**Idea**: as the user types in the input box, colour each token inline with
its emotion class (greyed out if not a match).  Implements "what does ML-Ask
see right now?" intuition for casual users — turns the app into an
interactive teaching tool.

### 5.5 Persistent settings via query string [NEW]
Currently every page reload resets the language, MeCab args, and any sample
text.  Encode the active settings into the URL query string so a shareable
link reproduces the same configuration.  Useful for paper authors linking to
specific example analyses.

---

## 6. Packaging and distribution

### 6.1 Production PyPI release
v0.5 is on TestPyPI.  Remaining work for the real PyPI release:
- Verify install on a fresh Python 3.10 / 3.11 / 3.12 / 3.13 venv
  (all four — done via §7.1 CI matrix).
- Write a one-page upgrade guide for pymlask users.
- Open a discussion topic on the Wang/Isomura repository pointing at the new
  package as a reference implementation.
- Push v0.5.0 to PyPI (`twine upload --repository pypi dist/*`).

### 6.2 conda-forge submission
The recipe at `conda-recipe/meta.yaml` is ready; the submission is a
PR to the [conda-forge/staged-recipes](https://github.com/conda-forge/staged-recipes)
repository.  Once merged, `conda install -c conda-forge mlask-official` works
on every conda-supported OS.

### 6.3 Docker image
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y mecab mecab-ipadic-utf8 libmecab-dev
RUN pip install 'mlask-official[app]'
CMD ["mlask", "serve"]           # launches FastAPI (§3.1)
```
Publish to Docker Hub / GitHub Container Registry alongside each tagged
release.  Solves the system-MeCab installation pain in one image.

### 6.4 Hugging Face Space deployment template [NEW]
Hugging Face Spaces is the de-facto demo platform for NLP research.  A
ready-made `Space` repository (Dockerfile + Streamlit app + README.md
explaining how to fork-and-deploy) would give the project a permanent
public demo URL with zero infrastructure cost.

---

## 7. Quality + testing infrastructure [NEW SECTION]

### 7.1 GitHub Actions CI matrix
- Test matrix: Python 3.10 × 3.11 × 3.12 × 3.13, Ubuntu × macOS.
- Steps: install system MeCab + IPADIC, `pip install -e '.[dev]'`, run pytest.
- A second job runs `twine check` on every PR and `python -m build` on tags.
- Optional: cache the `~/.cache/mlask_official` lemma pickle between runs.

### 7.2 Real pytest suite (currently: ad-hoc audit script)
The v0.5 audit at `/tmp/mlask_v05_audit.py` covers 58 checks but lives outside
the repo.  Convert it into a proper `tests/` directory:
- `tests/test_analyzer.py` — CVS battery, fuzzy emoteme, modern dict.
- `tests/test_cli.py` — every subcommand via `subprocess`.
- `tests/test_streamlit.py` — headless import + a couple of `parse_*` helpers.
- `tests/conftest.py` — fixture that builds the analyzer once per session.

Goal: a single `pytest` invocation green-lights every claim in the CHANGELOG.

### 7.3 Performance regression tests [NEW]
A pytest-benchmark suite that asserts `analyze_batch(10_000)` completes
under a soft latency budget (e.g. 350 ms on the GH Actions runner).  Catches
the dictionary-growth-vs-throughput trade-off before it becomes a release
surprise.

### 7.4 Reproducibility manifest [NEW]
Add a `mlask info` CLI subcommand that prints package version, backend name,
dictionary fingerprint, IPADIC/UniDic version, and Python version.  Required
context for any research result citing the library.

---

## 8. Ecosystem extensions [NEW SECTION]

### 8.1 Conversation / dialog-level analysis
**Problem**: chat logs, customer-service transcripts, and multi-turn dialogues
need emotion tracking *per speaker per turn*, plus inter-turn shift detection
("user calmed down after agent's reply").  Sentence-level ML-Ask under-uses
the structure.

**Solution**: a `DialogAnalyzer` that consumes a list of
`(speaker_id, timestamp, utterance)` tuples and produces per-speaker emotion
trajectories + shift events.  Built on top of `analyze_stream()`.

### 8.2 Document-level emotion aggregation
ML-Ask analyses sentences.  Documents (articles, blog posts, reviews) contain
multiple sentences, often expressing different emotions in different parts.
A document-level module could:
- Aggregate sentence-level results with position weighting (conclusions
  matter more for review-like documents).
- Detect emotion *shifts* (e.g., starts sad, ends hopeful).
- Model *dominant* vs *background* emotion.

### 8.3 Plugin system for custom emotion classes [NEW]
The 10 Nakamura classes are fixed by the published model.  Some downstream
applications need additional or alternative classes (e.g., add `envy`,
`pride`; or replace the 10 with the 6 Ekman basics).  A plugin interface
would let users register their own class set + per-class dictionaries +
Russell coordinates + colours, without forking.

### 8.4 VS Code / Jupyter quick-analysis extension [NEW]
Right-click any selected Japanese text in VS Code / Jupyter → "Analyse
emotion" → inline output with the representative class, valence, and the
matched words.  Low-effort wrapper around the existing CLI; large impact on
adoption among researchers who live in those editors.

---

## 9. Long-term research directions

### 9.1 Hybrid rule + neural approach
The system is purely lexical.  A lightweight neural re-ranking layer (e.g., a
small BERT classifier fine-tuned on a Japanese emotion corpus) could be used
as a post-processing step: when the rule system is uncertain (multiple
emotion classes, CVS triggered, or content-only matches), ask the neural
model to break the tie.  Preserves the interpretability of the rule layer
while improving precision on hard cases.

### 9.2 Cross-lingual projection (sister packages)
The Wang/Isomura paper maps Hiejima's English-Japanese dictionary to ML-Ask
categories.  The same mapping logic could be applied to **SentiWordNet**,
**NRC Emotion Lexicon**, or **WordNet Affect** to automatically generate
candidate Japanese translations via a bilingual dictionary or MT system,
with human post-filtering.

A natural extension is **language-sister packages** — `mlask-en`, `mlask-ko`,
`mlask-zh` — each with a language-specific tokeniser plug-in but the same
analyzer skeleton, Russell coordinates, and Plutchik colour palette.

### 9.3 Confidence calibration from corpus statistics [NEW]
Currently a match is binary: it fires or it doesn't.  But a 1-occurrence
dictionary hit on a rare expression is more diagnostic than the same hit on
a high-frequency word like `好き`.  Compute per-word IDF from a large
Japanese reference corpus once, and surface a confidence score per detected
emotion in the result dict (`emotion_confidence: {ikari: 0.92, iya: 0.41}`).
Preserves the rule-based interpretability while quantifying certainty.

### 9.4 Multi-sentence sentiment-shift detection [NEW]
Within a single multi-clause sentence, the speaker often shifts emotion
(`最初は嬉しかったけど、後で悲しくなった`).  A sentence-internal segmenter
(split on `〜けど`, `〜が`, `〜のに`) + per-segment ML-Ask + a shift score
captures contrastive emotion within one sentence.  Bridges the gap between
sentence-level and discourse-level analysis.
