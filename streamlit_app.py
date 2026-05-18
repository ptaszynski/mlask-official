# -*- coding: utf-8 -*-
"""
ML-Ask Official v0.5 — Streamlit Web Application
Japanese emotion analysis powered by dual Aho-Corasick automata.

v0.5 UI additions:
  * JA/EN language toggle (i18n.py)
  * Time-series chart when input lines are timestamp-prefixed (5.3)
  * Mobile-responsive layout (5.5)
"""
import io
import json
import math
import re
import sys
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ML-Ask Official",
    page_icon="❤️",
    layout="wide",
    initial_sidebar_state="expanded",
)

sys.path.insert(0, str(Path(__file__).parent))

from mlask_official import (
    EMOTIONS,
    EMOTION_LABELS_EN,
    EMOTION_LABELS_JA,
    RUSSELL_COORDS,
)
from mlask_official.i18n import t, emotion_label, LANGUAGES

# ── Constants ─────────────────────────────────────────────────────────────────

EMOTION_COLORS = {
    "yorokobi": "#FFD700",
    "suki":     "#9ACD32",
    "kowa":     "#3CB371",
    "odoroki":  "#20B2AA",
    "aware":    "#4169E1",
    "iya":      "#9932CC",
    "ikari":    "#DC143C",
    "takaburi": "#FF8C00",
    "haji":     "#8B0057",
    "yasu":     "#ADFF2F",
}

VALENCE_COLORS = {
    "POSITIVE":        "#27ae60",
    "mostly_POSITIVE": "#82c341",
    "NEGATIVE":        "#e74c3c",
    "mostly_NEGATIVE": "#e67e22",
    "NEUTRAL":         "#7f8c8d",
}
ACTIVATION_COLORS = {
    "ACTIVE":         "#3498db",
    "mostly_ACTIVE":  "#5dade2",
    "PASSIVE":        "#9b59b6",
    "mostly_PASSIVE": "#af7ac5",
    "NEUTRAL":        "#7f8c8d",
}

SAMPLE_TEXTS = [
    "彼のことは嫌いではない！",
    "今日は本当に嬉しかった！ありがとう！",
    "怖くてたまらない。",
    "腹が立って仕方がない。頭にくる！",
    "なんてこった！信じられない出来事だ。",
    "恥ずかしくて穴があったら入りたい。",
    "すごく楽しかった！また行きたいな。",
    "悲しくて泣いてしまった。",
    "やっとすっきりした。心が落ち着いた。",
    "大好き！ずっと一緒にいたい。",
]

PLOTLY_CONFIG = {
    "displaylogo": False,
    "toImageButtonOptions": {
        "format": "png", "filename": "mlask_chart", "scale": 2,
    },
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "select2d", "lasso2d",
        "autoScale2d", "resetScale2d", "zoomIn2d", "zoomOut2d",
    ],
}
SERIF_FAMILY = "Source Serif Pro, Source Serif 4, Georgia, serif"

# 5.5 — Mobile-responsive CSS: collapse columns at narrow widths.
MOBILE_CSS = """
<style>
@media (max-width: 768px) {
  .block-container { padding-left: 0.6rem; padding-right: 0.6rem; }
  div[data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 0.5rem; }
  div[data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
  .badge { display:block !important; margin: 4px 0 !important; }
}
</style>
"""


@st.cache_resource(show_spinner="Loading ML-Ask Official (first run only)…")
def load_analyzer(mecab_arg: str = "", backend: str = "mecab"):
    from mlask_official import MLAskOfficial
    return MLAskOfficial(mecab_arg=mecab_arg, backend=backend)


def get_lang() -> str:
    """Read the active language from session_state, falling back to 'en' if the
    stored value is missing or somehow not a recognised language code.

    A defensive cast is necessary because session_state persists across
    Streamlit reruns and even hot-reloads, so stale values from a previous app
    version (or a manual edit) could otherwise crash the sidebar's
    ``LANGUAGES.index(lang)`` call."""
    lang = st.session_state.get("lang", "en")
    if lang not in LANGUAGES:
        lang = "en"
        st.session_state["lang"] = lang
    return lang


def lbl(emo: str) -> str:
    """Localised emotion label."""
    return emotion_label(emo, get_lang())


# ── Time-series detection (5.3) ──────────────────────────────────────────────

_RE_TIMESTAMP = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+\-]\d{2}:?\d{2})?)?)"
    r"[\s\t,;|]+"
)


def split_timestamp(line: str) -> tuple:
    """If `line` starts with an ISO date, return (timestamp_str, rest).
    Otherwise return (None, line)."""
    m = _RE_TIMESTAMP.match(line)
    if m:
        return m.group(1), line[m.end():].strip()
    return None, line


