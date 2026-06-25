"""
session_utils.py
────────────────
Single source of truth for reading active data in the dashboard.

HOW IT WORKS:
- Demo data is stored under  st.session_state['demo_*']  keys (loaded at app start).
- Upload data is stored under st.session_state['upload_*'] keys (set by upload_section).
- Every getter below checks for upload data FIRST.
  If an upload has happened → returns upload data.
  If no upload yet           → falls back to demo data.

USAGE (in any section file):
    from utils.session_utils import get_active_analytics, get_active_predictions

    analytics   = get_active_analytics()
    predictions = get_active_predictions()

Never read st.session_state['demo_*'] directly in section files.
Always use these getters so sections switch automatically after upload.
"""

import streamlit as st


def get_active_analytics() -> dict:
    upload = st.session_state.get("upload_analytics")
    if upload is not None:
        return upload
    return st.session_state.get("demo_analytics", {})


def get_active_predictions():
    upload = st.session_state.get("upload_predictions")
    if upload is not None:
        return upload
    return st.session_state.get("demo_predictions")


def get_active_landmarks():
    upload = st.session_state.get("upload_landmarks")
    if upload is not None:
        return upload
    return st.session_state.get("demo_landmarks")


def get_active_features():
    upload = st.session_state.get("upload_features")
    if upload is not None:
        return upload
    return st.session_state.get("demo_features")

def get_active_video_path() -> str:
    result = st.session_state.get("upload_result")
    if result is not None:
        return result.get("annotated_video_path", "video/test_annotated_video.mp4")
    return "video/test_annotated_video.mp4"


def is_upload_active() -> bool:
    return st.session_state.get("upload_analytics") is not None


def clear_upload_data():
    """Clears all upload data from session state. Wire to a 'Reset to demo' button."""
    for key in [
        "upload_analytics", "upload_predictions", "upload_landmarks",
        "upload_features", "upload_result",
    ]:
        if key in st.session_state:
            del st.session_state[key]
