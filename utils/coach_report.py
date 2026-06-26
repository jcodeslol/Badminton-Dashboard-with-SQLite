import json
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

def generate_session_summary(inputs):
    identity = inputs["identity"]
    dom      = identity["dominant_side"]
    cp       = identity["court_preference"]
    return (
        f"This session ran **{inputs['duration']:.1f} seconds** and earned grade "
        f"**{inputs['grade']}** with BPS **{inputs['bps']:.1f}/100**. "
        f"The player's profile is a **{identity['archetype']}** — {identity['archetype_description'].lower()}\n\n"
        f"Shot distribution: **{dom['side'].lower()}-dominant** "
        f"({dom['forehand_pct']:.0f}% forehand / {dom['backhand_pct']:.0f}% backhand). "
        f"Court positioning centred around **{cp['label']}** ({cp['top_zone_pct']:.0f}% of time). "
        f"Pose detection confidence: {inputs['pose_detection_rate']*100:.0f}%."
    )

def generate_strength_analysis(inputs):
    strengths = inputs["tactical"]["top_strengths"]
    if not strengths: return "No strength data available for this session."
    lines = ["Top strengths ranked by score:\n"]
    for i, s in enumerate(strengths, 1):
        lines.append(f"{i}. **{s['metric'].replace('_',' ').title()}** ({s['score']:.1f}/100) — {s['blurb']}")
    lines.append(f"\n**{strengths[0]['metric'].replace('_',' ')}** is the strongest foundation to build on.")
    return "\n".join(lines)

def generate_weakness_analysis(inputs):
    weaknesses = inputs["tactical"]["top_weaknesses"]
    if not weaknesses: return "No weakness data available for this session."
    lines = ["Lowest-scoring areas:\n"]
    for i, w in enumerate(weaknesses, 1):
        lines.append(f"{i}. **{w['metric'].replace('_',' ').title()}** ({w['score']:.1f}/100) — {w['blurb']}")
    worst = weaknesses[0]
    lines.append(f"\n**{worst['metric'].replace('_',' ').title()}** (score {worst['score']:.1f}) is the most urgent gap.")
    return "\n".join(lines)

def generate_tactical_insights(inputs):
    t        = inputs["tactical"]["tactical"]
    identity = inputs["identity"]
    lines = [f"{t['tendency_text']}\n",
             f"Shot-side: **{t['forehand_pct']:.0f}% forehand** vs **{t['backhand_pct']:.0f}% backhand**."]
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
    lines.append(f"\nStyle tags: {', '.join(identity['style_tags'])}.")
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
    if not priorities: return "No training priority data available."
    lines = ["Recommended training plan ranked by urgency:\n"]
    for p in priorities:
        lines.append(f"**Priority {p['rank']}: {p['focus']}** (urgency {p['urgency']:.0f}/100)  \nDrill: {p['suggestion']}")
    lines.append("\nSpend the first third of the next session on Priority 1 while movement is fresh.")
    return "\n\n".join(lines)

def generate_report_text(inputs):
    identity = inputs["identity"]
    return "\n\n".join([
        f"## AI Coach Report\n**Grade {inputs['grade']} · BPS {inputs['bps']:.1f} · {identity['archetype']}**",
        "### Session Summary",      generate_session_summary(inputs),
        "### Strength Analysis",    generate_strength_analysis(inputs),
        "### Weakness Analysis",    generate_weakness_analysis(inputs),
        "### Tactical Insights",    generate_tactical_insights(inputs),
        "### Recovery Recommendations", generate_recovery_recommendations(inputs),
        "### Training Suggestions", generate_training_suggestions(inputs),
    ])

def render_coach_report_section(*args, **kwargs):
    import streamlit as st
    analytics   = get_active_analytics()
    predictions = get_active_predictions()
    inputs = build_report_inputs(analytics, predictions)

    st.markdown("## 🤖 AI Coach Report")
    st.caption(f"Grade {inputs['grade']} · BPS {inputs['bps']:.1f} · {inputs['identity']['archetype']}")

    with st.expander("📋 Session Summary", expanded=True):
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