def parse_timestamped_input(lines: list) -> tuple:
    """Return (texts, timestamps_or_empty).  Timestamps are only returned
    when ≥ 70 % of input lines have a recognisable ISO date prefix."""
    timestamps = []
    texts = []
    found_ts = 0
    for line in lines:
        ts_str, body = split_timestamp(line)
        if ts_str:
            try:
                ts = pd.to_datetime(ts_str)
                timestamps.append(ts)
                texts.append(body)
                found_ts += 1
                continue
            except (ValueError, TypeError):
                pass
        timestamps.append(None)
        texts.append(line)
    if found_ts / max(1, len(lines)) >= 0.7:
        return texts, timestamps
    return texts, []


# ── Chart helpers ─────────────────────────────────────────────────────────────

def make_radar_chart(result: dict) -> go.Figure:
    emotion_dict = result.get("emotion") or {}
    values = [len(emotion_dict.get(e, [])) for e in EMOTIONS]
    labels = [lbl(e) for e in EMOTIONS]

    values_closed = values + [values[0]]
    labels_closed = labels + [labels[0]]

    fill_color = "rgba(52, 152, 219, 0.20)"
    line_color = "#3498db"
    valence = result.get("valence", "")
    if valence.endswith("POSITIVE"):
        fill_color = "rgba(39, 174, 96, 0.20)"
        line_color = "#27ae60"
    elif valence.endswith("NEGATIVE"):
        fill_color = "rgba(231, 76, 60, 0.20)"
        line_color = "#e74c3c"

    marker_colors_closed = [EMOTION_COLORS[e] for e in EMOTIONS] + [EMOTION_COLORS[EMOTIONS[0]]]

    fig = go.Figure(
        go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            fillcolor=fill_color,
            line=dict(color=line_color, width=2),
            marker=dict(size=8, color=marker_colors_closed, line=dict(width=1, color="#333")),
            hovertemplate="%{theta}: %{r}<extra></extra>",
        )
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, max(max(values), 1)],
                            tickfont=dict(size=10), gridcolor="#e0e0e0"),
            angularaxis=dict(tickfont=dict(size=11)),
            bgcolor="#fafafa",
        ),
        showlegend=False, margin=dict(l=70, r=70, t=40, b=30),
        height=400, paper_bgcolor="rgba(0,0,0,0)",
        title=dict(text="Plutchik colours" if get_lang() == "en" else "Plutchik 配色",
                   font=dict(size=14, family=SERIF_FAMILY), x=0.5),
    )
    return fig


def _label_position_for_angle(theta_deg: float) -> str:
    t_ = theta_deg % 360
    if   t_ <  22.5: return "middle right"
    elif t_ <  67.5: return "top right"
    elif t_ < 112.5: return "top center"
    elif t_ < 157.5: return "top left"
    elif t_ < 202.5: return "middle left"
    elif t_ < 247.5: return "bottom left"
    elif t_ < 292.5: return "bottom center"
    elif t_ < 337.5: return "bottom right"
    return "middle right"


