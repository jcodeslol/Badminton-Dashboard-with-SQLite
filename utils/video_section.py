import streamlit as st
import os
import cv2
import numpy as np
import pandas as pd
from utils.session_utils import get_active_landmarks, get_active_predictions, get_active_video_path


def section_video():
    st.subheader("🎥 Video Analysis Preview")

    if "demo_landmarks" not in st.session_state or "demo_predictions" not in st.session_state:
        st.error(
            "Demo landmarks/predictions not found in session_state. "
            "Make sure app.py loads data/landmarks.csv and data/predictions.csv "
            "into 'demo_landmarks' / 'demo_predictions' at startup."
        )
        return

    landmarks   = get_active_landmarks()
    predictions = get_active_predictions()
    video_path = get_active_video_path()

    if predictions is None:
        st.warning("No predictions available yet. Upload and process a video first.")
        return

    if landmarks is None:
        st.warning("No landmarks available yet. Upload and process a video first.")
        return
    
    col1, col2 = st.columns([1.3, 1])

    with col1:
        if os.path.exists(video_path):
            with open(video_path, "rb") as f:
                st.video(f.read())
        else:
            st.warning(f"Video not found at {video_path} — showing summary only.")

    with col2:
        st.markdown("**Processing Summary**")
        total_frames = len(predictions)
        st.metric("Frames Processed", total_frames)
        st.metric("Predicted Classes", predictions["prediction"].nunique())

        st.markdown("**Pipeline Status**")
        st.progress(1.0, text="Frames → Landmarks → Features → RF Predictions ✅")

    st.divider()
    _frame_inspector(landmarks, predictions, video_path)


def _frame_inspector(landmarks, predictions, video_path):
    st.markdown("**🔍 Frame Inspector — Skeleton + Bounding Box + RF Prediction**")

    video_frame_count = _get_video_frame_count(video_path)
    landmarks_frame_count = len(landmarks)

    if video_frame_count is not None and video_frame_count != landmarks_frame_count:
        st.warning(
            f"⚠️ Data mismatch: video has {video_frame_count} frames but "
            f"landmarks data has {landmarks_frame_count} rows. Showing the "
            f"smaller of the two to avoid out-of-range seeks."
        )

    max_frame = min(
        landmarks_frame_count,
        video_frame_count if video_frame_count is not None else landmarks_frame_count,
    ) - 1
    max_frame = max(max_frame, 0)

    frame_idx = st.slider("Select frame", 0, max_frame, 0)

    row = landmarks.iloc[frame_idx]
    pred_row = predictions.iloc[frame_idx] if frame_idx < len(predictions) else None

    img, frame_read_ok = _get_raw_frame(video_path, frame_idx)
    if not frame_read_ok:
        st.error(f"Could not read frame {frame_idx} from {video_path}.")
        return

    img = _draw_skeleton(img, row)
    img = _draw_bounding_box(img, row)

    if pred_row is not None:
        label = pred_row["prediction"]
        cv2.putText(img, f"Prediction: {label}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    img_col, _ = st.columns([1, 1])
    with img_col:
        st.image(img, channels="BGR", width=420)


def _get_video_frame_count(video_path):
    if not os.path.exists(video_path):
        return None
    cap = cv2.VideoCapture(video_path)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return count if count > 0 else None


def _get_raw_frame(video_path, frame_idx):
    if os.path.exists(video_path):
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        cap.release()
        if ret:
            return frame, True
    return np.full((480, 640, 3), 30, dtype=np.uint8), False


def _draw_skeleton(img, row):
    h, w = img.shape[:2]

    x_cols = [c for c in row.index if c.endswith("_x")]

    for x_col in x_cols:
        y_col = x_col[:-2] + "_y"

        if y_col not in row.index:
            continue

        # Skip missing or invalid landmark values
        if pd.isna(row[x_col]) or pd.isna(row[y_col]):
            continue

        try:
            x_px = int(float(row[x_col]) * w)
            y_px = int(float(row[y_col]) * h)
        except (ValueError, TypeError):
            continue

        cv2.circle(img, (x_px, y_px), 4, (0, 200, 255), -1)

    return img
def _draw_bounding_box(img, row):
    h, w = img.shape[:2]

    x_vals = []
    y_vals = []

    for col in row.index:
        if col.endswith("_x") and not pd.isna(row[col]):
            x_vals.append(float(row[col]) * w)
        elif col.endswith("_y") and not pd.isna(row[col]):
            y_vals.append(float(row[col]) * h)

    if not x_vals or not y_vals:
        return img

    x_min, x_max = min(x_vals), max(x_vals)
    y_min, y_max = min(y_vals), max(y_vals)

    cv2.rectangle(
        img,
        (int(x_min), int(y_min)),
        (int(x_max), int(y_max)),
        (0, 255, 0),
        2,
    )

    return img