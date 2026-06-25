"""
coach_report.py — AI Coach Report powered by Google Gemini
"""

import os
import traceback
import streamlit as st

from utils.session_utils import get_active_analytics, get_active_predictions
from utils.identity_section import build_identity_card
from utils.tactical_section import build_tactical_data


# ─────────────────────────────────────────────
# Data builder
# ─────────────────────────────────────────────

def build_report_inputs(analytics, predictions=None):
    identity = build_identity_card(analytics)
    tactical = build_tactical_data(analytics, predictions)
    return {
        "identity":              identity,
        "archetype":             identity["archetype"],
        "archetype_description": identity["archetype_description"],
        "style_tags":            identity["style_tags"],
        "dominant_side":         identity["dominant_side"],
        "court_preference":      identity["court_preference"],
        "tactical":              tactical,
        "grade":                 analytics.get("session_grade", "N/A"),
        "bps":                   analytics.get("bps", 0),
        "duration":              analytics.get("duration_seconds", 0),
        "pose_detection_rate":   analytics.get("pose_detection_rate", 1.0),
        "avg_recovery_distance": analytics.get("avg_recovery_distance", 0),
        "avg_stance_width":      analytics.get("avg_stance_width", 0),
    }


# ─────────────────────────────────────────────
# Static report generators
# ─────────────────────────────────────────────

def generate_session_summary(inputs):
    dom = inputs["dominant_side"]
    cp  = inputs["court_preference"]
    return (
        f"This session ran **{inputs['duration']:.1f} seconds** and earned grade "
        f"**{inputs['grade']}** with BPS **{inputs['bps']:.1f}/100**. "
        f"The player's profile is a **{inputs['archetype']}** — {inputs['archetype_description'].lower()}\n\n"
        f"Shot distribution: **{dom['side'].lower()}-dominant** "
        f"({dom['forehand_pct']:.0f}% forehand / {dom['backhand_pct']:.0f}% backhand). "
        f"Court positioning centred around **{cp['label']}** ({cp['top_zone_pct']:.0f}% of time). "
        f"Pose detection confidence: {inputs['pose_detection_rate']*100:.0f}%."
    )


def generate_strength_analysis(inputs):
    strengths = inputs["tactical"]["top_strengths"]
    if not strengths:
        return "No strength data available for this session."
    lines = ["Top strengths ranked by score:\n"]
    for i, s in enumerate(strengths, 1):
        lines.append(f"{i}. **{s['metric'].replace('_',' ').title()}** ({s['score']:.1f}/100) — {s['blurb']}")
    lines.append(f"\n**{strengths[0]['metric'].replace('_',' ')}** is the strongest foundation to build on.")
    return "\n".join(lines)


def generate_weakness_analysis(inputs):
    weaknesses = inputs["tactical"]["top_weaknesses"]
    if not weaknesses:
        return "No weakness data available for this session."
    lines = ["Lowest-scoring areas:\n"]
    for i, w in enumerate(weaknesses, 1):
        lines.append(f"{i}. **{w['metric'].replace('_',' ').title()}** ({w['score']:.1f}/100) — {w['blurb']}")
    worst = weaknesses[0]
    lines.append(f"\n**{worst['metric'].replace('_',' ').title()}** (score {worst['score']:.1f}) is the most urgent gap.")
    return "\n".join(lines)


def generate_tactical_insights(inputs):
    t     = inputs["tactical"]["tactical"]
    lines = [
        f"{t['tendency_text']}\n",
        f"Shot-side: **{t['forehand_pct']:.0f}% forehand** vs **{t['backhand_pct']:.0f}% backhand**."
    ]
    imbalance = abs(t["forehand_pct"] - t["backhand_pct"])
    if imbalance > 20:
        weaker = "forehand" if t["backhand_pct"] > t["forehand_pct"] else "backhand"
        lines.append(f"This {imbalance:.0f}-point gap is a tactical vulnerability — opponents targeting the **{weaker}** side may disrupt rhythm.")
    else:
        lines.append("Shot-side usage is reasonably balanced.")
    depth = t["depth_breakdown"]
    dominant_depth = max(depth, key=depth.get) if any(depth.values()) else None
    if dominant_depth:
        lines.append(f"\nCourt depth concentrated in **{dominant_depth} court** ({depth[dominant_depth]:.0f}%).")
    lines.append(f"\nStyle tags: {', '.join(inputs['style_tags'])}.")
    return "\n".join(lines)


def generate_recovery_recommendations(inputs):
    rd = inputs["avg_recovery_distance"]
    sw = inputs["avg_stance_width"]
    if rd > 0.30:
        rec = (f"Recovery distance **{rd:.2f}** is above the 0.30 target. "
               f"Player is not returning to base position consistently.\n\n"
               f"**Recommendation:** Drill split-step and return-to-base timing in shadow footwork sessions.")
    else:
        rec = (f"Recovery distance **{rd:.2f}** is within healthy range. "
               f"Player is resetting to base effectively.\n\n"
               f"**Recommendation:** Maintain habits; raise intensity to build resilience under fatigue.")
    if sw:
        rec += (f"\n\nAvg stance width: **{sw:.3f}** (normalized). "
                f"{'Wide base supports lateral stability.' if sw > 0.07 else 'Narrower stance may limit lateral reach — consider stance-width cues.'}")
    return rec


def generate_training_suggestions(inputs):
    priorities = inputs["tactical"]["training_priorities"]
    if not priorities:
        return "No training priority data available."
    lines = ["Recommended training plan ranked by urgency:\n"]
    for p in priorities:
        lines.append(f"**Priority {p['rank']}: {p['focus']}** (urgency {p['urgency']:.0f}/100)  \nDrill: {p['suggestion']}")
    lines.append("\nSpend the first third of the next session on Priority 1 while movement is fresh.")
    return "\n\n".join(lines)