def make_russell_chart(result: dict) -> go.Figure:
    emotion_dict = result.get("emotion") or {}
    representative = result.get("representative")
    rep_name = representative[0] if representative else None
    n_detected = sum(1 for e in EMOTIONS if emotion_dict.get(e))
    hide_undetected_labels = n_detected >= 3
    lang = get_lang()

    fig = go.Figure()

    quad_labels_en = ["Active Positive", "Active Negative", "Passive Negative", "Passive Positive"]
    quad_labels_ja = ["活性ポジティブ", "活性ネガティブ", "非活性ネガティブ", "非活性ポジティブ"]
    qlabels = quad_labels_ja if lang == "ja" else quad_labels_en
    quad_configs = [
        ( 0,  0,  1,  1, "rgba(255, 200,  50, 0.08)", qlabels[0],  0.75,  0.96),
        (-1,  0,  0,  1, "rgba(220,  50,  50, 0.08)", qlabels[1], -0.75,  0.96),
        (-1, -1,  0,  0, "rgba( 65, 105, 225, 0.08)", qlabels[2], -0.75, -0.96),
        ( 0, -1,  1,  0, "rgba( 50, 205,  50, 0.08)", qlabels[3],  0.75, -0.96),
    ]
    for x0, y0, x1, y1, fc, label, lx, ly in quad_configs:
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                      fillcolor=fc, line=dict(width=0), layer="below")
        fig.add_annotation(x=lx, y=ly, text=f"<i>{label}</i>", showarrow=False,
                           font=dict(size=10, color="#999", family=SERIF_FAMILY), xanchor="center")

    for shape in (
        dict(type="line", x0=-1, y0=0, x1=1, y1=0, line=dict(color="#bbb", width=1, dash="dot")),
        dict(type="line", x0=0, y0=-1, x1=0, y1=1, line=dict(color="#bbb", width=1, dash="dot")),
    ):
        fig.add_shape(**shape)

    for emo in EMOTIONS:
        vx, vy = RUSSELL_COORDS[emo]
        count = len(emotion_dict.get(emo, []))
        detected = count > 0
        color = EMOTION_COLORS[emo]
        is_rep = (emo == rep_name)
        marker_size = (18 + 6 * math.sqrt(count)) if detected else 12
        marker_opacity = 1.0 if detected else 0.22
        marker_symbol = "star" if is_rep else "circle"
        line_width = 3 if is_rep else (2 if detected else 1)
        line_color = "#000" if is_rep else ("#333" if detected else "#ccc")
        label = lbl(emo)
        show_label = detected or not hide_undetected_labels
        angle_deg = math.degrees(math.atan2(vy, vx))
        textpos = _label_position_for_angle(angle_deg)

        fig.add_trace(go.Scatter(
            x=[vx], y=[vy],
            mode="markers+text" if show_label else "markers",
            marker=dict(size=marker_size, color=color if detected else "white",
                        opacity=marker_opacity, symbol=marker_symbol,
                        line=dict(color=line_color, width=line_width)),
            text=[label] if show_label else None,
            textposition=textpos,
            textfont=dict(size=11 if detected else 9,
                          color="#222" if detected else "#999",
                          family=SERIF_FAMILY),
            hovertemplate=(
                f"<b>{label}</b><br>"
                f"Valence: {vx:+.2f}<br>"
                f"Arousal: {vy:+.2f}<br>"
                + (f"Detected: {count}" if detected else
                   ("Not detected" if lang == "en" else "未検出"))
                + ("<br>★ " + ("Representative" if lang == "en" else "代表") if is_rep else "")
                + "<extra></extra>"
            ),
            showlegend=False,
        ))

        if detected and count > 1:
            fig.add_annotation(x=vx, y=vy, text=f" ×{count}", showarrow=False,
                               font=dict(size=9, color="#222"),
                               xanchor="left", yanchor="middle",
                               xshift=int(marker_size // 2) + 2)

    title_en = "Russell's 2D Circumplex Model of Affect"
    title_ja = "Russell 感情円環モデル（2次元）"
    fig.update_layout(
        xaxis=dict(
            range=[-1.25, 1.25],
            title=dict(text=("← Negative   Valence   Positive →   (−1 … +1)" if lang == "en"
                              else "← ネガティブ   感情極性   ポジティブ →   (−1 … +1)"),
                       font=dict(size=12, family=SERIF_FAMILY), standoff=18),
            zeroline=False, showgrid=False, tickvals=[-1, -0.5, 0, 0.5, 1],
            scaleanchor="y", scaleratio=1,
        ),
        yaxis=dict(
            range=[-1.25, 1.25],
            title=dict(text=("← Passive   Arousal   Active →   (−1 … +1)" if lang == "en"
                              else "← 非活性   覚醒度   活性 →   (−1 … +1)"),
                       font=dict(size=12, family=SERIF_FAMILY), standoff=18),
            zeroline=False, showgrid=False, tickvals=[-1, -0.5, 0, 0.5, 1],
        ),
        height=540, margin=dict(l=90, r=60, t=60, b=90),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fafafa",
        title=dict(text=title_ja if lang == "ja" else title_en,
                   font=dict(size=15, family=SERIF_FAMILY), x=0.5),
    )
    return fig


def _short_x_label(i: int, text: str, max_chars: int = 10) -> str:
    snippet = text[:max_chars] + ("…" if len(text) > max_chars else "")
    return f"{i+1}. {snippet}"


def make_bar_chart(results: list, texts: list) -> go.Figure:
    x_short = [_short_x_label(i, txt) for i, txt in enumerate(texts)]
    data = []
    for emo in EMOTIONS:
        counts = [len((r.get("emotion") or {}).get(emo, [])) for r in results]
        data.append(go.Bar(
            name=lbl(emo),
            x=x_short, y=counts, customdata=list(texts),
            marker_color=EMOTION_COLORS[emo],
            hovertemplate=("<b>%{x}</b><br>"
                           + ("Sentence" if get_lang() == "en" else "文") + ": %{customdata}<br>"
                           + f"{lbl(emo)}: " + "%{y}<extra></extra>"),
        ))
    fig = go.Figure(data=data)
    fig.update_layout(
        barmode="stack",
        xaxis=dict(tickangle=-30, tickfont=dict(size=10, family="Menlo, Consolas, monospace"),
                   title=dict(text=("Sentence (hover for full text)" if get_lang() == "en"
                                    else "文番号（ホバーで全文表示）"),
                              font=dict(family=SERIF_FAMILY, size=11))),
        yaxis=dict(title=dict(text=("Emotion word count" if get_lang() == "en" else "感情語数"),
                              font=dict(family=SERIF_FAMILY))),
        legend=dict(orientation="h", y=-0.40, font=dict(size=10)),
        height=420, margin=dict(l=40, r=20, t=30, b=130),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fafafa",
        title=dict(text=("Per-sentence emotion-word counts" if get_lang() == "en"
                         else "文ごとの感情語数"),
                   font=dict(size=13, family=SERIF_FAMILY), x=0.5),
    )
    return fig


def make_emotion_heatmap(results: list, texts: list) -> go.Figure:
    z = []
    annotations = []
    y_labels = []
    full_texts = []
    for i, (txt, r) in enumerate(zip(texts, results)):
        emo_dict = r.get("emotion") or {}
        row = [len(emo_dict.get(e, [])) for e in EMOTIONS]
        z.append(row)
        snippet = txt[:10] + ("…" if len(txt) > 10 else "")
        y_label = f"{i+1:>3}. {snippet}"
        y_labels.append(y_label)
        full_texts.append(txt)
        for j, count in enumerate(row):
            if count > 0:
                annotations.append(dict(
                    x=lbl(EMOTIONS[j]), y=y_label, text=str(count),
                    showarrow=False,
                    font=dict(size=10, color="#222" if count < 3 else "white"),
                ))

    n_sentences = len(texts)
    height = min(800, max(280, 26 * n_sentences + 120))
    zmax = max(1, max((max(row) for row in z), default=1))
    customdata = [[ft] * len(EMOTIONS) for ft in full_texts]

    fig = go.Figure(go.Heatmap(
        z=z, x=[lbl(e) for e in EMOTIONS], y=y_labels, customdata=customdata,
        colorscale="YlOrRd", zmin=0, zmax=zmax,
        hovertemplate=("<b>%{y}</b><br>"
                       + ("Sentence" if get_lang() == "en" else "文") + ": %{customdata}<br>"
                       + "%{x}: %{z}<extra></extra>"),
        colorbar=dict(title=dict(text=("words" if get_lang() == "en" else "語数"),
                                 side="right"), thickness=14),
        xgap=1, ygap=1,
    ))
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=70, b=80),
        xaxis=dict(tickangle=-30, side="top",
                   tickfont=dict(size=11, family=SERIF_FAMILY)),
        yaxis=dict(autorange="reversed",
                   tickfont=dict(size=10, family="Menlo, Consolas, monospace")),
        paper_bgcolor="rgba(0,0,0,0)", annotations=annotations,
        title=dict(
            text=(f"Emotion × sentence heatmap ({n_sentences} sentences)" if get_lang() == "en"
                  else f"感情×文 ヒートマップ（{n_sentences} 文）"),
            font=dict(size=14, family=SERIF_FAMILY), x=0.5,
        ),
    )
    return fig


