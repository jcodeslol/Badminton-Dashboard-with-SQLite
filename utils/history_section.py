"""
utils/history_section.py
────────────────────────
Renders the History tab — a table of all past uploaded sessions
pulled from SQLite via utils/db.py.

Shows: date, filename, frames, detection rate, BPS, grade,
       duration, forehand/backhand split, top strength, top weakness.
Allows deleting individual rows.
"""

import streamlit as st
import pandas as pd
from utils.db import get_session_history, delete_session


# Grade → colour mapping matches styling.py signal palette
_GRADE_COLORS = {
    "A+": "#00E5A0",
    "A":  "#00E5A0",
    "B+": "#4AE8A0",
    "B":  "#8AE87A",
    "C+": "#F5A623",
    "C":  "#F5A623",
    "D":  "#E8503A",
}


def _grade_badge(grade: str) -> str:
    color = _GRADE_COLORS.get(grade, "#8A9E8D")
    return (
        f'<span style="'
        f'background:rgba({_hex_to_rgb(color)},0.12);'
        f'border:1px solid {color};'
        f'color:{color};'
        f'border-radius:3px;'
        f'padding:2px 8px;'
        f'font-family:Rajdhani,sans-serif;'
        f'font-weight:700;'
        f'font-size:0.9rem;'
        f'letter-spacing:0.04em;'
        f'">{grade}</span>'
    )


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"


def _bps_bar(bps: float) -> str:
    pct = min(max(bps, 0), 100)
    if pct >= 70:
        color = "#00E5A0"
    elif pct >= 50:
        color = "#F5A623"
    else:
        color = "#E8503A"
    return (
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<div style="flex:1;background:#1F2820;border-radius:2px;height:4px;">'
        f'<div style="width:{pct}%;background:{color};height:4px;border-radius:2px;"></div>'
        f'</div>'
        f'<span style="font-family:\'DM Mono\',monospace;font-size:0.8rem;'
        f'color:{color};min-width:36px;">{bps:.1f}</span>'
        f'</div>'
    )


def render_history_section():
    st.markdown("## 📁 Session History")
    st.caption("All previously processed video uploads stored in the local database.")

    df = get_session_history()

    if df.empty:
        st.info("No sessions recorded yet. Upload and process a video to get started.")
        return

    # ── Summary stats across all sessions ────────────────────────────────
    total   = len(df)
    avg_bps = df["bps"].mean()
    best    = df.loc[df["bps"].idxmax()]
    grades  = df["grade"].value_counts()

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total Sessions",  total)
    s2.metric("Avg BPS",         f"{avg_bps:.1f}")
    s3.metric("Best Grade",      best["grade"])
    s4.metric("Best BPS",        f"{best['bps']:.1f}")

    st.divider()

    # ── Per-session cards ─────────────────────────────────────────────────
    for _, row in df.iterrows():
        with st.container():
            # Header row: filename + grade badge + delete button
            h1, h2, h3 = st.columns([4, 1, 1])
            with h1:
                st.markdown(
                    f"**{row['filename']}** &nbsp; "
                    f"<span style='color:#4D5E50;font-size:0.75rem;'>{row['uploaded_at']}</span>",
                    unsafe_allow_html=True
                )
            with h2:
                st.markdown(_grade_badge(row["grade"]), unsafe_allow_html=True)
            with h3:
                if st.button("🗑 Delete", key=f"del_{row['id']}", use_container_width=True):
                    delete_session(int(row["id"]))
                    st.rerun()

            # Metrics row
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("BPS",            f"{row['bps']:.1f}")
            m2.metric("Total Frames",   int(row["total_frames"]))
            m3.metric("Detection Rate", f"{row['detection_rate']:.1f}%")
            m4.metric("Duration",       f"{row['duration_sec']:.1f}s")
            m5.metric("Forehand",       f"{row['forehand_pct']:.1f}%")
            m6.metric("Backhand",       f"{row['backhand_pct']:.1f}%")

            # Strength / weakness pills
            pill_col1, pill_col2, _ = st.columns([2, 2, 4])
            if row.get("top_strength"):
                pill_col1.success(f"💪 {row['top_strength']}", icon=None)
            if row.get("top_weakness"):
                pill_col2.warning(f"⚠️ {row['top_weakness']}", icon=None)

            # BPS progress bar
            st.markdown(_bps_bar(row["bps"]), unsafe_allow_html=True)
            st.markdown(
                "<div style='border-bottom:1px solid #1F2820;margin:14px 0 10px 0;'></div>",
                unsafe_allow_html=True
            )

    # ── Raw table toggle ──────────────────────────────────────────────────
    with st.expander("📋 Raw data table"):
        display_df = df.drop(columns=["video_path"], errors="ignore")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
