# -*- coding: utf-8 -*-
"""Tiny i18n table for the Streamlit app (and any other UI). v0.5.

Two locales: ``en`` (English) and ``ja`` (Japanese).  Lookup via ``t(key, lang)``.
"""
from mlask_official._analyzer import EMOTION_LABELS_EN, EMOTION_LABELS_JA

LANGUAGES = ("en", "ja")

# UI strings, keyed by stable IDs.  Add new keys as the UI grows.
STRINGS: dict[str, dict[str, str]] = {
    # Sidebar / header
    "page_title":                {"en": "ML-Ask Official",            "ja": "ML-Ask 公式"},
    "version_caption":           {"en": "v0.5 · dual Aho-Corasick · 10 emotions",
                                  "ja": "v0.5 · 二重Aho-Corasick · 10感情"},
    "language":                  {"en": "Language",                    "ja": "言語"},
    "english":                   {"en": "English",                     "ja": "English"},
    "japanese":                  {"en": "日本語",                    "ja": "日本語"},
    "mecab_arg_label":           {"en": "MeCab arguments (optional)",  "ja": "MeCab 引数（任意）"},
    "mecab_arg_help":            {"en": "Leave blank for auto-detection.",
                                  "ja": "空欄で自動検出します。"},
    "about_title":               {"en": "About ML-Ask",                "ja": "ML-Ask について"},
    "about_body":                {"en": "ML-Ask (eMotive eLement and Expression Analysis system) "
                                        "is a keyword-based rule system for automatic affect "
                                        "annotation of Japanese utterances.",
                                  "ja": "ML-Ask（eMotive eLement and Expression Analysis system）は、"
                                        "日本語発話の感情を自動付与するキーワードベースの規則ベースシステムです。"},
    "emotion_classes":           {"en": "Emotion classes",             "ja": "感情カテゴリ"},
    "citation":                  {"en": "Citation",                    "ja": "引用情報"},
    "citation_lead":             {"en": "If you use ML-Ask in research, please cite both papers:",
                                  "ja": "ML-Ask を研究で使用される場合、下記の2本の論文を引用してください。"},
    "credit":                    {"en": "Original system: Michal Ptaszynski, Pawel Dybala, "
                                        "Rafal Rzepka, Kenji Araki.",
                                  "ja": "原典システム開発者：プタシンスキ・ミハウ、ディバワ・パヴェウ、"
                                        "ジェプカ・ラファウ、荒木健治。"},

    # Tabs
    "tab_single":                {"en": "Single text",                  "ja": "単文解析"},
    "tab_batch":                 {"en": "Batch analysis",               "ja": "バッチ解析"},
    "single_subheader":          {"en": "Analyze a single text",        "ja": "単一文の解析"},
    "batch_subheader":           {"en": "Batch analysis",               "ja": "バッチ解析"},
    "input_label":               {"en": "Japanese text",                "ja": "日本語テキスト"},
    "input_placeholder":         {"en": "Enter Japanese text here…",    "ja": "日本語テキストを入力…"},
    "quick_examples":            {"en": "Quick examples:",              "ja": "サンプル文："},
    "analyze_button":            {"en": "Analyze",                      "ja": "解析"},
    "analyze_all_button":        {"en": "Analyze all",                  "ja": "全て解析"},
    "elapsed_caption":           {"en": "Analysis completed in **{ms:.1f} ms**",
                                  "ja": "解析完了：**{ms:.1f} ms**"},
    "no_text_warning":           {"en": "Please enter some text.",
                                  "ja": "テキストを入力してください。"},

    # Result rendering
    "emotion_words_header":      {"en": "Emotion words found",          "ja": "検出された感情語"},
    "intensifiers_header":       {"en": "Intensifiers",                 "ja": "感情強調語"},
    "representative_label":      {"en": "Representative:",              "ja": "代表感情："},
    "representative_caption":    {"en": "The representative emotion is the class whose longest "
                                        "matched expression has the most characters — longer "
                                        "dictionary entries are more specific.",
                                  "ja": "代表感情は、検出された表現のうち最長の表現を含むカテゴリです。"
                                        "より長い辞書項目はより具体的な感情を表します。"},
    "detected_words":            {"en": "**Detected emotion words:**",  "ja": "**検出された感情語：**"},
    "negated_suffix":            {"en": "_(negated)_",                  "ja": "_（否定）_"},
    "particle_stripped_suffix":  {"en": "_(particle-stripped match)_",  "ja": "_（助詞省略一致）_"},
    "no_emotion_words":          {"en": "No emotion words detected in this text.",
                                  "ja": "このテキストから感情語は検出されませんでした。"},

    "emotive_banner_title":      {"en": "EMOTIVE",                      "ja": "感情的"},
    "non_emotive_banner_title":  {"en": "NON-EMOTIVE",                  "ja": "非感情的"},
    "emotive_body":              {"en": "emotional intensity markers detected, but no specific "
                                        "emotion word found in the dictionary.",
                                  "ja": "感情強調マーカーは検出されましたが、辞書中の具体的な感情語は見つかりませんでした。"},
    "emotive_caption":           {"en": "This sentence is likely expressive or emotional in tone; "
                                        "the expressed emotion could not be classified into one "
                                        "of the 10 ML-Ask categories.",
                                  "ja": "感情的・表現的なトーンの可能性が高いですが、ML-Askの10カテゴリには分類できませんでした。"},
    "non_emotive_body":          {"en": "no emotional markers or emotion words detected.",
                                  "ja": "感情マーカーや感情語は検出されませんでした。"},
    "non_emotive_caption":       {"en": "The sentence appears neutral or factual. No emotemes, "
                                        "interjections, emoticons, or emotion dictionary matches were found.",
                                  "ja": "この文は中立的または事実的な記述と思われます。感情語・感動詞・顔文字・辞書一致のいずれも検出されませんでした。"},

    "raw_output":                {"en": "Raw output (dict)",            "ja": "生出力（辞書形式）"},
    "pipe_output":               {"en": "Original ML-Ask pipe format",  "ja": "オリジナル ML-Ask 形式（パイプ区切り）"},

    # Batch panel
    "upload_label":              {"en": "Upload a .txt file (one sentence per line)",
                                  "ja": ".txt ファイルをアップロード（1行1文）"},
    "upload_help":               {"en": "UTF-8 encoded, one Japanese sentence per line.",
                                  "ja": "UTF-8 エンコード、1行に1つの日本語文を入力してください。"},
    "paste_label":               {"en": "…or paste sentences here (one per line)",
                                  "ja": "…またはここに文を貼り付け（1行1文）"},
    "no_input":                  {"en": "No input text found.",         "ja": "入力テキストがありません。"},
    "analyzing":                 {"en": "Analyzing {n} sentences…",     "ja": "{n} 文を解析中…"},
    "analyzed_summary":          {"en": "Analyzed **{n}** sentences in **{ms:.1f} ms** ({rate:.0f} sentences/sec)",
                                  "ja": "**{n}** 文を **{ms:.1f} ms** で解析（{rate:.0f} 文/秒）"},

    "kpi_total":                 {"en": "Total",                        "ja": "合計"},
    "kpi_emotive":               {"en": "Emotive",                      "ja": "感情的"},
    "kpi_non_emotive":           {"en": "Non-emotive",                  "ja": "非感情的"},
    "kpi_throughput":            {"en": "Throughput",                   "ja": "処理速度"},
    "valence_distribution":      {"en": "Valence distribution",         "ja": "感情極性分布"},

    "results_table":             {"en": "Results table",                "ja": "結果テーブル"},
    "download_csv":              {"en": "⬇ CSV (table)",                "ja": "⬇ CSV（表）"},
    "download_json":             {"en": "⬇ JSON (raw dicts)",           "ja": "⬇ JSON（生辞書）"},
    "download_pipe":             {"en": "⬇ Pipe (original ML-Ask)",     "ja": "⬇ パイプ形式（ML-Ask 元形式）"},

    "trend_title":               {"en": "Emotion prevalence over time",
                                  "ja": "感情頻度の時系列推移"},
    "trend_hint":                {"en": "Detected ISO-style timestamps in your input — showing time series.",
                                  "ja": "ISO形式のタイムスタンプを検出しました。時系列表示に切り替えます。"},
}


def t(key: str, lang: str = "en", **fmt) -> str:
    """Look up a UI string. Falls back to ``en`` then to the key itself."""
    lang = lang if lang in LANGUAGES else "en"
    entry = STRINGS.get(key)
    if entry is None:
        return key
    s = entry.get(lang) or entry.get("en") or key
    if fmt:
        try:
            return s.format(**fmt)
        except (KeyError, IndexError, ValueError):
            return s
    return s


def emotion_label(emo: str, lang: str = "en") -> str:
    """Localised emotion label (e.g. ``Yorokobi (joy)`` vs ``喜び``)."""
    table = EMOTION_LABELS_JA if lang == "ja" else EMOTION_LABELS_EN
    return table.get(emo, emo)