def make_timeseries_chart(results: list, timestamps: list) -> go.Figure:
    """5.3 — per-emotion sentence-count over time."""
    df = pd.DataFrame({
        "ts": pd.to_datetime(timestamps),
        **{emo: [len((r.get("emotion") or {}).get(emo, [])) > 0 for r in results]
           for emo in EMOTIONS},
    }).dropna(subset=["ts"]).sort_values("ts")

    span = df["ts"].max() - df["ts"].min()
    if span.total_seconds() < 3600:        freq = "1min"
    elif span.total_seconds() < 86400:     freq = "10min"
    elif span.total_seconds() < 86400 * 30: freq = "1h"
    else:                                   freq = "1D"
    agg = df.set_index("ts").resample(freq).sum(numeric_only=True).reset_index()

    fig = go.Figure()
    for emo in EMOTIONS:
        fig.add_trace(go.Scatter(
            x=agg["ts"], y=agg[emo], name=lbl(emo),
            mode="lines+markers",
            line=dict(color=EMOTION_COLORS[emo], width=2),
            marker=dict(size=5),
            hovertemplate="%{x|%Y-%m-%d %H:%M}<br>" + f"{lbl(emo)}: " + "%{y}<extra></extra>",
        ))
    fig.update_layout(
        title=dict(text=t("trend_title", get_lang()),
                   font=dict(size=14, family=SERIF_FAMILY), x=0.5),
        xaxis=dict(title=dict(text="time" if get_lang() == "en" else "時刻",
                              font=dict(family=SERIF_FAMILY))),
        yaxis=dict(title=dict(text="sentence count" if get_lang() == "en" else "文数",
                              font=dict(family=SERIF_FAMILY))),
        legend=dict(orientation="h", y=-0.25, font=dict(size=10)),
        height=420, margin=dict(l=60, r=20, t=50, b=80),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fafafa",
    )
    return fig


