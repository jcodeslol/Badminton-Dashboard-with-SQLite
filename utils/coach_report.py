"""
coach_report.py
Member 3 - Tactical & AI Coach Lead

LLM-powered coach report using:
  1. Gemini API  (works on Streamlit Cloud — needs GEMINI_API_KEY in secrets)
  2. Ollama      (works locally — needs `ollama serve` running, model pulled)
  3. Rule-based  (always works — zero dependencies, fallback of last resort)

Priority order: Gemini → Ollama → Rule-based.
Nothing crashes if a provider is unavailable — it just silently drops to the next.

SETUP:
  Gemini:  Add GEMINI_API_KEY to Streamlit secrets or .env
  Ollama:  `ollama pull llama3` then `ollama serve` locally
  Neither: rule-based report generates automatically, no config needed
"""

import os
import json
import streamlit as st

from utils.session_utils import get_active_analytics, get_active_predictions
from utils.identity_section import build_identity_card
from utils.tactical_section import build_tactical_data


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"   # change to whatever model you have pulled
GEMINI_MODEL = "gemini-2.0-flash"  # free tier, fast


# ---------------------------------------------------------------------------
# Build the shared context payload (same regardless of provider)
# ---------------------------------------------------------------------------
def build_report_inputs(analytics: dict, predictions=None) -> dict:
    return {
        "identity":              build_identity_card(analytics),
        "tactical":              build_tactical_data(analytics, predictions),
        "grade":                 analytics.get("session_grade", "N/A"),
        "bps":                   analytics.get("bps", 0),
        "duration":              analytics.get("duration_seconds", 0),
        "pose_detection_rate":   analytics.get("pose_detection_rate", 1.0),
        "avg_recovery_distance": analytics.get("avg_recovery_distance", 0),
        "avg_stance_width":      analytics.get("avg_stance_width", 0),
    }


def _build_prompt(inputs: dict) -> str:
    """
    Converts the structured session data into a plain-English prompt.
    The LLM only sees this string — no raw DataFrames, no imports.
    """
    identity  = inputs["identity"]
    tactical  = inputs["tactical"]
    dom       = identity["dominant_side"]
    t         = tactical["tactical"]
    strengths = tactical["top_strengths"]
    weaknesses= tactical["top_weaknesses"]
    priorities= tactical["training_priorities"]

    strength_lines  = "\n".join(f"  - {s['metric'].replace('_',' ').title()}: {s['score']:.1f}/100 — {s['blurb']}"
                                for s in strengths)
    weakness_lines  = "\n".join(f"  - {w['metric'].replace('_',' ').title()}: {w['score']:.1f}/100 — {w['blurb']}"
                                for w in weaknesses)
    priority_lines  = "\n".join(f"  {p['rank']}. {p['focus']} (urgency {p['urgency']:.0f}/100): {p['suggestion']}"
                                for p in priorities)

    return f"""You are an expert badminton performance coach writing a post-session report for a university athlete.

SESSION DATA:
- Duration: {inputs['duration']:.1f} seconds
- BPS Score: {inputs['bps']:.1f} / 100
- Session Grade: {inputs['grade']}
- Player Archetype: {identity['archetype']} — {identity['archetype_description']}
- Style Tags: {', '.join(identity['style_tags'])}
- Dominant Side: {dom['side']} ({dom['forehand_pct']:.0f}% forehand / {dom['backhand_pct']:.0f}% backhand)
- Primary Court Zone: {identity['court_preference']['label']} ({identity['court_preference']['top_zone_pct']:.0f}% of time)
- Court Depth Breakdown: Front {t['depth_breakdown'].get('front',0):.0f}%, Mid {t['depth_breakdown'].get('mid',0):.0f}%, Back {t['depth_breakdown'].get('back',0):.0f}%
- Pose Detection Confidence: {inputs['pose_detection_rate']*100:.0f}%
- Avg Recovery Distance: {inputs['avg_recovery_distance']:.3f} (target < 0.30)
- Avg Stance Width: {inputs['avg_stance_width']:.3f}
- Tactical Tendency: {t['tendency_text']}

TOP STRENGTHS:
{strength_lines}

TOP WEAKNESSES:
{weakness_lines}

TRAINING PRIORITIES (ranked by urgency):
{priority_lines}

Write a professional coach report with these exact sections. Be specific, direct, and encouraging.
Use the actual numbers from the session data above. Do not make up statistics.

## Session Summary
(2-3 sentences: grade, archetype, overall impression)

## Strength Analysis
(What the player does well and why it matters tactically)

## Weakness Analysis
(What needs work most urgently and what the consequences are if ignored)

## Tactical Insights
(Shot selection patterns, court positioning tendencies, what opponents could exploit)

## Recovery Recommendations
(Recovery distance, stance width, specific physical recommendations)

## Training Plan
(Concrete drills for each priority, with a suggested session structure)

Keep each section to 3-5 sentences. Be a real coach, not a robot."""


