import os
import tempfile
import traceback
import streamlit as st
from pipeline.run_pipeline import load_model_and_encoder, run_full_pipeline
from utils.db import save_session


@st.cache_resource
def get_model_and_encoder():
    return load_model_and_encoder()


def render_upload_section():
    st.markdown("### 🎬 Upload a Match Video")
    st.caption("Upload a raw .mp4 clip to run pose detection → footwork classification → annotated video.")

    uploaded_file = st.file_uploader("Choose a video file", type=["mp4", "mov", "avi"])
    if uploaded_file is None:
        return None

    process_clicked = st.button("▶️ Process Video", type="primary")
    if not process_clicked:
        st.info("Click 'Process Video' to run the pipeline.")
        return None

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(uploaded_file.read())
        temp_video_path = tmp.name

    model, encoder = get_model_and_encoder()
    if model is None:
        st.warning("rf.pkl not found in data/ — video will be annotated with skeleton/bbox only, no footwork predictions.")

    progress_bar = st.progress(0, text="Starting...")

    def update_progress(stage, current, total):
        pct = current / total if total else 0
        progress_bar.progress(min(pct, 1.0), text=f"{stage}: {current}/{total}")

    try:
        with st.spinner("Processing video — this may take a minute..."):
            result = run_full_pipeline(
                temp_video_path, model, encoder, progress_callback=update_progress
            )

        st.success(
            f"✅ Processing complete! Pose detected in "
            f"{result['detected_frame_count']}/{result['total_frames']} frames."
        )

        # ── SAVE ALL RESULTS TO SESSION STATE ─────────────────────────────
        # Uses upload_* keys so demo_* keys are NEVER overwritten.
        # Every other section reads these via get_active_*() from session_utils.
        st.session_state["upload_analytics"]   = result.get("analytics")       # analytics dict
        st.session_state["upload_predictions"] = result.get("predictions_df")  # DataFrame
        st.session_state["upload_landmarks"]   = result.get("landmarks_df")    # DataFrame
        st.session_state["upload_features"]    = result.get("features_df")     # DataFrame

        # THE FIX: also store the raw result dict so video_section.py (a
        # DIFFERENT tab) can find the correct annotated_video_path via
        # get_active_video_path(). Without this, the Video tab kept drawing
        # the uploaded video's skeleton onto the OLD demo video file.
        st.session_state["upload_result"] = result

        # ── PERSIST TO DATABASE ────────────────────────────────────────────
        try:
            analytics = result.get("analytics") or {}
            save_session(
                filename=uploaded_file.name,
                result=result,
                analytics=analytics,
            )
        except Exception as db_err:
            st.warning(f"Session saved but database write failed: {db_err}")

        if result["detected_frame_count"] < result["total_frames"] * 0.5:
            st.warning(
                "⚠️ Pose was only detected in fewer than half the frames. "
                "Overlays will be missing on undetected frames. "
                "Check lighting/framing in the source video."
            )

        return result

    except Exception as e:
        st.error(f"❌ Pipeline failed: {e}")
        with st.expander("Full error details (for debugging)"):
            st.code(traceback.format_exc())
        return None

    finally:
        os.unlink(temp_video_path)


def render_upload_results(result: dict):
    if result is None:
        return

    st.subheader("🎥 Uploaded Video — Analysis Results")

    video_path = result["annotated_video_path"]
    if not os.path.exists(video_path):
        st.error(f"Annotated video file not found at {video_path}")
        return

    col1, col2 = st.columns([1.3, 1])

    with col1:
        with open(video_path, "rb") as f:
            video_bytes = f.read()
        # Serve as bytes not path — avoids browser URL caching of old videos
        st.video(video_bytes)

    with col2:
        st.markdown("**Processing Summary**")
        st.metric("Total Frames Processed",    result["total_frames"])
        st.metric("Frames With Pose Detected", result["detected_frame_count"])
        st.metric("Footwork Labels Detected",  len(result["label_counts"]))

        st.markdown("**Footwork Label Breakdown**")
        for label, count in result["label_counts"].items():
            pct      = round(100 * count / result["total_frames"], 1)
            avg_conf = result["label_confidence"].get(label, 0.0)
            st.write(
                f"**{label}** — {count} frames ({pct}%) "
                f"· avg confidence {avg_conf * 100:.0f}%"
            )