# ── Result rendering ──────────────────────────────────────────────────────────

def render_badges(result: dict) -> None:
    lang = get_lang()
    valence = result.get("valence") or "—"
    activation = result.get("activation") or "—"
    val_color = VALENCE_COLORS.get(valence, "#7f8c8d")
    act_color = ACTIVATION_COLORS.get(activation, "#7f8c8d")
    valence_label = "Valence" if lang == "en" else "感情極性"
    activation_label = "Activation" if lang == "en" else "活性度"
    st.markdown(
        f"""<style>.badge{{display:inline-block;padding:6px 14px;border-radius:20px;
        color:#fff;font-weight:700;font-size:15px;margin:4px 6px;letter-spacing:.5px}}</style>
        <span class="badge" style="background:{val_color}">{valence_label}: {valence}</span>
        <span class="badge" style="background:{act_color}">{activation_label}: {activation}</span>""",
        unsafe_allow_html=True,
    )


def render_emotion_details(result: dict) -> None:
    lang = get_lang()
    emotion_dict = result.get("emotion") or {}
    if not emotion_dict:
        st.info(t("no_emotion_words", lang))
        return

    rep = result.get("representative")
    if rep:
        rep_name, rep_words = rep
        st.markdown(
            f"**{t('representative_label', lang)}** `{rep_name}` — "
            f"*{lbl(rep_name)}* "
            f"(`{'`, `'.join(rep_words)}`)"
        )
        st.caption(t("representative_caption", lang))

    st.markdown(t("detected_words", lang))
    cols = st.columns(min(len(emotion_dict), 3))
    neg_suffix = t("negated_suffix", lang)
    pstrip_suffix = t("particle_stripped_suffix", lang)
    for idx, (emo, words) in enumerate(emotion_dict.items()):
        color = EMOTION_COLORS.get(emo, "#888")
        with cols[idx % len(cols)]:
            cvs_words    = [w for w in words if "*CVS" in w or "*depCVS" in w]
            approx_words = [w for w in words if "≈" in w and "*CVS" not in w and "*depCVS" not in w]
            plain_words  = [w for w in words if "≈" not in w and "*CVS" not in w and "*depCVS" not in w]
            parts = []
            if plain_words:
                parts.append("  ".join(f"`{w}`" for w in plain_words))
            if approx_words:
                parts.append("  ".join(f"`{w}` {pstrip_suffix}" for w in approx_words))
            if cvs_words:
                parts.append("  ".join(f"`{w}` {neg_suffix}" for w in cvs_words))
            st.markdown(
                f'<div style="border-left:4px solid {color};padding:8px 12px;'
                f'margin:4px 0;background:#f9f9f9;border-radius:4px;color:#212529;">'
                f"<strong>{emo}</strong><br/>"
                f"<small style='color:#495057;'>{lbl(emo)}</small><br/>"
                f"{'<br/>'.join(parts)}</div>",
                unsafe_allow_html=True,
            )


def _render_no_emotion(result: dict) -> None:
    lang = get_lang()
    emotive = result.get("emotive", False)
    intensifier = result.get("intensifier") or {}
    emoticon = result.get("emoticon") or []
    if emotive:
        found_parts = []
        if intensifier.get("emotemes"):
            emos = intensifier["emotemes"]
            label = "emoteme(s)" if lang == "en" else "感情語"
            found_parts.append(f"{len(emos)} {label}: " +
                               " ".join(f"`{e}`" for e in dict.fromkeys(emos)))
        if intensifier.get("interjections"):
            label = "interjection(s)" if lang == "en" else "感動詞"
            found_parts.append(f"{label}: " +
                               " ".join(f"`{i}`" for i in intensifier["interjections"]))
        if intensifier.get("emotikony") or emoticon:
            ec = intensifier.get("emotikony", emoticon)
            label = "emoticon(s)" if lang == "en" else "顔文字"
            found_parts.append(f"{label}: " + " ".join(f"`{e}`" for e in ec))
        detail = "  ·  ".join(found_parts) if found_parts else ""
        st.markdown(
            f"<div style='padding:12px 16px;border-radius:8px;"
            f"background:#fff8e1;border-left:5px solid #FF8C00;margin-bottom:8px;color:#212529;'>"
            f"<strong>{t('emotive_banner_title', lang)}</strong> — {t('emotive_body', lang)}<br/>"
            f"<small style='color:#495057;'>{t('emotive_caption', lang)}</small>"
            + (f"<br/><small style='color:#495057;'>{detail}</small>" if detail else "")
            + "</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div style='padding:12px 16px;border-radius:8px;"
            f"background:#f5f5f5;border-left:5px solid #9E9E9E;margin-bottom:8px;color:#212529;'>"
            f"<strong>{t('non_emotive_banner_title', lang)}</strong> — {t('non_emotive_body', lang)}<br/>"
            f"<small style='color:#495057;'>{t('non_emotive_caption', lang)}</small>"
            f"</div>", unsafe_allow_html=True)


