# -*- coding: utf-8 -*-
"""
ML-Ask Official — eMotive eLement and Expression Analysis system  v0.5
High-performance Python implementation using dual Aho-Corasick automata.

What's new in v0.5
------------------
* **On-disk lemma cache** (~25 ms saved at every cold start; mtime+MD5 invalidated).
* **Optional fugashi/UniDic backend** for better verb-boundary coverage
  (``MLAskOfficial(backend="fugashi")``).
* **Optional GiNZA dependency-tree CVS** for long-distance negation
  (``MLAskOfficial(use_dependency_cvs=True)``).
* **Fuzzy emoteme matching** for stretched characters (やばーーーい → やばーい).
* **Modern-language dictionaries** (emoji, kaomoji, gyaru-go, katakana borrowings).
* **Streaming + multiprocessing APIs**: ``analyze_stream()`` and
  ``analyze_parallel()`` (the latter auto-on at ≥ 50,000 sentences).
* **Japanese emotion labels** exported as ``EMOTION_LABELS_JA``.

See CHANGELOG.md for full history.
"""
import collections
import hashlib
import multiprocessing as mp
import os
import pickle
import re
import subprocess
import warnings
from pathlib import Path
from typing import Iterable, Iterator, Optional, Union

import ahocorasick

__version__ = "0.5.0"

EMOTIONS = (
    "aware", "haji", "ikari", "iya", "kowa",
    "odoroki", "suki", "takaburi", "yasu", "yorokobi",
)

# English labels for human-readable display.
EMOTION_LABELS_EN: dict[str, str] = {
    "aware":    "Aware (sadness)",
    "haji":     "Haji (shame)",
    "ikari":    "Ikari (anger)",
    "iya":      "Iya (disgust)",
    "kowa":     "Kowa (fear)",
    "odoroki":  "Odoroki (surprise)",
    "suki":     "Suki (affection)",
    "takaburi": "Takaburi (excitement)",
    "yasu":     "Yasu (relief)",
    "yorokobi": "Yorokobi (joy)",
}

# Japanese labels for Japanese-language UI.  Uses noun forms that map cleanly
# to the Nakamura categories (哀しみ rather than 哀, 喜び rather than 喜).
EMOTION_LABELS_JA: dict[str, str] = {
    "aware":    "哀しみ",
    "haji":     "恥",
    "ikari":    "怒り",
    "iya":      "嫌悪",
    "kowa":     "恐れ",
    "odoroki":  "驚き",
    "suki":     "好き",
    "takaburi": "昂り",
    "yasu":     "安らぎ",
    "yorokobi": "喜び",
}

# Contextual Valence Shifters: which emotions flip to which when negated
CVS_TABLE: dict[str, list[str]] = {
    "suki":     ["iya"],
    "ikari":    ["yasu"],
    "kowa":     ["yasu"],
    "yasu":     ["ikari", "takaburi", "odoroki", "haji", "kowa"],
    "iya":      ["yorokobi", "suki"],
    "aware":    ["suki", "yorokobi", "takaburi", "odoroki", "haji"],
    "takaburi": ["yasu", "aware"],
    "odoroki":  ["yasu", "aware"],
    "haji":     ["yasu", "aware"],
    "yorokobi": ["iya"],
}

VALENCE: dict[str, str] = {
    "yasu": "P", "yorokobi": "P", "suki": "P",
    "iya": "N", "aware": "N", "ikari": "N", "kowa": "N",
    "takaburi": "NorP", "odoroki": "NorP", "haji": "NorP",
}
ACTIVATION: dict[str, str] = {
    "takaburi": "A", "odoroki": "A", "haji": "A", "ikari": "A", "kowa": "A",
    "yasu": "P", "aware": "P",
    "iya": "N", "yorokobi": "N", "suki": "N",
}
RUSSELL_COORDS: dict[str, tuple[float, float]] = {
    "yorokobi": ( 0.85,  0.50),
    "suki":     ( 0.75,  0.10),
    "yasu":     ( 0.65, -0.70),
    "takaburi": ( 0.45,  0.85),
    "odoroki":  ( 0.05,  0.80),
    "haji":     (-0.30,  0.20),
    "aware":    (-0.55, -0.55),
    "iya":      (-0.75,  0.05),
    "kowa":     (-0.60,  0.75),
    "ikari":    (-0.82,  0.80),
}

# POS tags kept as "content words" for the particle-stripped automaton.
# Includes both IPADIC and UniDic POS labels (the v0.5 fugashi backend uses
# UniDic, which spells some labels slightly differently).
_CONTENT_POS = frozenset((
    "名詞", "動詞", "形容詞", "形容動詞", "副詞",
    "感動詞", "接頭詞", "接頭語", "代名詞",
))

# --- Pre-compiled regex patterns (compiled once at import time) ---