# ---------------------------------------------------------------------------
# Provider 1: Gemini
# ---------------------------------------------------------------------------
def _call_gemini(prompt: str) -> str | None:
    """Returns the LLM response string, or None if unavailable/failed."""
    api_key = (
        st.secrets.get("GEMINI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
    )
    if not api_key:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model    = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.toast(f"Gemini unavailable: {e}", icon="⚠️")
        return None


# ---------------------------------------------------------------------------
# Provider 2: Ollama (local only)
# ---------------------------------------------------------------------------
def _call_ollama(prompt: str) -> str | None:
    """Returns the LLM response string, or None if Ollama isn't running."""
    try:
        import requests
        payload  = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Provider 3: Rule-based fallback (always works)
# ---------------------------------------------------------------------------
def _rule_based_report(inputs: dict) -> str:
    identity  = inputs["identity"]
    tactical  = inputs["tactical"]
    dom       = identity["dominant_side"]
    t         = tactical["tactical"]
    strengths = tactical["top_strengths"]
    weaknesses= tactical["top_weaknesses"]
    priorities= tactical["training_priorities"]
    rd        = inputs["avg_recovery_distance"]
    sw        = inputs["avg_stance_width"]

    # Session Summary
    summary = (
        f"This {inputs['duration']:.1f}s session earned grade **{inputs['grade']}** "
        f"(BPS {inputs['bps']:.1f}/100). "
        f"The player profiles as a **{identity['archetype']}** — "
        f"{identity['archetype_description'].lower()} "
        f"Shot distribution leaned **{dom['side'].lower()}-dominant** "
        f"({dom['forehand_pct']:.0f}% forehand / {dom['backhand_pct']:.0f}% backhand)."
    )

    # Strengths
    s_lines = [f"{i}. **{s['metric'].replace('_',' ').title()}** ({s['score']:.1f}/100) — {s['blurb']}"
               for i, s in enumerate(strengths, 1)]
    strength_text = "\n".join(s_lines) if s_lines else "No strength data available."

    # Weaknesses
    w_lines = [f"{i}. **{w['metric'].replace('_',' ').title()}** ({w['score']:.1f}/100) — {w['blurb']}"
               for i, w in enumerate(weaknesses, 1)]
    weakness_text = "\n".join(w_lines) if w_lines else "No weakness data available."

    # Tactical
    imbalance = abs(t["forehand_pct"] - t["backhand_pct"])
    tactical_note = (
        f"A {imbalance:.0f}-point shot-side gap is a tactical vulnerability."
        if imbalance > 20 else
        "Shot-side usage is reasonably balanced."
    )
    tactical_text = f"{t['tendency_text']} {tactical_note}"

    # Recovery
    if rd > 0.30:
        recovery_text = (
            f"Recovery distance **{rd:.2f}** exceeds the 0.30 target. "
            "Drill split-step and return-to-base timing in shadow footwork sessions."
        )
    else:
        recovery_text = (
            f"Recovery distance **{rd:.2f}** is within healthy range. "
            "Raise drill intensity to maintain this under match fatigue."
        )
    if sw:
        recovery_text += (
            f" Stance width **{sw:.3f}** — "
            f"{'good lateral base.' if sw > 0.07 else 'consider widening stance for better lateral reach.'}"
        )

    # Training plan
    p_lines = [f"**{p['rank']}. {p['focus']}** (urgency {p['urgency']:.0f}/100) — {p['suggestion']}"
               for p in priorities]
    training_text = (
        "\n".join(p_lines) +
        "\n\nSpend the first third of the next session on Priority 1 while movement is freshest."
        if p_lines else "No training priority data available."
    )

    return "\n\n".join([
        f"## AI Coach Report\n**Grade {inputs['grade']} · BPS {inputs['bps']:.1f} · {identity['archetype']}**",
        f"### Session Summary\n{summary}",
        f"### Strength Analysis\n{strength_text}",
        f"### Weakness Analysis\n{weakness_text}",
        f"### Tactical Insights\n{tactical_text}",
        f"### Recovery Recommendations\n{recovery_text}",
        f"### Training Plan\n{training_text}",
    ])


# ---------------------------------------------------------------------------
# Main generator — tries providers in order
# ---------------------------------------------------------------------------
def generate_llm_report(inputs: dict) -> tuple[str, str]:
    """
    Returns (report_text, provider_label).
    provider_label is one of: 'gemini' | 'ollama' | 'rule-based'
    """
    prompt = _build_prompt(inputs)

    report = _call_gemini(prompt)
    if report:
        return report, "gemini"

    report = _call_ollama(prompt)
    if report:
        return report, "ollama"

    return _rule_based_report(inputs), "rule-based"


# ---------------------------------------------------------------------------
# Streamlit renderer
# ---------------------------------------------------------------------------
def render_coach_report_section(*args, **kwargs):
    analytics   = get_active_analytics()
    predictions = get_active_predictions()
    inputs      = build_report_inputs(analytics, predictions)

    st.markdown("## 🤖 AI Coach Report")

    # Provider badge
    provider_colors = {
        "gemini":     ("🟣", "Gemini 1.5 Flash"),
        "ollama":     ("🟢", f"Ollama · {OLLAMA_MODEL}"),
        "rule-based": ("⚪", "Rule-based fallback"),
    }

    with st.spinner("Generating your personalised coach report..."):
        report_text, provider = generate_llm_report(inputs)

    icon, label = provider_colors[provider]
    st.caption(
        f"Grade **{inputs['grade']}** · BPS **{inputs['bps']:.1f}** · "
        f"{inputs['identity']['archetype']} · {icon} {label}"
    )

    # If LLM gave us the full text, render it as one block with expandable copy
    if provider in ("gemini", "ollama"):
        st.markdown(report_text)
        with st.expander("📄 Copy full report"):
            st.text_area(
                "Full report",
                report_text,
                height=400,
                label_visibility="collapsed",
            )
    else:
        # Rule-based: render section by section with expanders
        sections = report_text.split("\n\n### ")
        # First block is the header + summary
        first = sections[0].split("\n\n### ")
        st.markdown(sections[0].split("### Session Summary")[0])

        section_map = {}
        for chunk in sections:
            if chunk.startswith("## "):
                continue
            lines  = chunk.strip().split("\n", 1)
            title  = lines[0].replace("### ", "").strip()
            body   = lines[1].strip() if len(lines) > 1 else ""
            section_map[title] = body

        expander_icons = {
            "Session Summary":          "📋",
            "Strength Analysis":        "💪",
            "Weakness Analysis":        "⚠️",
            "Tactical Insights":        "🎯",
            "Recovery Recommendations": "🔄",
            "Training Plan":            "🏋️",
        }

        for title, body in section_map.items():
            icon_str = expander_icons.get(title, "📌")
            expanded = title == "Session Summary"
            with st.expander(f"{icon_str} {title}", expanded=expanded):
                st.markdown(body)

        with st.expander("📄 Copy full report"):
            st.text_area(
                "Full report",
                report_text,
                height=400,
                label_visibility="collapsed",
            )


if __name__ == "__main__":
    import json as _json
    from utils.identity_section import load_analytics
    from utils.tactical_section import load_predictions

    analytics   = load_analytics("data/analytics.json")
    predictions = load_predictions("data/predictions.csv")
    inputs      = build_report_inputs(analytics, predictions)
    text, prov  = generate_llm_report(inputs)
    print(f"[{prov.upper()}]\n\n{text}")