def render_intensifiers(result: dict) -> None:
    intensifier = result.get("intensifier") or {}
    emoticon = result.get("emoticon") or []
    intension = result.get("intension", 0)
    if not intensifier and not emoticon:
        return
    parts = []
    if emoticon:
        parts.append(f"**Emoticons:** {' '.join(f'`{e}`' for e in emoticon)}")
    for kind, items in intensifier.items():
        parts.append(f"**{kind.capitalize()}:** {' '.join(f'`{i}`' for i in items)}")
    if intension:
        parts.append(f"**Intension level:** {intension}")
    st.markdown("  ·  ".join(parts))


def render_kpi_cards(cards: list) -> None:
    card_html = "".join(
        f"""<div style="flex:1;min-width:120px;padding:14px 16px;
                background:#f4f6f8;border-radius:8px;border:1px solid #e2e6ea;color:#212529;">
            <div style="font-size:13px;color:#6c757d;margin-bottom:4px;">{label}</div>
            <div style="font-size:28px;font-weight:600;color:#212529;line-height:1.1;">{value}</div>
        </div>""" for label, value in cards)
    st.markdown(
        f'<div style="display:flex;gap:12px;margin:8px 0 18px;flex-wrap:wrap;">{card_html}</div>',
        unsafe_allow_html=True)


def results_to_df(texts: list, results: list) -> pd.DataFrame:
    rows = []
    for txt, r in zip(texts, results):
        emo = r.get("emotion") or {}
        rep = r.get("representative")
        rows.append({
            "text": txt,
            "valence": r.get("valence", ""),
            "activation": r.get("activation", ""),
            "representative": rep[0] if rep else "",
            "emotive": "yes" if (emo or r.get("emotive")) else "no",
            **{e: ", ".join(emo.get(e, [])) for e in EMOTIONS},
        })
    return pd.DataFrame(rows)


# ── Sidebar ──────────────────────────────────────────────────────────────────

def render_sidebar() -> tuple:
    lang = get_lang()
    with st.sidebar:
        # Belt-and-braces: `get_lang()` already normalises, but compute the
        # index defensively so a transient stale session_state value can never
        # crash this widget.
        try:
            lang_idx = LANGUAGES.index(lang)
        except ValueError:
            lang_idx = 0
        new_lang = st.radio(
            t("language", lang),
            options=LANGUAGES,
            format_func=lambda code: t("english", lang) if code == "en" else t("japanese", lang),
            horizontal=True,
            index=lang_idx,
            key="_lang_radio",
        )
        if new_lang != lang:
            st.session_state["lang"] = new_lang
            st.rerun()
        lang = get_lang()

        st.markdown(
            f"<h2 style='margin:0;padding:8px 0;color:#a4133c;'>"
            f"❤️ {t('page_title', lang)}</h2>"
            f"<p style='margin:0;font-size:13px;color:#666;'>{t('version_caption', lang)}</p>",
            unsafe_allow_html=True,
        )
        st.divider()

        mecab_arg = st.text_input(
            t("mecab_arg_label", lang), value="",
            placeholder="-r /opt/homebrew/etc/mecabrc",
            help=t("mecab_arg_help", lang),
        )

        st.divider()
        st.markdown(f"### {t('about_title', lang)}")
        st.markdown(t("about_body", lang))

        st.markdown(f"### {t('emotion_classes', lang)}")
        for emo in EMOTIONS:
            color = EMOTION_COLORS[emo]
            st.markdown(
                f'<span style="display:inline-block;width:12px;height:12px;'
                f"border-radius:50%;background:{color};margin-right:6px;"
                f'vertical-align:middle;"></span>{lbl(emo)}',
                unsafe_allow_html=True,
            )

        st.divider()
        st.markdown(f"### {t('citation', lang)}")
        st.caption(t("citation_lead", lang))
        st.code(
            "Ptaszynski, M., Dybala, P., Rzepka, R., Araki, K., &\n"
            "  Masui, F. (2017). ML-Ask: Open source affect analysis\n"
            "  software for textual input in Japanese. Journal of Open\n"
            "  Research Software, 5(1), 16-16.",
            language=None,
        )
        st.code(
            "Wang, L., Isomura, S., Ptaszynski, M., Dybala, P.,\n"
            "  Urabe, Y., Rzepka, R., & Masui, F. (2024). The limits\n"
            "  of words: expanding a word-based emotion analysis system\n"
            "  with multiple emotion dictionaries and the automatic\n"
            "  extraction of emotive expressions. Applied Sciences,\n"
            "  14(11), 4439.",
            language=None,
        )
        st.caption(t("credit", lang))

    return mecab_arg, lang