_RE_PARTICLES = "[だとはでがはもならじゃちってんすあ]*"
_RE_CVS = (
    "いまひとつもない|なくても?問題ない|わけに[はも]?いかない|わけに[はも]?いくまい"
    "|いまひとつない|ちょ?っとも?ない|なくても?大丈夫|今ひとつもない|訳にはいくまい"
    "|訳に[はも]?[行い]かない|そんなにない|ぜったいない|まったくない|すこしもない"
    "|いまいちない|ぜんぜんない|そもそもない|いけない|ゼッタイない|今ひとつない"
    "|今一つもない|行けない|あまりない|なくていい|なくても?OK|なくても?結構"
    "|少しもない|今一つない|今いちない|言えるない|いえるない|行かん|あかん|いかん"
    "|なくても?良い|てはだめ|[ちじ]ゃだめ|余りない|絶対ない|全くない|今一ない"
    "|全然ない|もんか|ものか|あるますん|ない|いない|思うない|思えるない"
    "|ありません|ありませんでした|ませんでした|ません|なかった|なくて"
    "|訳[がだではもならじゃに]*ない|わけ[がだではもならじゃに]*ない"
)
RE_CVS_SUFFIX = re.compile(f"(?:{_RE_PARTICLES})(?:{_RE_CVS})")

# Negation lemmas used by the dependency-tree CVS (5.1.4).  Surface text isn't
# checked there; we look up token lemmas directly in this set.
_DEP_CVS_NEG_LEMMAS = frozenset(("ない", "ぬ", "ん", "ねぇ", "ねえ", "ぬか"))

_BRACKET = r"\[|\(|\（|\【|\{|\〈|\［|\｛|\＜|\｜|\|"
_EMOTICON_CHARS = (
    r"￣|◕|´|_|ﾟ|・|｀|\-|\^|\ |･|＾|ω|\`|＿|゜|∀|\/|Д|　|\~|д|T|▽|o|ー|\<"
    r"|。|°|∇|；|ﾉ|\>|ε|\)|\(|≦|\;|\'|▼|⌒|\*|ノ|─|≧|ゝ|●|□|＜|＼|0|\.|○"
    r"|━|＞|\||O|ｰ|\+|◎|｡|◇|艸|Ｔ|'|з|v|∩|x|┬|☆|＠|\,|\=|ヘ|ｪ|ェ|ｏ|△"
    r"|／|ё|ロ|へ|０|\"|皿|．|3|つ|Å|、|σ|～|＝|U|\@|Θ|'|u|c|┳|〃|ﾛ|ｴ|q"
    r"|Ｏ|３|∪|ヽ|┏|エ|′|＋|〇|ρ|Ｕ|‐|A|┓|っ|ｖ|∧|曲|Ω|∂|■|､|\:|ˇ|p|i"
    r"|ο|⊃|〓|Q|人|口|ι|Ａ|×|）|―|m|V|＊|ﾍ|\?|э|ｑ|（|，|P|┰|π|δ|ｗ|ｐ"
    r"|★|I|┯|ｃ|≡|⊂|∋|L|炎|З|ｕ|ｍ|ｉ|⊥|◆|゛|w|益|一|│|о|ж|б|μ|Φ|Δ"
    r"|→|ゞ|j|\\|\t|θ|ｘ|∈|∞|\"|‥|¨|ﾞ|y|e|\]|8|凵|О|λ|メ|し|Ｌ|†|∵"
    r"|←|〒|▲|\[|Y|\!|┛|с|υ|ν|Σ|Α|う|Ｉ|Ｃ|◯|∠|∨|↑|￥|♀|」|\"|〆|ﾊ"
    r"|n|l|d|b|X|ó|Ő|Å|癶|乂|工|ш|ч|х|н|Ч|Ц|Л|ψ|Ψ|Ο|Λ|Ι|ヮ|ム|ハ|テ|コ"
    r"|す|ｙ|ｎ|ｌ|ｊ|Ｖ|Ｑ|√|≪|⊇|⊆|＄|″|♂|±|｜|ヾ|？|：|ﾝ|ｮ|f|\%"
    r"|ò|å|冫|冖|丱|个|凸|┗|┼|ц|п|Ш|А|φ|τ|η|ζ|β|α|Γ|ン|ワ|ゥ|ぁ|ｚ|ｒ"
    r"|ｋ|ｄ|ｂ|Ｘ|Ｐ|Ｈ|Ｄ|８|♪|≫|↓|＆|「|［|々|仝|!|ﾒ|ｼ|｣"
)
RE_EMOTICON = re.compile(f"({_BRACKET})([{_EMOTICON_CHARS}]{{3,}}).*")
RE_POS_INTERJECTION = re.compile("感動|フィラー")
RE_MIDAS = re.compile(r"^(?:て|ね)(?:え|ぇ)$")

# Fuzzy emoteme (1.5): collapse any run of the same character longer than 2
# down to exactly 2 before scanning, so やばーーーい normalises to やばーーい
# (length-2 ー) and matches emotemes/dict entries written with one or two ー.
RE_REPEATED_CHARS = re.compile(r"(.)\1{2,}", re.UNICODE)

# Threshold above which `analyze_batch` automatically switches to multiprocessing
# (overridable via the `parallel_threshold` constructor argument).
DEFAULT_PARALLEL_THRESHOLD = 50_000
_MIN_CONTENT_LEN = 2


# ---------------------------------------------------------------------------
# Cache version — bump whenever the lemma-build logic or POS set changes so
# stale pickles from an older mlask version are not silently reused.
_CACHE_VERSION = 4


