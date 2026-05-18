# -*- coding: utf-8 -*-
"""Candidate emotive-expression extraction — v0.5 productisation of the
Wang & Isomura (2024) corpus-mining method (IMPROVEMENTS.md §2.1).

The pipeline is intentionally simple — POS-pattern mining + frequency
filtering + co-occurrence with known emotion words — but matches the spirit
of the published method and outputs human-reviewable TSV.

Workflow:

1. Tokenise each corpus sentence with the chosen backend.
2. Analyse with MLAskOfficial — record (input, detected_emotion) pairs.
3. Scan tokens for POS *patterns* that frequently co-occur with each
   emotion (adjective stem, noun + する, verb te-form + たまらない, etc.).
4. Return candidates ranked by frequency, with emotion label and example
   contexts for manual review.
"""
from __future__ import annotations

import collections
import re
from pathlib import Path
from typing import Iterable

from mlask_official._analyzer import MLAskOfficial, EMOTIONS, _CONTENT_POS


# POS patterns considered as candidate emotive expressions.  Each entry is
# (pattern_name, predicate_on_pos_sequence) where the predicate returns True
# if the pattern matches the (surface, pos, lemma) token sequence.
_PATTERNS: list[tuple[str, callable]] = [
    # Single 形容詞: e.g. やばい / すごい
    ("adj",     lambda toks: len(toks) == 1 and toks[0][1].startswith("形容詞")),
    # 名詞 + な (formal/adjectival use): e.g. 不安な
    ("noun+na", lambda toks: len(toks) == 2 and toks[0][1].startswith("名詞")
                              and toks[1][0] == "な"),
    # 動詞 + たまらない / しょうがない (intensified verb)
    ("v+intens", lambda toks: len(toks) >= 2 and toks[0][1].startswith("動詞")
                                and any(t[2] in ("たまらない", "しょうがない", "やまない")
                                        for t in toks[1:])),
    # Onomatopoeia (副詞, repeated phonology like ワクワク / ドキドキ)
    ("onomato", lambda toks: len(toks) == 1 and toks[0][1].startswith("副詞")
                              and re.match(r"^(.{1,2})\1$", toks[0][0])),
]


def _windows(seq: list, max_len: int) -> Iterable[list]:
    n = len(seq)
    for size in range(1, max_len + 1):
        for i in range(n - size + 1):
            yield seq[i : i + size]


def extract_candidates(
    corpus_path: Path,
    *,
    min_freq: int = 3,
    backend: str = "mecab",
    mecab_arg: str = "",
    max_window: int = 3,
) -> list[tuple[str, str, int, list[str]]]:
    """Return a list of ``(emotion, candidate_phrase, frequency, contexts)``
    for candidate phrases that:

    * Match one of the heuristic POS patterns above,
    * Co-occur in the same sentence as a known emotion word at least
      ``min_freq`` times,
    * Are not already in the dictionary.

    The returned list is sorted by (emotion, descending frequency).
    """
    analyzer = MLAskOfficial(
        mecab_arg=mecab_arg,
        backend=backend,
        use_cache=True,
        fuzzy_emoteme=False,
    )
    known_words: set[str] = {
        w for words in analyzer.emotion_dicts.values() for w in words
    }

    # (emotion, candidate_phrase) -> {freq: int, contexts: list[str]}
    table: dict[tuple[str, str], dict] = collections.defaultdict(
        lambda: {"freq": 0, "contexts": []}
    )

    with corpus_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            sentence = line.strip()
            if not sentence:
                continue
            result = analyzer.analyze(sentence)
            emotions = result.get("emotion") or {}
            if not emotions:
                continue

            # Tokens for pattern scanning
            tokens = analyzer._parse_tokens(sentence)
            content_tokens = [t for t in tokens if t[1] in _CONTENT_POS]

            for window in _windows(content_tokens, max_window):
                if not any(pred(window) for _, pred in _PATTERNS):
                    continue
                phrase = "".join(tok[0] for tok in window)
                if phrase in known_words:
                    continue
                # Assign the phrase to every detected emotion class in this sentence
                for emo in emotions:
                    entry = table[(emo, phrase)]
                    entry["freq"] += 1
                    if len(entry["contexts"]) < 5:
                        entry["contexts"].append(sentence)

    out: list[tuple[str, str, int, list[str]]] = []
    for (emo, phrase), info in table.items():
        if info["freq"] < min_freq:
            continue
        out.append((emo, phrase, info["freq"], info["contexts"]))

    out.sort(key=lambda x: (EMOTIONS.index(x[0]) if x[0] in EMOTIONS else 99,
                            -x[2]))
    return out
