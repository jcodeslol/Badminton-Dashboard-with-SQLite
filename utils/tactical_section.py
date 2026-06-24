"""
tactical_section.py
Member 3 - Tactical & AI Coach Lead

Owns:
    - Tactical Analysis (Forehand %, Backhand %, Court Usage % + Plotly visuals)
    - Session Grade card
    - Top 3 Strengths
    - Top 3 Weaknesses
    - Training Priority Meter (top 3 priority areas)

Consumes:
    - analytics.json (Member 1's court_zone_coverage, Member 2's bps_score etc.)
    - predictions.csv (per-frame shot classification)
"""

import json
import csv
from utils.session_utils import get_active_analytics, get_active_predictions



def load_analytics(path: str = "data/analytics.json") -> dict:
    with open(path, "r") as f:
        return json.load(f)


def load_predictions(path: str = "data/predictions.csv") -> list[dict]:
    """predictions.csv columns: frame, prediction, confidence"""
    rows = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "frame": int(row["frame"]),
                "prediction": row["prediction"],
                "confidence": float(row["confidence"]),
            })
    return rows


def _normalize_predictions(predictions) -> list[dict]:
    """
    THE FIX: get_active_predictions() returns a pandas DataFrame (both for
    demo data, loaded via pd.read_csv, and upload data, which is the raw
    predictions_df from run_pipeline.py). Every function below expects
    list[dict] and does `for row in predictions: row["prediction"]` —
    iterating a DataFrame that way loops over COLUMN NAMES (strings), and
    indexing a string with a string key throws TypeError. Normalize once,
    right here, so it never matters what shape the caller handed us.
    """
    if predictions is None:
        return []
    if hasattr(predictions, "to_dict"):  # pandas DataFrame
        return predictions.to_dict("records")
    return predictions


ZONE_DEPTH = {
    "1": "front", "2": "front", "3": "front",
    "4": "mid", "5": "mid", "6": "mid",
    "7": "back", "8": "back", "9": "back",
}


# ---------------------------------------------------------------------------
# Tactical Analysis
# ---------------------------------------------------------------------------
def get_tactical_breakdown(analytics: dict) -> dict:
    zones = analytics.get("court_zone_coverage", {})

    depth_breakdown = {"front": 0.0, "mid": 0.0, "back": 0.0}
    for zone_id, pct in zones.items():
        depth = ZONE_DEPTH.get(str(zone_id))   # str() guard: key may be int
        if depth:
            depth_breakdown[depth] = round(depth_breakdown[depth] + pct, 1)

    zones_used = len([z for z, p in zones.items() if p > 0])
    court_coverage_pct = round(zones_used / 9 * 100, 1)   # % of 9 zones visited

    return {
        "forehand_pct":    analytics.get("forehand_usage", 0.0),
        "backhand_pct":    analytics.get("backhand_usage", 0.0),
        "court_usage_pct": court_coverage_pct,
        "zones_used":      zones_used,
        "zone_breakdown":  zones,
        "depth_breakdown": depth_breakdown,
    }


def get_avg_shot_confidence(predictions: list[dict]) -> dict:
    totals: dict[str, list[float]] = {}
    for row in predictions:
        totals.setdefault(row["prediction"], []).append(row["confidence"])
    return {shot: round(sum(c) / len(c), 3) for shot, c in totals.items()}


def get_shot_counts(predictions: list[dict]) -> dict:
    """Raw frame counts per shot type - feeds the Plotly pie chart."""
    counts: dict[str, int] = {}
    for row in predictions:
        counts[row["prediction"]] = counts.get(row["prediction"], 0) + 1
    return counts


def get_tactical_tendency_text(tactical: dict) -> str:
    """Short interpretive sentence describing court usage behavior pattern."""
    depth = tactical["depth_breakdown"]
    if not any(depth.values()):
        return "No court zone data available."
    dominant_depth = max(depth, key=depth.get)
    pct = depth[dominant_depth]
    descriptions = {
        "front": "plays close to the net, favoring quick exchanges and net play",
        "mid": "operates mostly from mid-court, balancing offense and defense",
        "back": "stays deep in the back court, favoring clears and defensive lifts",
    }
    return f"Court usage pattern shows the player {descriptions.get(dominant_depth, '')} ({pct:.0f}% of time)."