# ── Single-text tab ──────────────────────────────────────────────────────────

def tab_single(analyzer) -> None:
    lang = get_lang()
    st.subheader(t("single_subheader", lang))

    if "_pending_sample" in st.session_state:
        st.session_state["input_text"] = st.session_state.pop("_pending_sample")
    if "input_text" not in st.session_state:
        st.session_state["input_text"] = "彼のことは嫌いではない！"

    text = st.text_area(
        t("input_label", lang), height=120,
        placeholder=t("input_placeholder", lang), key="input_text",
    )

    st.markdown(f"**{t('quick_examples', lang)}**")
    row1 = st.columns(5); row2 = st.columns(5)
    for i, sample in enumerate(SAMPLE_TEXTS):
        col = (row1 if i < 5 else row2)[i % 5]
        button_label = sample if len(sample) <= 18 else sample[:17] + "…"
        if col.button(button_label, key=f"sample_{i}",
                      use_container_width=True, help=sample):
            st.session_state["_pending_sample"] = sample
            st.rerun()

    analyze_btn = st.button(t("analyze_button", lang), type="primary")

    if analyze_btn or text:
        if not text.strip():
            st.warning(t("no_text_warning", lang))
            return

        t0 = time.perf_counter()
        result = analyzer.analyze(text)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        st.caption(t("elapsed_caption", lang, ms=elapsed_ms))

        if result.get("emotion") is None:
            _render_no_emotion(result); return

        col_radar, col_russell = st.columns(2)
        with col_radar:
            st.plotly_chart(make_radar_chart(result),
                            use_container_width=True, config=PLOTLY_CONFIG)
        with col_russell:
            st.plotly_chart(make_russell_chart(result),
                            use_container_width=True, config=PLOTLY_CONFIG)

        render_badges(result)
        st.markdown("---")

        col_detail, col_intens = st.columns([3, 2])
        with col_detail:
            st.markdown(f"#### {t('emotion_words_header', lang)}")
            render_emotion_details(result)
        with col_intens:
            st.markdown(f"#### {t('intensifiers_header', lang)}")
            render_intensifiers(result)

        with st.expander(t("raw_output", lang)):
            st.json({k: (list(v) if isinstance(v, tuple) else v) for k, v in result.items()})

        with st.expander(t("pipe_output", lang)):
            st.code(analyzer.format_original(result))


# ── Batch tab ───────────────────────────────────────────────────────────────

