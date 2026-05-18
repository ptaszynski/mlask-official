# -*- coding: utf-8 -*-
"""ML-Ask Official command-line interface (v0.5, IMPROVEMENTS.md §3.2).

Subcommands:

    mlask analyze        Analyse a single sentence (stdin or --text)
    mlask batch          Analyse a file or stdin; output CSV / JSON / pipe
    mlask benchmark      Throughput benchmark
    mlask extract        POS-pattern extraction of emotive expression
                         candidates from a corpus (IMPROVEMENTS.md §2.1)

All commands accept ``--backend mecab|fugashi``.  Run ``mlask --help``.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

import typer

from mlask_official._analyzer import MLAskOfficial, EMOTIONS, EMOTION_LABELS_EN

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="ML-Ask Official — Japanese emotion analysis CLI",
)


# ---------------------------------------------------------------------------
# Helpers

def _make_analyzer(
    backend: str = "mecab",
    mecab_arg: str = "",
    no_cache: bool = False,
    use_dep_cvs: bool = False,
) -> MLAskOfficial:
    return MLAskOfficial(
        mecab_arg=mecab_arg,
        backend=backend,
        use_cache=not no_cache,
        use_dependency_cvs=use_dep_cvs,
    )


def _write_results(
    analyzer: MLAskOfficial,
    results: list[dict],
    fmt: str,
    out: Path | None,
) -> None:
    if fmt == "json":
        payload = []
        for r in results:
            row = {}
            for k, v in r.items():
                if isinstance(v, tuple):
                    row[k] = list(v)
                elif hasattr(v, "items"):
                    row[k] = dict(v)
                else:
                    row[k] = v
            payload.append(row)
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    elif fmt == "pipe":
        text = "\n".join(analyzer.format_original(r) for r in results)
    elif fmt == "csv":
        import csv, io
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["text", "valence", "activation", "representative", "emotive"]
            + list(EMOTIONS)
        )
        for r in results:
            em = r.get("emotion") or {}
            rep = r.get("representative")
            writer.writerow(
                [
                    r.get("text", ""),
                    r.get("valence", ""),
                    r.get("activation", ""),
                    rep[0] if rep else "",
                    "yes" if (em or r.get("emotive")) else "no",
                ]
                + [", ".join(em.get(e, [])) for e in EMOTIONS]
            )
        text = buf.getvalue()
    else:
        raise typer.BadParameter(f"Unknown format: {fmt}")

    if out is None or str(out) == "-":
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        out.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Commands

@app.command()
def analyze(
    text: Optional[str] = typer.Option(
        None, "--text", "-t",
        help="Text to analyse. If omitted, reads from stdin.",
    ),
    fmt: str = typer.Option(
        "json", "--format", "-f",
        help="Output format: json | pipe | csv",
    ),
    backend: str = typer.Option("mecab", help="Tokeniser backend: mecab | fugashi"),
    mecab_arg: str = typer.Option("", help="Arguments passed to MeCab.Tagger."),
    use_dep_cvs: bool = typer.Option(
        False, "--dep-cvs",
        help="Enable GiNZA dependency-tree CVS (long-distance negation).",
    ),
    no_cache: bool = typer.Option(
        False, "--no-cache",
        help="Skip the on-disk lemma cache.",
    ),
) -> None:
    """Analyse a single sentence (`--text "..."` or piped on stdin)."""
    if text is None:
        text = sys.stdin.read()
    text = text.strip()
    if not text:
        raise typer.BadParameter("No text given.")

    analyzer = _make_analyzer(backend, mecab_arg, no_cache, use_dep_cvs)
    _write_results(analyzer, [analyzer.analyze(text)], fmt, None)


@app.command()
def batch(
    file: Optional[Path] = typer.Option(
        None, "--file", "-i",
        help="Input .txt file (one sentence per line). Reads stdin if omitted.",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output file path; '-' or omit for stdout.",
    ),
    fmt: str = typer.Option(
        "csv", "--format", "-f",
        help="Output format: csv | json | pipe",
    ),
    parallel: Optional[bool] = typer.Option(
        None, "--parallel/--no-parallel",
        help="Force multiprocessing on/off (default: auto at 50k sentences).",
    ),
    workers: Optional[int] = typer.Option(
        None, "--workers", "-j",
        help="Multiprocessing worker count (default: os.cpu_count()).",
    ),
    backend: str = typer.Option("mecab", help="Tokeniser backend: mecab | fugashi"),
    mecab_arg: str = typer.Option("", help="Arguments passed to MeCab.Tagger."),
    use_dep_cvs: bool = typer.Option(False, "--dep-cvs"),
    no_cache: bool = typer.Option(False, "--no-cache"),
) -> None:
    """Analyse many sentences from a file or stdin."""
    if file is not None:
        texts = [
            l.strip()
            for l in file.read_text("utf-8").splitlines()
            if l.strip()
        ]
    else:
        texts = [l.strip() for l in sys.stdin.readlines() if l.strip()]
    if not texts:
        raise typer.BadParameter("No input sentences found.")

    analyzer = _make_analyzer(backend, mecab_arg, no_cache, use_dep_cvs)
    t0 = time.perf_counter()
    results = analyzer.analyze_batch(texts, parallel=parallel, workers=workers)
    elapsed = time.perf_counter() - t0
    typer.echo(
        f"[mlask] {len(texts)} sentences in {elapsed*1000:.1f} ms "
        f"({len(texts)/elapsed:.0f}/s, "
        f"backend={analyzer.backend_name})",
        err=True,
    )
    _write_results(analyzer, results, fmt, output)


@app.command()
def benchmark(
    sentences: int = typer.Option(
        10_000, "--sentences", "-n", help="How many sentences to benchmark."
    ),
    backend: str = typer.Option("mecab", help="Tokeniser backend."),
    parallel: bool = typer.Option(False, "--parallel"),
    workers: Optional[int] = typer.Option(None, "--workers", "-j"),
) -> None:
    """Throughput benchmark — runs N copies of a fixed mixed sentence pool."""
    pool = [
        "今日は本当に嬉しかった！",
        "怖くてたまらない。",
        "腹が立つ。頭にくる！",
        "やっとすっきりした。",
        "大好き！ずっと一緒にいたい。",
        "悲しくて泣いてしまった。",
        "彼のことは嫌いではない！",
    ]
    texts = [pool[i % len(pool)] for i in range(sentences)]

    typer.echo(f"[mlask] loading analyzer (backend={backend})…", err=True)
    analyzer = MLAskOfficial(backend=backend)

    typer.echo(f"[mlask] analysing {sentences} sentences "
               f"(parallel={parallel})…", err=True)
    t0 = time.perf_counter()
    if parallel:
        results = analyzer.analyze_parallel(texts, workers=workers)
    else:
        results = analyzer.analyze_batch(texts, parallel=False)
    elapsed = time.perf_counter() - t0
    typer.echo(
        f"[mlask] {sentences} sentences in {elapsed:.2f}s "
        f"= {sentences/elapsed:.0f} sentences/sec",
        err=True,
    )
    n_emotive = sum(1 for r in results if r.get("emotion") or r.get("emotive"))
    typer.echo(f"[mlask] {n_emotive}/{sentences} were classified as emotive", err=True)


@app.command()
def extract(
    corpus: Path = typer.Argument(..., help="Path to a UTF-8 text corpus (one sentence per line)."),
    out: Path = typer.Option(
        Path("extracted_candidates.tsv"), "--output", "-o",
        help="Output TSV path.",
    ),
    min_freq: int = typer.Option(3, help="Minimum frequency for a candidate."),
    backend: str = typer.Option("mecab"),
    mecab_arg: str = typer.Option(""),
) -> None:
    """Extract candidate emotive expressions from a corpus
    (Wang/Isomura method, productised — IMPROVEMENTS.md §2.1)."""
    from mlask_official.extract import extract_candidates  # local import
    candidates = extract_candidates(
        corpus, min_freq=min_freq, backend=backend, mecab_arg=mecab_arg,
    )
    with out.open("w", encoding="utf-8") as f:
        f.write("emotion\tcandidate\tfreq\tcontexts\n")
        for emo, cand, freq, ctx in candidates:
            ctx_join = " | ".join(ctx[:3])  # first 3 context snippets
            f.write(f"{emo}\t{cand}\t{freq}\t{ctx_join}\n")
    typer.echo(
        f"[mlask extract] wrote {len(candidates)} candidates to {out}",
        err=True,
    )


if __name__ == "__main__":
    app()