# ---------------------------------------------------------------------------
# Strengths / Weaknesses (Top 3, formatted with interpretation)
# ---------------------------------------------------------------------------
STRENGTH_BLURBS = {
    "stability": "Excellent balance control during shots and movement transitions.",
    "forehand_balance": "Well-developed, reliable forehand technique.",
    "recovery_speed": "Returns to ready position quickly after shots.",
    "agility": "Quick directional changes and footwork response.",
    "path_efficiency": "Takes direct, efficient routes around the court.",
    "avg_speed": "Strong overall court speed.",
    "speed": "Strong overall court speed.",
    "recovery": "Returns to ready position quickly after shots.",
}

WEAKNESS_BLURBS = {
    "stability": "Balance breaks down under movement load — risk of mistimed shots.",
    "recovery_speed": "Slow to reset to base position, exposing the court after shots.",
    "path_efficiency": "Movement routes are indirect, costing time and energy.",
    "avg_speed": "Overall court speed is limiting reaction time on faster rallies.",
    "speed": "Overall court speed is limiting reaction time on faster rallies.",
    "agility": "Directional changes are slower than ideal.",
    "recovery": "Slow to reset to base position, exposing the court after shots.",
}


def get_top_strengths(analytics: dict, n: int = 3) -> list[dict]:
    strengths = analytics.get("top_strengths", [])[:n]
    for s in strengths:
        s["blurb"] = STRENGTH_BLURBS.get(s["metric"], "A consistently strong metric this session.")
    return strengths


def get_top_weaknesses(analytics: dict, n: int = 3) -> list[dict]:
    weaknesses = sorted(analytics.get("top_weaknesses", []), key=lambda w: w["score"])[:n]
    for w in weaknesses:
        w["blurb"] = WEAKNESS_BLURBS.get(w["metric"], "An area worth targeting in upcoming training.")
    return weaknesses


# ---------------------------------------------------------------------------
# Training Priority Meter — top 3 priorities, not just 1
# ---------------------------------------------------------------------------
TRAINING_SUGGESTIONS = {
    "stability": "Single-leg balance drills, core stability work.",
    "recovery_speed": "Shadow footwork drills focused on split-step and return-to-base timing.",
    "recovery": "Shadow footwork drills focused on split-step and return-to-base timing.",
    "path_efficiency": "Cone-based movement drills to reinforce direct court paths.",
    "avg_speed": "Interval sprints and reactive footwork ladders.",
    "speed": "Interval sprints and reactive footwork ladders.",
    "agility": "Multi-directional agility ladder and reaction-ball drills.",
}


def get_training_priorities(analytics: dict, n: int = 3) -> list[dict]:
    """Top n lowest-scoring weaknesses, ranked by urgency (lower score = higher urgency)."""
    weaknesses = sorted(analytics.get("top_weaknesses", []), key=lambda w: w["score"])[:n]
    priorities = []
    for i, w in enumerate(weaknesses, start=1):
        urgency = max(0.0, min(100.0, round(100 - w["score"], 1)))
        priorities.append({
            "rank": i,
            "focus": w["metric"].replace("_", " ").title(),
            "metric_key": w["metric"],
            "score": w["score"],
            "urgency": urgency,
            "suggestion": TRAINING_SUGGESTIONS.get(w["metric"], "General movement conditioning."),
        })
    return priorities


def build_tactical_data(analytics: dict, predictions=None) -> dict:
    predictions = _normalize_predictions(predictions)

    data = {
        "tactical": get_tactical_breakdown(analytics),
        "top_strengths": get_top_strengths(analytics),
        "top_weaknesses": get_top_weaknesses(analytics),
        "training_priorities": get_training_priorities(analytics),
        "session_grade": analytics.get("session_grade", "N/A"),
        "bps": analytics.get("bps", 0),
    }
    data["tactical"]["tendency_text"] = get_tactical_tendency_text(data["tactical"])
    if predictions:
        data["shot_confidence"] = get_avg_shot_confidence(predictions)
        data["shot_counts"] = get_shot_counts(predictions)
    return data