def generate_report_text(inputs):
    return "\n\n".join([
        f"## AI Coach Report\n**Grade {inputs['grade']} · BPS {inputs['bps']:.1f} · {inputs['archetype']}**",
        "### Session Summary",          generate_session_summary(inputs),
        "### Strength Analysis",        generate_strength_analysis(inputs),
        "### Weakness Analysis",        generate_weakness_analysis(inputs),
        "### Tactical Insights",        generate_tactical_insights(inputs),
        "### Recovery Recommendations", generate_recovery_recommendations(inputs),
        "### Training Suggestions",     generate_training_suggestions(inputs),
    ])


# ─────────────────────────────────────────────
# Gemini integration
# ─────────────────────────────────────────────

def _get_api_key():
    try:
        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


def _build_gemini_prompt(inputs):
    strengths  = [s["metric"].replace("_", " ") for s in inputs["tactical"]["top_strengths"]]
    weaknesses = [w["metric"].replace("_", " ") for w in inputs["tactical"]["top_weaknesses"]]
    return f"""You are an expert badminton coach reviewing a player's session data. \
Write a concise, actionable coach report (around 250 words) with four clearly labelled \
sections: Overview, Key Strengths, Areas to Improve, and Top Drill Recommendation. \
Be encouraging but honest.

Session data:
- Grade: {inputs["grade"]}
- BPS Score: {inputs["bps"]:.1f}/100
- Duration: {inputs["duration"]:.0f} seconds
- Archetype: {inputs["archetype"]} — {inputs["archetype_description"]}
- Dominant side: {inputs["dominant_side"]["side"]} \
({inputs["dominant_side"]["forehand_pct"]:.0f}% FH / {inputs["dominant_side"]["backhand_pct"]:.0f}% BH)
- Court preference: {inputs["court_preference"]["label"]} \
({inputs["court_preference"]["top_zone_pct"]:.0f}% of time)
- Style tags: {", ".join(inputs["style_tags"])}
- Avg recovery distance: {inputs["avg_recovery_distance"]:.2f} (target < 0.30)
- Avg stance width: {inputs["avg_stance_width"]:.3f}
- Top strengths: {", ".join(strengths)}
- Top weaknesses: {", ".join(weaknesses)}
"""


def generate_gemini_report(inputs):
    api_key = _get_api_key()
    if not api_key:
        return None, "No Gemini API key found. Add `GEMINI_API_KEY` to your Streamlit secrets."

    try:
        import google.generativeai as genai
    except ModuleNotFoundError:
        return None, "`google-generativeai` not installed. Add it to requirements.txt."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")   # ← fixed model name
        resp  = model.generate_content(_build_gemini_prompt(inputs))
        return resp.text, None
    except Exception as exc:
        return None, f"Gemini API error: {exc}\n\n```\n{traceback.format_exc()}\n```"


# ─────────────────────────────────────────────
# Streamlit renderer
# ─────────────────────────────────────────────

def render_coach_report_section(*args, **kwargs):
    analytics   = get_active_analytics()
    predictions = get_active_predictions()

    if not analytics:
        st.error("No analytics data found. Make sure `data/analytics.json` exists or upload a video first.")
        return

    try:
        inputs = build_report_inputs(analytics, predictions)
    except Exception as exc:
        st.error(f"Failed to build report inputs: `{exc}`")
        with st.expander("🔍 Full traceback"):
            st.code(traceback.format_exc())
        return

    st.markdown("## 🤖 AI Coach Report")
    st.caption(f"Grade {inputs['grade']} · BPS {inputs['bps']:.1f} · {inputs['archetype']}")

    # ── Gemini section ────────────────────────────────────────
    st.markdown("### ✨ Gemini AI Analysis")

    if not _get_api_key():
        st.warning("Gemini API key not configured. Add `GEMINI_API_KEY` to Streamlit secrets (Settings → Secrets).")
    else:
        if st.button("🔄 Generate AI Report", type="primary"):
            with st.spinner("Calling Gemini…"):
                ai_text, error = generate_gemini_report(inputs)
            if error:
                st.error(error)
            else:
                st.session_state["gemini_report"] = ai_text

        if "gemini_report" in st.session_state:
            st.markdown(st.session_state["gemini_report"])

    st.divider()

    # ── Static breakdown ──────────────────────────────────────
    st.markdown("### 📊 Detailed Breakdown")

    sections = [
        ("📋 Session Summary",        generate_session_summary,        True),
        ("💪 Strength Analysis",       generate_strength_analysis,      False),
        ("⚠️ Weakness Analysis",       generate_weakness_analysis,      False),
        ("🎯 Tactical Insights",       generate_tactical_insights,      False),
        ("🔄 Recovery Recommendations",generate_recovery_recommendations,False),
        ("🏋️ Training Suggestions",    generate_training_suggestions,   False),
    ]

    for label, fn, expanded in sections:
        with st.expander(label, expanded=expanded):
            try:
                st.markdown(fn(inputs))
            except Exception as exc:
                st.error(f"{label} error: `{exc}`")
                st.code(traceback.format_exc())

    with st.expander("📄 Full Report (copy-paste)"):
        try:
            st.text_area("Full report", generate_report_text(inputs), height=400, label_visibility="collapsed")
        except Exception as exc:
            st.error(f"Full Report error: `{exc}`")
            st.code(traceback.format_exc())