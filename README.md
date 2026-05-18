# ML-Ask Official

**eMotive eLement and Expression Analysis system — official Python rewrite by the original author.**

[![PyPI version](https://img.shields.io/pypi/v/mlask-official.svg)](https://pypi.org/project/mlask-official/)
[![Python versions](https://img.shields.io/pypi/pyversions/mlask-official.svg)](https://pypi.org/project/mlask-official/)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](LICENSE)
[![Streamlit demo](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://mlask-official.streamlit.app/)

High-performance Japanese emotion analysis.  Originally developed by
Michal Ptaszynski, Pawel Dybala, Rafal Rzepka and Kenji Araki at Hokkaido
University, the system was first described in
Ptaszynski et al. (2017, *Journal of Open Research Software*) and extended with
new dictionaries in Wang et al. (2024, *Applied Sciences*).  This package is
the official Python implementation maintained by the original author.

- 📦 **PyPI:** <https://pypi.org/project/mlask-official/>
- 🧪 **Hosted demo:** <https://mlask-official.streamlit.app/>
- 🐙 **Source + issues:** <https://github.com/ptaszynski/mlask-official>
- 📝 **Changelog:** [CHANGELOG.md](CHANGELOG.md)
- 🗺️ **Roadmap:** [IMPROVEMENTS.md](IMPROVEMENTS.md)
- 📚 **Citation file:** [CITATION.cff](CITATION.cff)

---

## Quick start

```bash
# 1. system MeCab + IPADIC (macOS shown; see Installation for other OSes)
brew install mecab mecab-ipadic

# 2. the package
pip install 'mlask-official[app]'

# 3. analyze a sentence
python -c "from mlask_official import MLAskOfficial; \
print(MLAskOfficial().analyze('彼のことは嫌いではない！')['valence'])"
# → POSITIVE
```

CLI and web app both ship in the same install:

```bash
echo "腹が立つ" | mlask analyze --format pipe
streamlit run streamlit_app.py     # from a source checkout
```

---

## About ML-Ask

ML-Ask (*eMotive eLement and Expression Analysis system*) is a keyword-based
rule system for automatic affect annotation of Japanese utterances.  It
combines a curated lexicon of ~4,700 emotive expressions across 10 categories
with a particle-stripped content-form pass and a Contextual Valence Shifter
(CVS) layer for negation.

---

## Features

- **Combined and expanded dictionaries** — Nakamura's original *Dictionary of
  Emotive Expressions* merged with the Wang & Isomura (2024) two-dictionary
  expansion (Hiejima's and Murakami's emotion dictionaries, plus automatically
  extracted expressions).  Total: ~4,700 entries across 10 emotion classes,
  augmented with modern internet language (emoji, kaomoji, gyaru-go, katakana
  borrowings) per class.
- **Russell's 2D circumplex model** of affect — every emotion class is placed
  on a (valence, arousal) plane; aggregate sentence orientation is reported
  as `valence` (POSITIVE / NEGATIVE / NEUTRAL, optionally `mostly_*`) and
  `activation` (ACTIVE / PASSIVE / NEUTRAL).
- **Plutchik-wheel colour palette** — all 10 emotion classes are colour-coded
  by the hue angles of Plutchik's published wheel for a familiar,
  paper-ready palette.
- **Dual Aho-Corasick matching** — two automata are built at startup, one
  over fully lemmatised dictionary entries (covers verb inflections) and one
  over particle-stripped content forms (covers particle-omission variants
  such as 腹がたつ ↔ 腹たつ).  Both automata scan in a single O(n + k) pass
  per sentence; sustained throughput is ~50,000 sentences/sec on a single
  core, ~100,000 sentences/sec on four.
- **CVS (Contextual Valence Shifters)** — 108 Japanese negation patterns
  reverse emotion polarity when applied (`嫌いではない` → positive, not
  negative).  An optional GiNZA dependency-tree pass catches long-distance
  negation that the local regex misses.
- **Three-state emotive distinction** — `analyze()` returns `emotive: bool`
  even when no specific emotion word is detected, so callers can distinguish
  emotive-but-unclassifiable sentences (interjections / kaomoji only) from
  fully non-emotive ones.
- **Streaming + multiprocessing APIs** — `analyze_stream()` for
  memory-light corpus processing; auto-parallel batches at ≥ 50,000 sentences.
- **JA/EN Streamlit web app** with publication-quality charts (radar +
  Russell 2D + time-series + heatmap), PNG export at 2× scale, and a
  language toggle that flips all UI strings + emotion labels.
- **On-disk lemma cache** — sub-millisecond warm-start once the cache is
  primed; MD5-invalidated.
- **Optional UniDic backend** via fugashi for users who prefer modern
  morphological analysis.

---

## Emotion classes

| Name       | English gloss | Japanese | Valence | Arousal | Plutchik hue |
|------------|--------------|----------|---------|---------|-------------|
| yorokobi   | joy          | 喜び      | POS     | ACT     | yellow      |
| suki       | affection    | 好き      | POS     | —       | yellow-green|
| yasu       | relief       | 安らぎ    | POS     | PAS     | green-yellow|
| takaburi   | excitement   | 昂り      | NorP    | ACT     | orange      |
| odoroki    | surprise     | 驚き      | NorP    | ACT     | teal-cyan   |
| haji       | shame        | 恥        | NorP    | —       | rose-purple |
| aware      | sadness      | 哀しみ    | NEG     | PAS     | royal blue  |
| iya        | disgust      | 嫌悪      | NEG     | —       | dark orchid |
| kowa       | fear         | 恐れ      | NEG     | ACT     | green       |
| ikari      | anger        | 怒り      | NEG     | ACT     | crimson     |

### Representative emotion

For sentences where ML-Ask detects multiple emotion classes, the
**representative emotion** is the single class chosen as the dominant one for
the sentence.  The heuristic — inherited from the original Perl ML-Ask — is:

> *The class whose longest matched expression has the most characters.*

For example, in *「腹がたって仕方ない、もう嫌だ」* both *ikari* (`腹が立つ`) and
*iya* (`嫌だ`) match; *ikari* wins because `腹が立つ` is longer than `嫌だ`.
The intuition is that longer dictionary entries are more specific — and
therefore more diagnostic of the speaker's emotion — than shorter, more
generic ones.

Returned as `result["representative"] = (class_name, [matching_words])`.

---

## Installation

ML-Ask Official runs on **Linux, macOS and Windows (WSL recommended)** with
**Python 3.10 – 3.13**.  It depends on the
[MeCab](https://taku910.github.io/mecab/) morphological analyser, which is a
*system* package (not Python), so the install is split into two parts:

1. install MeCab + a Japanese dictionary at the OS level,
2. install the `mlask-official` Python package inside a virtualenv.

### Step 1 — Install MeCab + a Japanese dictionary

#### macOS (Homebrew)

```bash
brew install mecab mecab-ipadic
```

Verify:

```bash
echo "今日は嬉しい" | mecab
```

You should see one token per line and an `EOS` marker.

#### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y mecab libmecab-dev mecab-ipadic-utf8
```

#### Fedora / RHEL

```bash
sudo dnf install mecab mecab-devel mecab-ipadic
```

#### Arch Linux

```bash
sudo pacman -S mecab mecab-ipadic
```

#### Windows

Native Windows MeCab is fragile — **the recommended path is Windows Subsystem
for Linux (WSL2)**: install Ubuntu under WSL and follow the Ubuntu
instructions above.  If you must run on bare Windows, see the
[mecab-python3 README](https://github.com/SamuraiT/mecab-python3#windows)
for the MSVC build steps.

### Step 2 — Create a Python virtual environment

Strongly recommended (keeps the package's dependencies out of your system
Python):

```bash
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate.bat       # Windows cmd
# .venv\Scripts\Activate.ps1       # Windows PowerShell
```

Make sure `python --version` reports 3.10 or newer.

### Step 3 — Install `mlask-official`

#### From PyPI

```bash
pip install mlask-official            # core: analyzer + CLI
pip install 'mlask-official[app]'     # + Streamlit web app
pip install 'mlask-official[fugashi]' # + UniDic backend via fugashi
pip install 'mlask-official[deps]'    # + GiNZA dependency-tree CVS
pip install 'mlask-official[all]'     # everything above
```

#### From a source checkout

```bash
git clone https://github.com/ptaszynski/mlask-official.git
cd mlask-official
pip install -e .                      # editable core install
pip install -e '.[all]'               # editable + every extra
```

The base install pulls in `mecab-python3`, `pyahocorasick`, and `typer`
automatically.

### Step 4 — Verify the installation

#### Python API

```bash
python -c "from mlask_official import MLAskOfficial; \
print(MLAskOfficial().analyze('今日は嬉しい！')['valence'])"
```

You should see:

```
POSITIVE
```

#### CLI

```bash
mlask --help
echo "彼のことは嫌いではない！" | mlask analyze --format pipe
```

The pipe-format output should look like:

```
彼のことは嫌いではない！|emotions:(2)|YOR:嫌い*CVS 嫌いな*CVS|SUK:嫌い*CVS 嫌いな*CVS||2D|POSITIVE|NEUTRAL
```

#### Streamlit app

The Streamlit application is part of the source repository.  Easiest way to
try it is the hosted demo:

> **<https://mlask-official.streamlit.app/>**

To run it locally, clone the repo and launch from there:

```bash
git clone https://github.com/ptaszynski/mlask-official.git
cd mlask-official
pip install -e '.[app]'
bash run_app.sh                        # → http://localhost:8501
bash run_app.sh --server.port 8505     # custom port
```

Open the URL in your browser and try the *Quick examples* under the input box.

### Step 5 — Troubleshooting

**`RuntimeError: Failed initializing MeCab` (`no such file: /usr/local/etc/mecabrc`)**

`mecab-python3` can't find `mecabrc`.  Find it and pass it explicitly:

```bash
mecab-config --sysconfdir   # → e.g. /opt/homebrew/etc

python -c "from mlask_official import MLAskOfficial; \
print(MLAskOfficial(mecab_arg='-r /opt/homebrew/etc/mecabrc').analyze('嬉しい'))"
```

Or pass `--mecab-arg "-r /opt/homebrew/etc/mecabrc"` to the CLI.  The
Streamlit app has a *MeCab arguments* field in the sidebar for the same
purpose.

**`No module named 'MeCab'`**

`mecab-python3` failed to compile against your system MeCab.  Re-install
with verbose output:

```bash
pip install --force-reinstall --verbose mecab-python3
```

On macOS the most common cause is missing Xcode command-line tools
(`xcode-select --install`).

**`No module named 'fugashi'` / `'spacy'`**

Optional extras aren't installed.  Either disable the feature
(`MLAskOfficial(backend="mecab", use_dependency_cvs=False)`) or install
the relevant extra group from step 3.

**`built an empty emotion index` / `Not an Aho-Corasick automaton yet`**

MeCab returned no tokens for the shipped dictionary entries — usually a bad
or mismatched dictionary path.  The error message lists the three most
common causes and the fix for each.  See also the *Notes on tokenisation*
section below.

**Stale lemma cache after a manual dictionary edit**

The cache is invalidated by file *content* (MD5), so saving the file will
already invalidate it.  To force a rebuild explicitly:

```bash
rm -rf ~/.cache/mlask_official
# or per-call:
python -c "from mlask_official import MLAskOfficial; MLAskOfficial(use_cache=False)"
```

---

## Usage

```python
from mlask_official import MLAskOfficial

a = MLAskOfficial()

# Inflected form — handled by full-lemma automaton
r = a.analyze("身の毛がよだった！")
print(r["emotion"])       # {'kowa': ['身の毛がよだつ']}
print(r["valence"])       # 'NEGATIVE'
print(r["activation"])    # 'ACTIVE'
print(r["emotive"])       # True

# Particle dropped — handled by content-lemma automaton
#   (use the kanji form when possible — IPADIC's lemma for the kana
#    writing `たつ` is the unrelated verb `経つ` "to elapse",
#    so kana variants of ambiguous verbs may miss; see §Notes.)
r = a.analyze("腹立つ！")
print(r["emotion"])       # {'ikari': ['腹立ち', '腹立つ', '腹が立つ≈']}

r = a.analyze("身の毛よだつ")          # particle が dropped
print(r["emotion"])       # {'kowa': ['身の毛がよだつ≈']}

# Negation via CVS
r = a.analyze("彼のことは嫌いではない！")
print(r["valence"])       # 'POSITIVE'  ← 嫌い → CVS flip → yorokobi/suki

# Emotive but no classifiable emotion
r = a.analyze("あーもう！！")
print(r["emotion"])       # None
print(r["emotive"])       # True  ← emotemes detected
print(r["intensifier"])   # {'emotemes': ['！','！'], 'interjections': ['あー','もう']}

# Non-emotive
r = a.analyze("今日は晴れです。")
print(r["emotion"])       # None
print(r["emotive"])       # False
```

### Streaming + parallel APIs

```python
# Generator — constant-memory for large corpora
for result in a.analyze_stream(open("big_corpus.txt", encoding="utf-8")):
    process(result)

# Multiprocessing — auto-on for batches ≥ 50,000 sentences
results = a.analyze_batch(texts)                 # auto: parallel iff len(texts) ≥ 50_000
results = a.analyze_batch(texts, parallel=True,  # force on
                          workers=8)
```

### Notes on tokenisation

ML-Ask delegates tokenisation and lemmatisation to MeCab.  Two practical
consequences worth knowing:

* **Use IPADIC, not UniDic.**  The shipped dictionaries (Nakamura + Wang &
  Isomura) were compiled against the IPADIC POS scheme.  UniDic tokenises
  some compounds differently and won't kanji-normalise kana writings, which
  reduces match coverage.  If you previously installed `unidic-lite` as a
  side effect of another package, point MeCab back at IPADIC explicitly:

  ```bash
  brew install mecab-ipadic
  # then either edit /opt/homebrew/etc/mecabrc to set
  #     dicdir = /opt/homebrew/lib/mecab/dic/ipadic
  # or pass -d per call:
  MLAskOfficial(mecab_arg="-d /opt/homebrew/lib/mecab/dic/ipadic")
  ```

* **Kana writings of ambiguous verbs may miss.**  IPADIC's lemma table picks
  the most frequent reading for a kana writing.  `たつ` in isolation
  lemmatises to `経つ` ("to elapse"), not `立つ` ("to stand"), so a kana-only
  input like `腹たつ` won't reach the `腹が立つ` dictionary entry even with
  particle omission.  The same input written `腹立つ` or `腹が立つ` matches
  cleanly.  Robust yomi/N-best parsing for these cases is tracked as
  [IMPROVEMENTS.md §1.1 + §1.2](IMPROVEMENTS.md).

---

## Command-line interface

```bash
# Single sentence (stdin or --text)
echo "腹が立つ"                  | mlask analyze --format pipe
echo "彼のことは嫌いではない！"   | mlask analyze --format json

# Batch a file
mlask batch -i corpus.txt -o results.csv  --format csv
mlask batch -i corpus.txt -o results.json --format json --parallel
mlask batch -i corpus.txt                 --format pipe > results.txt

# Throughput benchmark
mlask benchmark --sentences 10000
mlask benchmark --sentences 100000 --parallel -j 8

# Mine candidate emotive expressions from a corpus (manual-review TSV)
mlask extract corpus.txt --output candidates.tsv --min-freq 5
```

All commands accept `--backend mecab|fugashi` and
`--mecab-arg "-r /path/to/mecabrc"`.

---

## Performance

On Apple Silicon (Python 3.14, mecab-python3 + IPADIC):

| Workload | Throughput |
|---|---|
| Cold start (no cache) | ~37 ms |
| Warm start (cache hit) | ~17 ms |
| Single sentence (steady-state) | 20 µs median, 46 µs p99 |
| Sequential batch (10,000 sentences) | ~50,000 sentences/sec |
| Multiprocessing batch (10,000 × 4 workers) | ~50,000 sentences/sec |
| Auto-parallel `analyze_batch(50,000)` | ~100,000 sentences/sec |

See [CHANGELOG.md](CHANGELOG.md) for full benchmark methodology.

---

## Citation

When using ML-Ask in research, please cite both of the following:

> Ptaszynski, M., Dybala, P., Rzepka, R., Araki, K., & Masui, F. (2017).
> *ML-Ask: Open source affect analysis software for textual input in
> Japanese.* Journal of Open Research Software, 5(1), 16-16.

```bibtex
@article{ptaszynski2017ml,
  title={ML-Ask: Open source affect analysis software for textual input in Japanese},
  author={Ptaszynski, Michal and Dybala, Pawel and Rzepka, Rafal and Araki, Kenji and Masui, Fumito},
  journal={Journal of Open Research Software},
  volume={5},
  number={1},
  pages={16--16},
  year={2017}
}
```

> Wang, L., Isomura, S., Ptaszynski, M., Dybala, P., Urabe, Y., Rzepka, R.,
> & Masui, F. (2024). *The limits of words: expanding a word-based emotion
> analysis system with multiple emotion dictionaries and the automatic
> extraction of emotive expressions.* Applied Sciences, 14(11), 4439.

```bibtex
@article{wang2024limits,
  title={The limits of words: expanding a word-based emotion analysis system with multiple emotion dictionaries and the automatic extraction of emotive expressions},
  author={Wang, Lu and Isomura, Sho and Ptaszynski, Michal and Dybala, Pawel and Urabe, Yuki and Rzepka, Rafal and Masui, Fumito},
  journal={Applied Sciences},
  volume={14},
  number={11},
  pages={4439},
  year={2024},
  publisher={MDPI}
}
```

A machine-readable Citation File Format manifest is at
[`CITATION.cff`](CITATION.cff).

---

## Contributing

Issues, pull requests, and dictionary submissions are welcome at
<https://github.com/ptaszynski/mlask-official>.  See [IMPROVEMENTS.md](IMPROVEMENTS.md)
for the active roadmap; ❮ HIGH PRIORITY ❯ items are the best first
contributions.

When opening a PR that touches the emotion dictionaries (`mlask_official/emotions/*.txt`),
please include:

1. The source / rationale for each entry (paper, corpus reference, or
   example sentence).
2. Evidence that the entry doesn't collide with an existing class
   (`mlask analyze --text "<entry>"` before and after).
3. A note in [CHANGELOG.md](CHANGELOG.md) under an `[Unreleased]` section.

---

## License

[BSD 3-Clause](LICENSE) — the same licence as the original ML-Ask system.
