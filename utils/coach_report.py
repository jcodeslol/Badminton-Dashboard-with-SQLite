import json
import os
import streamlit as st
import google.generativeai as genai

from utils.session_utils import get_active_analytics, get_active_predictions
from utils.identity_section import build_identity_card
from utils.tactical_section import build_tactical_data

def build_report_inputs(analytics, predictions=None):
    return {
        "identity":              build_identity_card(analytics),
        "tactical":              build_tactical_data(analytics, predictions),
        "grade":                 analytics.get("session_grade","N/A"),
        "bps":                   analytics.get("bps", 0),
        "duration":              analytics.get("duration_seconds", 0),
        "pose_detection_rate":   analytics.get("pose_detection_rate", 1.0),
        "avg_recovery_distance": analytics.get("avg_recovery_distance", 0),
        "avg_stance_width":      analytics.get("avg_stance_width", 0),
    }

# ... (keep all your existing generate_* functions unchanged) ...

def generate_gemini_report(inputs):
    """Call Gemini API and return a coach report string."""
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None, "⚠️ No Gemini API key found. Add GEMINI_API_KEY to your Streamlit secrets."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        identity = inputs["identity"]
        tactical = inputs["tactical"]

        prompt = f"""
You are an expert badminton coach. Analyse this player's session data and write a concise, 
actionable coach report (max 300 words). Be encouraging but honest.

Session data:
- Grade: {inputs['grade']}
- BPS Score: {inputs['bps']:.1f}/100
- Duration: {inputs['duration']:.0f} seconds
- Archetype: {identity['archetype']} — {identity['archetype_description']}
- Dominant side: {identity['dominant_side']['side']} 
  ({identity['dominant_side']['forehand_pct']:.0f}% FH / {identity['dominant_side']['backhand_pct']:.0f}% BH)
- Court preference: {identity['court_preference']['label']}
- Style tags: {', '.join(identity['style_tags'])}
- Recovery distance: {inputs['avg_recovery_distance']:.2f} (target <0.30)
- Avg stance width: {inputs['avg_stance_width']:.3f}
- Top strengths: {[s['metric'] for s in tactical['top_strengths']]}
- Top weaknesses: {[w['metric'] for w in tactical['top_weaknesses']]}

Write sections: Overview, Key Strengths, Areas to Improve, Top Drill Recommendation.
"""
        response = model.generate_content(prompt)
        return response.text, None
    except Exception as e:
        return None, f"⚠️ Gemini API error: {e}"


def render_coach_report_section(*args, **kwargs):
    analytics   = get_active_analytics()
    predictions = get_active_predictions()
    inputs = build_report_inputs(analytics, predictions)

    st.markdown("## 🤖 AI Coach Report")
    st.caption(f"Grade {inputs['grade']} · BPS {inputs['bps']:.1f} · {inputs['identity']['archetype']}")

    # --- Gemini AI Report ---
    st.markdown("### ✨ Gemini AI Analysis")
    with st.spinner("Generating AI report..."):
        ai_text, error = generate_gemini_report(inputs)

    if error:
        st.warning(error)
    else:
        st.markdown(ai_text)

    st.divider()

    # --- Static sections (unchanged) ---
    with st.expander("📋 Session Summary", expanded=False):
        st.markdown(generate_session_summary(inputs))
    with st.expander("💪 Strength Analysis"):
        st.markdown(generate_strength_analysis(inputs))
    with st.expander("⚠️ Weakness Analysis"):
        st.markdown(generate_weakness_analysis(inputs))
    with st.expander("🎯 Tactical Insights"):
        st.markdown(generate_tactical_insights(inputs))
    with st.expander("🔄 Recovery Recommendations"):
        st.markdown(generate_recovery_recommendations(inputs))
    with st.expander("🏋️ Training Suggestions"):
        st.markdown(generate_training_suggestions(inputs))
    with st.expander("📄 Full Report (copy-paste)"):
        st.text_area("Full report", generate_report_text(inputs), height=400, label_visibility="collapsed")