def tab_batch(analyzer) -> None:
    lang = get_lang()
    st.subheader(t("batch_subheader", lang))

    col_upload, col_paste = st.columns(2)
    with col_upload:
        uploaded = st.file_uploader(
            t("upload_label", lang), type=["txt"],
            help=t("upload_help", lang),
        )
    with col_paste:
        pasted = st.text_area(t("paste_label", lang), height=150,
                              placeholder="嬉しい！\n悲しくてたまらない。\n怖かった。")

    run_batch = st.button(t("analyze_all_button", lang), type="primary")
    if not run_batch:
        return

    raw_lines: list = []
    if uploaded is not None:
        content = uploaded.read().decode("utf-8", errors="replace")
        raw_lines = [l.strip() for l in content.splitlines() if l.strip()]
    elif pasted.strip():
        raw_lines = [l.strip() for l in pasted.splitlines() if l.strip()]
    if not raw_lines:
        st.warning(t("no_input", lang)); return

    # 5.3 — auto-detect timestamp-prefixed input
    texts, timestamps = parse_timestamped_input(raw_lines)
    has_timestamps = bool(timestamps) and any(ts is not None for ts in timestamps)

    with st.spinner(t("analyzing", lang, n=len(texts))):
        t0 = time.perf_counter()
        results = analyzer.analyze_batch(texts)
        elapsed = time.perf_counter() - t0

    st.success(t("analyzed_summary", lang,
                 n=len(texts), ms=elapsed*1000, rate=len(texts)/elapsed))

    if has_timestamps:
        st.info(t("trend_hint", lang))

    df = results_to_df(texts, results)
    emotive_count = int((df["emotive"] == "yes").sum())

    render_kpi_cards([
        (t("kpi_total", lang),       str(len(texts))),
        (t("kpi_emotive", lang),     str(emotive_count)),
        (t("kpi_non_emotive", lang), str(len(texts) - emotive_count)),
        (t("kpi_throughput", lang),  f"{len(texts)/elapsed:.0f} / s"),
    ])

    val_counts = df["valence"].value_counts()
    pie_fig = go.Figure(go.Pie(
        labels=val_counts.index.tolist(),
        values=val_counts.values.tolist(),
        marker_colors=[VALENCE_COLORS.get(o, "#888") for o in val_counts.index],
        hole=0.45,
    ))
    pie_fig.update_layout(
        title=dict(text=t("valence_distribution", lang),
                   font=dict(size=13, family=SERIF_FAMILY), x=0.5),
        height=320, margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )

    agg_emotions: dict = {}
    for r in results:
        for emo, words in (r.get("emotion") or {}).items():
            agg_emotions.setdefault(emo, []).extend(words)

    col_pie, col_russell = st.columns([1, 2])
    with col_pie:
        st.plotly_chart(pie_fig, use_container_width=True, config=PLOTLY_CONFIG)
    with col_russell:
        if agg_emotions:
            agg_result = {
                "emotion": agg_emotions,
                "representative": sorted(agg_emotions.items(),
                                          key=lambda x: len(x[1]),
                                          reverse=True)[0],
            }
            st.plotly_chart(make_russell_chart(agg_result),
                            use_container_width=True, config=PLOTLY_CONFIG)

    # 5.3 time-series
    if has_timestamps:
        st.plotly_chart(make_timeseries_chart(results, timestamps),
                        use_container_width=True, config=PLOTLY_CONFIG)

    # Per-sentence breakdown
    if len(texts) <= 20:
        st.plotly_chart(make_bar_chart(results, texts),
                        use_container_width=True, config=PLOTLY_CONFIG)
    else:
        st.plotly_chart(make_emotion_heatmap(results, texts),
                        use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown(f"#### {t('results_table', lang)}")
    st.dataframe(df, use_container_width=True, height=300)

    # Downloads
    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False, encoding="utf-8")
    json_results = []
    for r in results:
        jr = {}
        for k, v in r.items():
            if isinstance(v, tuple): jr[k] = list(v)
            elif hasattr(v, "items"): jr[k] = dict(v)
            else: jr[k] = v
        json_results.append(jr)
    json_blob = json.dumps(json_results, ensure_ascii=False, indent=2)
    pipe_blob = "\n".join(analyzer.format_original(r) for r in results)

    col_csv, col_json, col_pipe = st.columns(3)
    with col_csv:
        st.download_button(t("download_csv", lang),
                           data=csv_buf.getvalue().encode("utf-8"),
                           file_name="mlask_results.csv", mime="text/csv",
                           use_container_width=True)
    with col_json:
        st.download_button(t("download_json", lang),
                           data=json_blob.encode("utf-8"),
                           file_name="mlask_results.json", mime="application/json",
                           use_container_width=True)
    with col_pipe:
        st.download_button(t("download_pipe", lang),
                           data=pipe_blob.encode("utf-8"),
                           file_name="mlask_results.txt", mime="text/plain",
                           use_container_width=True)


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)

    mecab_arg, lang = render_sidebar()

    st.title(f"❤️ {t('page_title', lang)}")
    if lang == "ja":
        st.markdown("*eMotive eLement and Expression Analysis* · v0.5 · "
                    "日本語感情解析 · 原典システム： **プタシンスキ・ミハウ** 他")
    else:
        st.markdown("*eMotive eLement and Expression Analysis* · v0.5 · "
                    "Japanese emotion analysis · Original system by **Michal Ptaszynski** et al.")
    st.divider()

    try:
        analyzer = load_analyzer(mecab_arg)
    except Exception as e:
        st.error(f"Failed to initialize ML-Ask: {e}")
        return

    tab1, tab2 = st.tabs([t("tab_single", lang), t("tab_batch", lang)])
    with tab1: tab_single(analyzer)
    with tab2: tab_batch(analyzer)


if __name__ == "__main__":
    main()