def _detect_mecabrc() -> str:
    try:
        result = subprocess.run(
            ["mecab-config", "--sysconfdir"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return f"-r {result.stdout.strip()}/mecabrc"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    for path in ["/opt/homebrew/etc/mecabrc", "/usr/local/etc/mecabrc", "/etc/mecabrc"]:
        if Path(path).exists():
            return f"-r {path}"
    return ""


def _cache_dir() -> Path:
    """OS-appropriate cache directory for the analyzer's lemma table."""
    base = os.environ.get("MLASK_CACHE_DIR")
    if base:
        return Path(base)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "mlask_official"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "mlask_official"


def _hash_files(paths: list[Path]) -> str:
    """MD5 of file contents (NOT mtimes) — robust to cp/rsync touching mtimes
    without changing data, and to mtime-only edits like `touch`."""
    h = hashlib.md5()
    for p in sorted(paths):
        h.update(p.name.encode("utf-8"))
        h.update(p.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Tokeniser backends
#
# The analyzer is parametrised on a tokeniser callable that returns
#     [(surface, pos, lemma), ...]
# This lets v0.5 transparently swap between mecab-python3 + IPADIC (default)
# and fugashi + UniDic (better verb-boundary coverage for inflected forms).


class _MecabBackend:
    """mecab-python3 + IPADIC.  Behaviour matches ML-Ask 4.x exactly."""

    name = "mecab"

    def __init__(self, mecab_arg: str = ""):
        import MeCab  # local import so fugashi-only installs still work
        if not mecab_arg:
            mecab_arg = _detect_mecabrc()
        self._tagger = MeCab.Tagger(mecab_arg)
        self._tagger.parse("")  # warm up

    def fingerprint(self) -> str:
        # Use stable dictionary attributes (filename, version, charset, size)
        # — the raw SWIG repr embeds a memory address and changes each run,
        # which broke the lemma cache before this fix.
        try:
            di = self._tagger.dictionary_info()
            return (
                f"mecab|{getattr(di, 'filename', '')}|"
                f"{getattr(di, 'version', '')}|"
                f"{getattr(di, 'charset', '')}|"
                f"{getattr(di, 'size', '')}"
            )
        except Exception:
            return "mecab|unknown"

    def parse(self, text: str) -> list[tuple[str, str, str]]:
        """Parse `text` and return [(surface, pos, lemma), ...].

        Handles both MeCab output formats transparently:

        * **IPADIC** (classic, comma-separated features):
              ``今日\\t名詞,一般,*,*,*,*,今日,キョウ,キョウ``
          → ``row[0]=surface``, ``row[1]=comma-separated feature list``.
          Top-level POS at feats[0], lemma at feats[6].

        * **UniDic** (Homebrew default since 2024; tab-separated columns):
              ``今日\\tキョー\\tキョウ\\t今日\\t名詞-普通名詞-副詞可能\\t…``
          → ``row[0]=surface``, ``row[1+]=tab-separated columns``.
          POS at row[4] (hyphen-joined top→sub→sub); lemma at row[3].
        """
        out = []
        for line in self._tagger.parse(text).splitlines():
            row = line.split("\t")
            if len(row) < 2:
                continue
            surface = row[0]
            if surface == "EOS":
                continue

            if len(row) >= 5:
                # UniDic-style: POS is in row[4] as hyphen-joined string.
                # Take the first segment so it matches our _CONTENT_POS set
                # (which uses top-level Japanese POS labels like 名詞 / 動詞).
                pos_full = row[4] or ""
                pos = pos_full.split("-", 1)[0] if pos_full else ""
                lemma = row[3] or surface
            else:
                # IPADIC-style: features are comma-separated in row[1].
                feats = row[1].split(",")
                if len(feats) > 7:
                    pos, lemma = feats[0], feats[6]
                elif len(feats) <= 1:
                    continue
                else:
                    pos, lemma = feats[0], surface

            if not pos:
                continue
            lemma = lemma if (lemma and lemma != "*") else surface
            out.append((surface, pos, lemma))
        return out


class _FugashiBackend:
    """fugashi + UniDic (opt-in via ``MLAskOfficial(backend='fugashi')``).

    UniDic has finer verb-boundary handling and a more consistent lemma
    column, eliminating some IPADIC misparses (1.3 in IMPROVEMENTS.md).
    """

    name = "fugashi"

    def __init__(self, mecab_arg: str = ""):
        try:
            import fugashi  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "The fugashi backend is opt-in. Install it with: "
                "pip install 'mlask-official[fugashi]'"
            ) from e
        import fugashi
        self._tagger = fugashi.Tagger() if not mecab_arg else fugashi.Tagger(mecab_arg)
        _ = list(self._tagger("ウォームアップ"))

    def fingerprint(self) -> str:
        return f"fugashi|{getattr(self._tagger.dictionary_info, '__str__', str)()}"

    def parse(self, text: str) -> list[tuple[str, str, str]]:
        out = []
        for tok in self._tagger(text):
            f = tok.feature
            pos = getattr(f, "pos1", None) or getattr(f, "pos", "") or ""
            # UniDic lemmas live in `lemma`; fall back to surface for unknowns
            lemma = getattr(f, "lemma", None) or tok.surface
            if not pos:
                continue
            out.append((tok.surface, pos, lemma))
        return out


# ---------------------------------------------------------------------------
# Analyzer

class MLAskOfficial:
    """High-performance Japanese emotion analyzer — ML-Ask Official v0.5.

    Parameters
    ----------
    mecab_arg : str
        Arguments passed to the underlying tokeniser.  Auto-detected for MeCab.
    backend : {"mecab", "fugashi"}
        Tokeniser backend.  ``"mecab"`` (default) is mecab-python3 + IPADIC,
        matching pymlask and the original Perl ML-Ask.  ``"fugashi"`` uses
        UniDic via fugashi for finer verb-boundary handling.
    use_cache : bool
        If True (default), cache the lemmatised dictionary on disk to skip
        re-tokenising ~4,700 entries at every cold start.  Invalidated by file
        content (MD5) — safe under file copies that change mtime.
    use_dependency_cvs : bool
        If True, also apply GiNZA-based dependency-tree CVS detection for
        long-distance negation (``彼が悲しそうなのは本当ではない``).  Requires
        ``pip install 'mlask-official[deps]'``.
    fuzzy_emoteme : bool
        Collapse runs of the same character longer than 2 down to 2 before
        emoteme scanning (``やばーーーい`` → ``やばーい``).  Default True.
    parallel_threshold : int
        Sentence count above which ``analyze_batch`` switches to
        multiprocessing automatically.  Default 50,000.
    workers : int or None
        Worker process count for multiprocessing batches.  None = ``os.cpu_count()``.
    """

    def __init__(
        self,
        mecab_arg: str = "",
        *,
        backend: str = "mecab",
        use_cache: bool = True,
        use_dependency_cvs: bool = False,
        fuzzy_emoteme: bool = True,
        parallel_threshold: int = DEFAULT_PARALLEL_THRESHOLD,
        workers: Optional[int] = None,
    ):
        if backend == "mecab":
            self._backend = _MecabBackend(mecab_arg)
        elif backend == "fugashi":
            self._backend = _FugashiBackend(mecab_arg)
        else:
            raise ValueError(f"Unknown backend: {backend!r}. Use 'mecab' or 'fugashi'.")

        self.backend_name: str = self._backend.name
        self.fuzzy_emoteme = fuzzy_emoteme
        self.parallel_threshold = parallel_threshold
        self.workers = workers
        self._mecab_arg = mecab_arg
        self._use_cache = use_cache

        # Public for tests / advanced users
        self.mecab = getattr(self._backend, "_tagger", None)

        self._load_dictionaries()
        self._build_emotion_automata(use_cache=use_cache)
        self._build_emoteme_automaton()

        # Optional GiNZA pipeline for dependency-tree CVS (1.4).
        self._ginza_nlp = None
        if use_dependency_cvs:
            self._ginza_nlp = _load_ginza()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _load_dictionaries(self) -> None:
        data_dir = Path(__file__).parent
        self.emotion_dicts: dict[str, list[str]] = {}
        for emotion in EMOTIONS:
            words: list[str] = []
            # Original Nakamura + Wang/Isomura
            base = data_dir / "emotions" / f"{emotion}_uncoded.txt"
            words.extend(
                w.strip() for w in base.read_text("utf-8").splitlines() if w.strip()
            )
            # v0.5 modern additions (emoji, kaomoji, gyaru-go, katakana borrowings)
            extra = data_dir / "emotions" / f"{emotion}_modern.txt"
            if extra.exists():
                words.extend(
                    w.strip() for w in extra.read_text("utf-8").splitlines()
                    if w.strip() and not w.strip().startswith("#")
                )
            # Dedupe but preserve order
            seen = set()
            self.emotion_dicts[emotion] = [
                w for w in words if not (w in seen or seen.add(w))
            ]

        emoteme_dir = data_dir / "emotemes"
        self.emoteme_words = [
            w.strip()
            for w in (emoteme_dir / "emotemes_all.txt").read_text("utf-8").splitlines()
            if w.strip()
        ]
        self.interjection_words = [
            w.strip()
            for w in (emoteme_dir / "interjections_uncoded.txt").read_text("utf-8").splitlines()
            if w.strip()
        ]

    # ------------------------------------------------------------------
    # Lemma cache (1.2) — saves ~25 ms cold start by skipping MeCab on ~4700
    # dictionary entries.  Cache key includes:
    #   - cache format version (bumped on any logic change)
    #   - backend name + tagger fingerprint
    #   - MD5 of every dict file
    # ------------------------------------------------------------------

    def _cache_key(self) -> str:
        data_dir = Path(__file__).parent
        paths = sorted(
            list((data_dir / "emotions").glob("*.txt"))
            + list((data_dir / "emotemes").glob("*.txt"))
        )
        h = hashlib.md5()
        h.update(str(_CACHE_VERSION).encode())
        h.update(self._backend.fingerprint().encode())
        for p in paths:
            h.update(p.name.encode("utf-8"))
            h.update(p.read_bytes())
        return h.hexdigest()

    def _cache_path(self) -> Path:
        return _cache_dir() / f"lemma-{self._cache_key()}.pkl"

    def _load_cached_lemmas(self) -> Optional[dict]:
        if not self._use_cache:
            return None
        path = self._cache_path()
        if not path.exists():
            return None
        try:
            with path.open("rb") as f:
                payload = pickle.load(f)
        except Exception as e:
            warnings.warn(f"mlask-official: failed to load lemma cache: {e}",
                          RuntimeWarning, stacklevel=2)
            return None
        # Refuse to use an empty cache.  If this file got written by a
        # broken MeCab install in a previous run, the failure would be
        # invisible (analyzer constructs cleanly but every analyze() crashes
        # with "Not an Aho-Corasick automaton yet").  Better to ignore the
        # bad cache and rebuild — and remove the poisoned file.
        if not payload or not payload.get("full_index"):
            warnings.warn(
                f"mlask-official: cache file at {path} is empty — likely written "
                "by a previous broken MeCab build. Removing and rebuilding.",
                RuntimeWarning, stacklevel=2,
            )
            try:
                path.unlink()
            except OSError:
                pass
            return None
        return payload

    def _save_cached_lemmas(self, payload: dict) -> None:
        if not self._use_cache:
            return
        # Refuse to save an empty index — that would poison every future
        # cold start.  Better to take the build hit again until the user
        # fixes MeCab.
        if not payload.get("full_index"):
            warnings.warn(
                "mlask-official: refusing to cache an empty lemma index "
                "(MeCab returned no tokens for any dictionary entry).",
                RuntimeWarning, stacklevel=2,
            )
            return
        path = self._cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            tmp = path.with_suffix(".tmp")
            with tmp.open("wb") as f:
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
            tmp.replace(path)
        except OSError as e:
            warnings.warn(f"mlask-official: failed to write lemma cache: {e}",
                          RuntimeWarning, stacklevel=2)

    # ------------------------------------------------------------------
    # Tokeniser helpers
    # ------------------------------------------------------------------

    def _parse_tokens(self, text: str) -> list[tuple[str, str, str]]:
        """Return [(surface, pos, lemma), ...] for every token in `text`."""
        return self._backend.parse(text)

    def _entry_lemmas(self, text: str) -> tuple[str, list[str], str, list[str]]:
        """Lemmatise a single dictionary entry.

        Returns (full_str, full_words, content_str, content_words).
        """
        tokens = self._parse_tokens(text)
        full_words: list[str] = []
        content_words: list[str] = []
        for _surface, pos, lemma in tokens:
            full_words.append(lemma)
            if pos in _CONTENT_POS:
                content_words.append(lemma)
        return (
            "".join(full_words),
            full_words,
            "".join(content_words),
            content_words,
        )

    # ------------------------------------------------------------------
    # Automaton construction
    # ------------------------------------------------------------------

    def _build_emotion_automata(self, use_cache: bool = True) -> None:
        """Build full-lemma and content-lemma automata.

        Builds the lemma index from cache when available; otherwise runs the
        tokeniser on every dictionary entry, then writes a fresh pickle for
        subsequent cold starts.
        """
        cached = self._load_cached_lemmas() if use_cache else None
        if cached is not None:
            full_index = cached["full_index"]
            content_index = cached["content_index"]
        else:
            full_index, content_index = self._compute_lemma_indices()
            self._save_cached_lemmas({
                "full_index":    full_index,
                "content_index": content_index,
            })

        # Sanity check: if no entries were indexed at all, MeCab tokenisation
        # failed silently (most often a bad mecabrc or a freshly-installed
        # mecab-python3 that can't find its dictionary).  Raising here is
        # much friendlier than the cryptic
        #   "Not an Aho-Corasick automaton yet"
        # that surfaces on the first analyze() call.
        if not full_index:
            raise RuntimeError(
                "mlask-official: built an empty emotion index.\n"
                "  This means MeCab returned no tokens for the dictionary "
                "entries.\n"
                "  Common causes:\n"
                "    1. mecabrc not auto-detected — pass an explicit one:\n"
                "         MLAskOfficial(mecab_arg='-r /opt/homebrew/etc/mecabrc')\n"
                "       (locate yours via:  mecab-config --sysconfdir)\n"
                "    2. mecab-ipadic (or another dictionary) is not installed.\n"
                "       Re-install per the README, then verify:\n"
                "         echo 'テスト' | mecab\n"
                "       should show several lines of tokens.\n"
                "    3. Stale lemma cache from a previous broken run.\n"
                "       Force a rebuild:  rm -rf ~/.cache/mlask_official"
            )

        self._emotion_automaton = ahocorasick.Automaton()
        for key, entries in full_index.items():
            self._emotion_automaton.add_word(key, (key, entries))
        self._emotion_automaton.make_automaton()

        if content_index:
            self._content_automaton: Optional[ahocorasick.Automaton] = ahocorasick.Automaton()
            for key, entries in content_index.items():
                self._content_automaton.add_word(key, (key, entries))
            self._content_automaton.make_automaton()
        else:
            self._content_automaton = None

    def _compute_lemma_indices(self) -> tuple[dict, dict]:
        full_index: dict[str, list[tuple[str, list[str]]]] = {}
        content_index: dict[str, list[tuple[str, list[str]]]] = {}

        for emotion, words in self.emotion_dicts.items():
            for raw_word in words:
                full_str, _, content_str, _ = self._entry_lemmas(raw_word)
                if not full_str:
                    continue
                full_index.setdefault(full_str, []).append((raw_word, [emotion]))
                if raw_word != full_str and len(raw_word) >= _MIN_CONTENT_LEN:
                    full_index.setdefault(raw_word, []).append((raw_word, [emotion]))
                if (len(content_str) >= _MIN_CONTENT_LEN
                        and content_str != full_str):
                    content_index.setdefault(content_str, []).append(
                        (raw_word, [emotion])
                    )

        def _merge(index):
            merged = {}
            for key, entries in index.items():
                word_to_classes: dict[str, list[str]] = {}
                for raw, classes in entries:
                    word_to_classes.setdefault(raw, []).extend(classes)
                merged[key] = [
                    (raw, list(dict.fromkeys(cls)))
                    for raw, cls in word_to_classes.items()
                ]
            return merged

        return _merge(full_index), _merge(content_index)

    def _build_emoteme_automaton(self) -> None:
        self._emoteme_automaton = ahocorasick.Automaton()
        for word in self.emoteme_words:
            self._emoteme_automaton.add_word(word, word)
        self._emoteme_automaton.make_automaton()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, text: str) -> dict:
        """Analyse emotion in a Japanese text string.

        Returns a dict with keys ``text, emotion, valence, activation,
        emoticon, intension, intensifier, representative, emotive``.
        """
        text = self._normalize(text)
        lemmas = self._lexical_analysis(text)
        emoticon = self._find_emoticon(text)
        intensifier = self._find_emotem(lemmas, emoticon)
        intension = sum(len(v) for v in intensifier.values())
        emotive = bool(intensifier)
        emotions = self._find_emotion(lemmas, original_text=text)

        base = {
            "text": text,
            "emoticon": emoticon or None,
            "intension": intension,
            "intensifier": intensifier,
            "emotive": emotive,
        }

        if emotions:
            return {
                **base,
                "emotion": emotions,
                "valence": self._estimate_valence(emotions),
                "activation": self._estimate_activation(emotions),
                "representative": self._get_representative(emotions),
            }
        return {**base, "emotion": None}

    def analyze_batch(
        self,
        texts: Union[list[str], tuple[str, ...]],
        *,
        parallel: Optional[bool] = None,
        workers: Optional[int] = None,
    ) -> list[dict]:
        """Analyse a list of texts.

        Switches to multiprocessing automatically when ``len(texts) >=
        parallel_threshold`` (50,000 by default).  Pass ``parallel=True/False``
        to force.
        """
        n = len(texts)
        if parallel is None:
            parallel = n >= self.parallel_threshold
        if parallel and n > 0:
            return self.analyze_parallel(texts, workers=workers)
        return [self.analyze(t) for t in texts]

    def analyze_stream(self, texts: Iterable[str]) -> Iterator[dict]:
        """Generator API for very large corpora — yields one result at a time
        without holding every result in memory."""
        for text in texts:
            if text is None:
                continue
            yield self.analyze(text)

    def analyze_parallel(
        self,
        texts: Union[list[str], tuple[str, ...]],
        *,
        workers: Optional[int] = None,
    ) -> list[dict]:
        """Process ``texts`` across multiple processes.

        MeCab itself is not fork-safe, but each worker process gets its own
        ``MLAskOfficial`` instance, so this is safe.  Useful for corpora
        above ~50,000 sentences.
        """
        if not texts:
            return []
        n_workers = workers or self.workers or os.cpu_count() or 2
        n_workers = max(1, min(n_workers, len(texts)))

        # Use 'spawn' on macOS to avoid MeCab-in-fork issues.
        ctx = mp.get_context("spawn")
        init_kwargs = {
            "mecab_arg": self._mecab_arg,
            "backend": self.backend_name,
            "use_cache": True,
            "fuzzy_emoteme": self.fuzzy_emoteme,
        }
        with ctx.Pool(
            n_workers,
            initializer=_pool_init,
            initargs=(init_kwargs,),
        ) as pool:
            chunksize = max(1, len(texts) // (n_workers * 4))
            return pool.map(_pool_analyze, texts, chunksize=chunksize)

    def format_original(self, result: dict) -> str:
        """Pipe-delimited output compatible with the original Perl ML-Ask."""
        parts = [result["text"], "|emotions:"]
        emotions = result.get("emotion") or {}
        parts.append(f"({len(emotions)})")
        for emo, words in emotions.items():
            tag = emo[:3].upper()
            parts.append(f"|{tag}:{' '.join(words)}")
        if emotions:
            parts.append("||2D|")
            parts.append(result.get("valence", ""))
            parts.append("|")
            parts.append(result.get("activation", ""))
        return "".join(parts)

    # ------------------------------------------------------------------
    # Internal analysis steps
    # ------------------------------------------------------------------

    def _normalize(self, text: str) -> str:
        text = text.replace("!", "！").replace("?", "？")
        if self.fuzzy_emoteme:
            # 1.5 — collapse runs of any single char longer than 2 down to 2.
            text = RE_REPEATED_CHARS.sub(r"\1\1", text)
        return text

    def _lexical_analysis(self, text: str) -> dict:
        lemma_words: list[str] = []
        content_words: list[str] = []
        content_to_lemma_idx: list[int] = []
        interjections: list[str] = []
        no_emotem_parts: list[str] = []
        tokens_full: list[tuple[str, str, str]] = []

        for surface, pos, lemma in self._parse_tokens(text):
            tokens_full.append((surface, pos, lemma))
            li = len(lemma_words)
            lemma_words.append(lemma)
            if pos in _CONTENT_POS:
                content_words.append(lemma)
                content_to_lemma_idx.append(li)
            if RE_POS_INTERJECTION.search(pos) or RE_MIDAS.search(surface):
                interjections.append(surface)
            else:
                no_emotem_parts.append(surface)

        return {
            "lemma_words":          lemma_words,
            "all":                  "".join(lemma_words).replace("*", ""),
            "content_words":        content_words,
            "content_all":          "".join(content_words),
            "content_to_lemma_idx": content_to_lemma_idx,
            "interjections":        interjections,
            "no_emotem":            "".join(no_emotem_parts),
            "tokens":               tokens_full,
        }

    def _find_emoticon(self, text: str) -> list[str]:
        m = RE_EMOTICON.search(text)
        return [m.group(1) + m.group(2)] if m else []

    def _find_emotem(self, lemmas: dict, emoticons: list[str]) -> dict:
        intensifier: dict = {}
        no_emotem = lemmas["no_emotem"]
        found_emo = [w for _, w in self._emoteme_automaton.iter(no_emotem)]
        if found_emo:
            intensifier["emotemes"] = found_emo
        if lemmas["interjections"]:
            intensifier["interjections"] = lemmas["interjections"]
        if emoticons:
            intensifier["emotikony"] = emoticons
        return intensifier

    @staticmethod
    def _boundary_sets(
        words: list[str],
    ) -> tuple[set[int], set[int], dict[int, int]]:
        starts: set[int] = set()
        ends: set[int] = set()
        end_to_idx: dict[int, int] = {}
        pos = 0
        for i, w in enumerate(words):
            starts.add(pos)
            pos += len(w)
            ends.add(pos - 1)
            end_to_idx[pos - 1] = i
        return starts, ends, end_to_idx

    def _scan_automaton(
        self,
        automaton: ahocorasick.Automaton,
        text: str,
        word_starts: set[int],
        word_ends: set[int],
        approximate: bool = False,
        check_cvs: bool = True,
        end_to_word_idx: Optional[dict[int, int]] = None,
        cvs_text: Optional[str] = None,
        cvs_word_end_offsets: Optional[list[int]] = None,
        word_idx_map: Optional[list[int]] = None,
    ) -> dict[str, list[str]]:
        found: dict[str, list[str]] = collections.defaultdict(list)
        suffix = "≈" if approximate else ""
        use_remap = (
            check_cvs
            and end_to_word_idx is not None
            and cvs_text is not None
            and cvs_word_end_offsets is not None
            and word_idx_map is not None
        )

        for end_idx, (key, entries) in automaton.iter(text):
            start_idx = end_idx - len(key) + 1
            if start_idx not in word_starts or end_idx not in word_ends:
                continue

            has_cvs = False
            if use_remap:
                scanned_w_idx = end_to_word_idx[end_idx]
                full_w_idx = word_idx_map[scanned_w_idx]
                full_end_offset = cvs_word_end_offsets[full_w_idx]
                after = cvs_text[full_end_offset + 1:]
                has_cvs = bool(RE_CVS_SUFFIX.match(after))
            elif check_cvs:
                after = text[end_idx + 1:]
                has_cvs = bool(RE_CVS_SUFFIX.match(after))

            for raw_word, emotion_classes in entries:
                label = raw_word + suffix
                for cls in emotion_classes:
                    if has_cvs:
                        for new_cls in CVS_TABLE.get(cls, []):
                            found[new_cls].append(f"{label}*CVS")
                    else:
                        found[cls].append(label)

        return dict(found)

    def _find_emotion(self, lemmas: dict, original_text: str = "") -> Optional[dict]:
        # Pass 1 — full lemma scan
        w_starts, w_ends, _ = self._boundary_sets(lemmas["lemma_words"])
        found = self._scan_automaton(
            self._emotion_automaton, lemmas["all"], w_starts, w_ends,
        )

        # Pass 2 — content-lemma scan (remapped CVS)
        if self._content_automaton:
            c_starts, c_ends, c_end_to_idx = self._boundary_sets(
                lemmas["content_words"]
            )
            full_end_offsets: list[int] = []
            pos = 0
            for w in lemmas["lemma_words"]:
                pos += len(w)
                full_end_offsets.append(pos - 1)

            content_found = self._scan_automaton(
                self._content_automaton,
                lemmas["content_all"],
                c_starts,
                c_ends,
                approximate=True,
                check_cvs=True,
                end_to_word_idx=c_end_to_idx,
                cvs_text=lemmas["all"],
                cvs_word_end_offsets=full_end_offsets,
                word_idx_map=lemmas["content_to_lemma_idx"],
            )
            full_raw = {
                w.replace("*CVS", "").replace("≈", "")
                for words in found.values()
                for w in words
            }
            for cls, words in content_found.items():
                for w in words:
                    raw = w.replace("≈", "").replace("*CVS", "")
                    if raw in full_raw:
                        continue
                    if any(
                        raw.startswith(fr) and 1 <= len(raw) - len(fr) <= 2
                        for fr in full_raw
                    ):
                        continue
                    found.setdefault(cls, []).append(w)
                    full_raw.add(raw)

        # Pass 3 — dependency-tree CVS (1.4, opt-in via use_dependency_cvs)
        if self._ginza_nlp is not None and found and original_text:
            found = self._apply_dependency_cvs(found, original_text)

        return dict(found) if found else None

    # --- 1.4 GiNZA dependency-tree CVS ----------------------------------

    def _apply_dependency_cvs(self, found: dict, text: str) -> dict:
        """For each emotion word in `found`, walk the dependency tree from its
        matching token to see whether it is in the scope of a negation.  If
        so, flip the class per CVS_TABLE.

        The regex pass already catches local negation; this pass adds
        long-distance / governing-clause negation that the surface regex misses.
        """
        try:
            doc = self._ginza_nlp(text)
        except Exception as e:
            warnings.warn(f"mlask-official: GiNZA parse failed: {e}",
                          RuntimeWarning, stacklevel=2)
            return found

        # Map every token's lemma to a node so we can do scope traversal
        tok_by_lemma: dict[str, list] = {}
        for tok in doc:
            tok_by_lemma.setdefault(getattr(tok, "lemma_", tok.text), []).append(tok)
            tok_by_lemma.setdefault(tok.text, []).append(tok)

        def _negated(token) -> bool:
            # Walk up the dependency head chain looking for a negation lemma
            seen = set()
            cur = token
            while cur is not None and id(cur) not in seen:
                seen.add(id(cur))
                for child in getattr(cur, "children", []):
                    lem = getattr(child, "lemma_", child.text)
                    if lem in _DEP_CVS_NEG_LEMMAS:
                        return True
                head = getattr(cur, "head", None)
                if head is None or head is cur:
                    break
                cur = head
            return False

        # Rebuild `found` applying dep-CVS where it triggers
        new_found: dict[str, list[str]] = collections.defaultdict(list)
        for cls, words in found.items():
            for w in words:
                if "*CVS" in w:
                    new_found[cls].append(w)   # already handled by surface CVS
                    continue
                raw = w.replace("≈", "")
                token_hits = tok_by_lemma.get(raw, [])
                if any(_negated(t) for t in token_hits):
                    for new_cls in CVS_TABLE.get(cls, []):
                        new_found[new_cls].append(f"{w}*depCVS")
                else:
                    new_found[cls].append(w)
        return dict(new_found)

    # ------------------------------------------------------------------

    def _estimate_valence(self, emotions: dict) -> str:
        pos = sum(1 for e in emotions if VALENCE.get(e) == "P")
        neg = sum(1 for e in emotions if VALENCE.get(e) == "N")
        if pos == neg:
            return "NEUTRAL"
        prefix = "mostly_" if pos > 0 and neg > 0 else ""
        return prefix + ("POSITIVE" if pos > neg else "NEGATIVE")

    def _estimate_activation(self, emotions: dict) -> str:
        active = sum(1 for e in emotions if ACTIVATION.get(e) == "A")
        passive = sum(1 for e in emotions if ACTIVATION.get(e) == "P")
        if active == passive:
            return "NEUTRAL"
        prefix = "mostly_" if active > 0 and passive > 0 else ""
        return prefix + ("ACTIVE" if active > passive else "PASSIVE")

    @staticmethod
    def _get_representative(emotions: dict) -> tuple:
        return sorted(
            emotions.items(),
            key=lambda x: len(x[1][0].replace("≈", "").replace("*CVS", "").replace("*depCVS", "")),
            reverse=True,
        )[0]


# ---------------------------------------------------------------------------
# Multiprocessing helpers — module-level so they are picklable by spawn pools.

_pool_analyzer: Optional[MLAskOfficial] = None


def _pool_init(init_kwargs: dict) -> None:
    global _pool_analyzer
    _pool_analyzer = MLAskOfficial(**init_kwargs)


def _pool_analyze(text: str) -> dict:
    assert _pool_analyzer is not None
    return _pool_analyzer.analyze(text)


# ---------------------------------------------------------------------------
# GiNZA loader (1.4) — kept separate so it doesn't hit the import path for
# users who don't enable dependency CVS.

def _load_ginza():
    try:
        import spacy
    except ImportError as e:
        raise ImportError(
            "Dependency-tree CVS requires GiNZA. Install with: "
            "pip install 'mlask-official[deps]'"
        ) from e
    for model_name in ("ja_ginza", "ja_ginza_electra"):
        try:
            return spacy.load(model_name)
        except (OSError, ImportError):
            continue
    raise RuntimeError(
        "ja_ginza model not found. Install with: pip install ja-ginza"
    )