GRADE_EXPLANATIONS = {
    "A+": "Outstanding session across nearly every metric.",
    "A":  "Excellent session with strong fundamentals.",
    "B+": "Very good session — a few areas still to sharpen.",
    "B":  "Solid session with room to grow in weaker components.",
    "C+": "Decent session — performance is inconsistent across metrics.",
    "C":  "Average session — fundamentals present but several gaps.",
    "D":  "Below-target session — multiple metrics need focused training.",
}


def render_session_grade_card(data: dict):
    import streamlit as st

    st.markdown("## 🏆 Session Grade")
    grade = data["session_grade"]
    bps = data["bps"]
    explanation = GRADE_EXPLANATIONS.get(grade, "Performance interpretation unavailable.")

    g1, g2 = st.columns([1, 2])
    g1.metric("Letter Grade", grade)
    g2.metric("BPS (Numeric Score)", f"{bps:.1f}")
    st.caption(explanation)


def render_tactical_charts(data: dict):
    """Plotly pie + stacked bar visuals for forehand/backhand and court-zone usage."""
    import streamlit as st
    import plotly.graph_objects as go

    t = data["tactical"]

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        fig_pie = go.Figure(data=[go.Pie(
            labels=["Forehand", "Backhand"],
            values=[t["forehand_pct"], t["backhand_pct"]],
            hole=0.5,
            marker=dict(colors=["#FF6B4A", "#4FD1C5"]),
        )])
        fig_pie.update_layout(
            title="Forehand vs Backhand Usage",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#EDF1F3"),
            showlegend=True,
            margin=dict(t=40, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with chart_col2:
        depth = t["depth_breakdown"]
        fig_bar = go.Figure(data=[go.Bar(
            x=["Court Usage"],
            y=[depth.get("front", 0)],
            name="Front", marker_color="#FF6B4A",
        ), go.Bar(
            x=["Court Usage"],
            y=[depth.get("mid", 0)],
            name="Mid", marker_color="#E8A33D",
        ), go.Bar(
            x=["Court Usage"],
            y=[depth.get("back", 0)],
            name="Back", marker_color="#4FD1C5",
        )])
        fig_bar.update_layout(
            barmode="stack",
            title="Court Depth Usage (%)",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#EDF1F3"),
            margin=dict(t=40, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    st.caption(
        f"{t['tendency_text']}  \n"
        f"Court zones reached: **{t['zones_used']}/9** ({t['court_usage_pct']:.0f}% coverage)."
    )


def render_tactical_section(
    analytics: dict | None = None,
    predictions=None,
    json_path: str = "data/analytics.json",
    csv_path: str = "data/predictions.csv",
):
    import streamlit as st

    analytics   = get_active_analytics()
    predictions = get_active_predictions()

    data = build_tactical_data(analytics, predictions)

    render_session_grade_card(data)

    st.markdown("## 🎯 Tactical Analysis")
    t = data["tactical"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Forehand %",   f"{t['forehand_pct']:.1f}%")
    c2.metric("Backhand %",   f"{t['backhand_pct']:.1f}%")
    c3.metric("Front Court",  f"{t['depth_breakdown']['front']:.1f}%")
    c4.metric("Mid Court",    f"{t['depth_breakdown']['mid']:.1f}%")
    c5.metric("Back Court",   f"{t['depth_breakdown']['back']:.1f}%")

    render_tactical_charts(data)

    st.markdown("## 💪 Top 3 Strengths")
    for s in data["top_strengths"]:
        st.success(f"**{s['metric'].replace('_', ' ').title()}** — {s['score']:.1f}  \n{s['blurb']}", icon="✅")

    st.markdown("## ⚠️ Top 3 Weaknesses")
    for w in data["top_weaknesses"]:
        st.warning(f"**{w['metric'].replace('_', ' ').title()}** — {w['score']:.1f}  \n{w['blurb']}", icon="⚠️")

    st.markdown("## 📊 Training Priority Meter")
    for p in data["training_priorities"]:
        st.markdown(f"**Priority {p['rank']}: {p['focus']}** (score {p['score']:.1f}, urgency {p['urgency']:.0f}/100)")
        st.progress(p["urgency"] / 100)
        st.caption(f"Suggested drill: {p['suggestion']}")


if __name__ == "__main__":
    analytics = load_analytics("data/analytics.json")
    predictions = load_predictions("data/predictions.csv")
    data = build_tactical_data(analytics, predictions)
    print(json.dumps(data, indent=2))
