"""
app.py — Badminton AI Performance Dashboard

ARCHITECTURE:
    Demo data loads once at startup into demo_* session_state keys.
    Uploading a video writes into upload_* keys (never touches demo_*).
    EVERY section file reads through get_active_*() from session_utils,
    which returns upload data if present, else falls back to demo data.

    This means: app.py does NOT need to know whether upload data exists.
    It just calls section_video(), section_court(), render_identity_section(),
    etc. directly — each one resolves its own active data internally.
    The ONLY exception is Performance, which needs a features DataFrame
    passed in explicitly (scoring_engine.py takes a DataFrame, not a
    session lookup) — handled below via get_active_features().
"""

import os
import json
import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu
from utils.history_section import render_history_section
from utils.db import init_db

from styling import apply_custom_theme

from utils.session_utils import get_active_features, is_upload_active, clear_upload_data
from utils.upload_section import render_upload_section, render_upload_results
from utils.video_section import section_video
from utils.court_section import section_court

from utils.alerts import render_alerts_section
from utils.identity_section import render_identity_section
from utils.tactical_section import render_tactical_section
from utils.coach_report import render_coach_report_section

from utils.performance_section import (
    get_performance_data_from_df,
    render_total_distance,
    render_avg_speed,
    render_peak_speed,
    render_recovery_time,
    render_court_coverage,
    render_bps_inputs,
    render_agility_score,
    render_recovery_score,
    render_explosiveness_score,
    render_consistency_score,
    render_path_efficiency_score,
    render_efficiency_radar,
    render_overall_score,
    render_breakdown,
    render_grade,
    render_numeric_score,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Badminton AI Performance Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_custom_theme()


# ---------------------------------------------------------------------------
# Load DEMO data once into session_state at startup — namespaced so Upload
# can never collide with or overwrite this data.
# ---------------------------------------------------------------------------
def load_demo_data():
    if "demo_landmarks" in st.session_state:
        return  # already loaded this session

    for key, path, loader in [
        ("demo_landmarks",   "data/landmarks.csv",   lambda p: pd.read_csv(p)),
        ("demo_predictions", "data/predictions.csv", lambda p: pd.read_csv(p)),
        ("demo_features",    "data/features.csv",    lambda p: pd.read_csv(p)),
        ("demo_analytics",   "data/analytics.json",  lambda p: json.load(open(p))),
    ]:
        if os.path.exists(path):
            st.session_state[key] = loader(path)
        else:
            st.session_state[key] = {} if key == "demo_analytics" else None

    # Overwrite bps + session_grade in demo_analytics using the same
    # scoring_engine that Performance section uses — single source of truth,
    # so Alerts / Tactical / Coach Report / Identity all show the same score.
    if os.path.exists("data/features.csv") and st.session_state.get("demo_analytics") is not None:
        from utils.scoring_engine import run_full_performance_analysis
        from utils.grade_engine import compute_grade
        features = st.session_state.get("demo_features")
        if features is not None:
            perf = run_full_performance_analysis(features)
            grade_info = compute_grade(perf["bps_score"])
            eff = perf["efficiency_scores"]
            components = {
                "agility":         eff["agility_score"],
                "recovery":        eff["recovery_score"],
                "explosiveness":   eff["explosiveness_score"],
                "consistency":     eff["consistency_score"],
                "path_efficiency": eff["path_efficiency"],
            }
            sorted_desc = sorted(components.items(), key=lambda x: x[1], reverse=True)
            sorted_asc  = sorted(components.items(), key=lambda x: x[1])
            st.session_state["demo_analytics"].update({
                "bps":            perf["bps_score"],
                "session_grade":  grade_info["grade"],
                "top_strengths":  [{"metric": k, "score": v} for k, v in sorted_desc[:3]],
                "top_weaknesses": [{"metric": k, "score": v} for k, v in sorted_asc[:3]],
                "component_scores": components,
            })


load_demo_data()
init_db()   # ensure SQLite table exists


# ---------------------------------------------------------------------------
# Performance data — recomputed fresh from whichever features set is active.
# Demo features are cached (they never change); upload features are NOT
# cached, since a new upload always means new data.
# ---------------------------------------------------------------------------
@st.cache_data
def _performance_from_demo_path(_features_csv_path: str) -> dict:
    features = pd.read_csv(_features_csv_path)
    return get_performance_data_from_df(features)


def get_active_perf_data() -> dict | None:
    if is_upload_active():
        features = get_active_features()
        if features is None:
            return None
        return get_performance_data_from_df(features)
    if os.path.exists("data/features.csv"):
        return _performance_from_demo_path("data/features.csv")
    return None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🏸 Dashboard")

    if is_upload_active():
        st.success("📹 Showing: your uploaded video")
        if st.button("↩️ Reset to demo data", use_container_width=True):
            clear_upload_data()
            st.session_state.pop("court_coverage_result", None)
            st.rerun()
    else:
        st.info("📁 Showing: demo session")

    selected = option_menu(
        menu_title=None,
        options=[
            "Video", "Upload", "Court",
            "Performance",
            "Identity", "Alerts", "Tactical", "Report", "History",
        ],
        icons=[
            "camera-video", "cloud-upload", "geo-alt",
            "bar-chart-line",
            "person-badge", "exclamation-triangle", "diagram-3", "robot", "clock-history",
        ],
        menu_icon="cast",
        default_index=0,
    )

st.title("🏸 Badminton AI Performance Dashboard")

# ---------------------------------------------------------------------------
# Section router — every branch is now a one-liner. All dynamism lives
# inside session_utils.get_active_*(), not here.
# ---------------------------------------------------------------------------

# ── Upload ───────────────────────────────────────────────────────────────
if selected == "Upload":
    result = render_upload_section()
    if result:
        render_upload_results(result)
    elif is_upload_active():
        # Revisiting the tab without re-uploading — show the last result
        render_upload_results(st.session_state.get("upload_result"))

# ── Video ────────────────────────────────────────────────────────────────
elif selected == "Video":
    section_video()

# ── Court ────────────────────────────────────────────────────────────────
elif selected == "Court":
    court_result = section_court()
    if court_result:
        st.session_state["court_coverage_result"] = court_result

# ── Performance (Member 2) ───────────────────────────────────────────────
elif selected == "Performance":
    st.markdown("## 📈 Performance Analytics")

    perf_data = get_active_perf_data()
    if perf_data is None:
        st.error(
            "No features data available. Upload a video in the Upload tab, "
            "or make sure data/features.csv exists for the demo."
        )
    else:
        court_coverage_data = st.session_state.get("court_coverage_result")

        st.markdown("### Match Overview")
        mo1, mo2, mo3 = st.columns(3)
        with mo1:
            render_total_distance(perf_data)
        with mo2:
            render_avg_speed(perf_data)
        with mo3:
            render_peak_speed(perf_data)
        render_recovery_time(perf_data)
        render_court_coverage(perf_data, court_coverage_data)
        render_bps_inputs(perf_data)

        st.divider()
        st.markdown("### Movement Efficiency")
        ef1, ef2, ef3, ef4, ef5 = st.columns(5)
        with ef1:
            render_agility_score(perf_data)
        with ef2:
            render_recovery_score(perf_data)
        with ef3:
            render_explosiveness_score(perf_data)
        with ef4:
            render_consistency_score(perf_data)
        with ef5:
            render_path_efficiency_score(perf_data)
        render_efficiency_radar(perf_data)

        st.divider()
        st.markdown("### BPS Score")
        bps_col1, bps_col2 = st.columns(2)
        with bps_col1:
            render_overall_score(perf_data)
        with bps_col2:
            render_breakdown(perf_data)

        st.divider()
        st.markdown("### Session Grade")
        grade_col1, grade_col2 = st.columns(2)
        with grade_col1:
            render_grade(perf_data)
        with grade_col2:
            render_numeric_score(perf_data)

# ── Identity (Member 3) ──────────────────────────────────────────────────
elif selected == "Identity":
    render_identity_section()

# ── Alerts (Member 3) ────────────────────────────────────────────────────
elif selected == "Alerts":
    render_alerts_section()

# ── Tactical (Member 3) ──────────────────────────────────────────────────
elif selected == "Tactical":
    render_tactical_section()

# ── AI Coach Report (Member 3) ───────────────────────────────────────────
elif selected == "Report":
    render_coach_report_section()
elif selected == "History":
    render_history_section()




#st.write(st.session_state)
