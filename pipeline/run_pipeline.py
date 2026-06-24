import os
import time
import cv2
import numpy as np
import pandas as pd
import joblib
import subprocess
import imageio_ffmpeg

# NOTE: mediapipe is imported LAZILY inside run_full_pipeline() only,
# NOT at module level. This prevents the "module has no attribute solutions"
# crash on Streamlit Cloud where mediapipe loads differently.

MODEL_JOINTS = [
    "left_shoulder", "right_shoulder", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
    "left_foot", "right_foot",
]

ROLLING_WINDOW = 5
COURT_ZONES_X = 3
COURT_ZONES_Y = 3

SKELETON_EDGES = [
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"), ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
]

RF_MODEL_PATH = "data/rf.pkl"


def load_model_and_encoder():
    model = joblib.load(RF_MODEL_PATH) if os.path.exists(RF_MODEL_PATH) else None
    encoder = None
    return model, encoder


def _build_model_features(landmarks_df: pd.DataFrame, fps: float) -> pd.DataFrame:
    df = landmarks_df.sort_values("frame", kind="stable").reset_index(drop=True)
    f = pd.DataFrame()
    f["frame"] = df["frame"]

    x_cols = [f"{j}_x" for j in MODEL_JOINTS]
    y_cols = [f"{j}_y" for j in MODEL_JOINTS]
    for c in x_cols + y_cols:
        f[c] = df[c] if c in df.columns else np.nan
    for c in x_cols + y_cols:
        f[c] = f[c].ffill().bfill().fillna(0.5)

    f["centroid_x"] = f[x_cols].mean(axis=1)
    f["centroid_y"] = f[y_cols].mean(axis=1)
    f["hip_center_x"] = (f["left_hip_x"] + f["right_hip_x"]) / 2
    f["hip_center_y"] = (f["left_hip_y"] + f["right_hip_y"]) / 2
    f["stance_width"] = np.sqrt(
        (f["left_ankle_x"] - f["right_ankle_x"])**2 +
        (f["left_ankle_y"] - f["right_ankle_y"])**2
    )

    f["dx"] = f["centroid_x"].diff().fillna(0)
    f["dy"] = f["centroid_y"].diff().fillna(0)
    f["distance"] = np.sqrt(f["dx"]**2 + f["dy"]**2)
    f["speed"] = f["distance"]

    f["centroid_x_smooth"] = f["centroid_x"].rolling(ROLLING_WINDOW, min_periods=1, center=True).mean()
    f["centroid_y_smooth"] = f["centroid_y"].rolling(ROLLING_WINDOW, min_periods=1, center=True).mean()
    f["rolling_speed_mean"] = f["speed"].rolling(ROLLING_WINDOW, min_periods=1).mean()
    f["rolling_speed_std"] = f["speed"].rolling(ROLLING_WINDOW, min_periods=1).std().fillna(0)
    f["speed_smoothed"] = f["rolling_speed_mean"]
    f["acceleration"] = f["speed"].diff().fillna(0)

    f["cumulative_distance"] = f["distance"].cumsum()
    f["path_length"] = f["cumulative_distance"]
    f["straight_distance"] = np.sqrt(
        (f["centroid_x"] - f["centroid_x"].iloc[0])**2 +
        (f["centroid_y"] - f["centroid_y"].iloc[0])**2
    )
    f["path_efficiency"] = np.where(
        f["cumulative_distance"] > 0,
        f["straight_distance"] / f["cumulative_distance"],
        0.0
    )

    angle = np.degrees(np.arctan2(f["dy"], f["dx"]))

    def classify_direction(dx_, dy_, ang_):
        speed = np.sqrt(dx_**2 + dy_**2)
        if speed < 1e-4:
            return "STILL"
        if -45 <= ang_ <= 45:
            return "RIGHT"
        elif 45 < ang_ <= 135:
            return "FORWARD"
        elif ang_ > 135 or ang_ <= -135:
            return "LEFT"
        return "BACKWARD"

    directions = [classify_direction(dx_, dy_, ang_) for dx_, dy_, ang_ in zip(f["dx"], f["dy"], angle)]
    direction_map = {"STILL": 0, "FORWARD": 1, "BACKWARD": 2, "LEFT": 3, "RIGHT": 4}
    f["direction_code"] = [direction_map[d] for d in directions]
    for d in ["BACKWARD", "FORWARD", "LEFT", "RIGHT", "STILL"]:
        f[f"direction_{d}"] = [1 if dd == d else 0 for dd in directions]
    f["direction_change"] = (pd.Series(directions) != pd.Series(directions).shift(1)).astype(int)
    f.loc[0, "direction_change"] = 0
    f["trajectory_angle"] = angle.fillna(0)

    f["movement_range_x"] = (
        f["centroid_x"].rolling(ROLLING_WINDOW, min_periods=1).max() -
        f["centroid_x"].rolling(ROLLING_WINDOW, min_periods=1).min()
    )
    f["movement_range_y"] = (
        f["centroid_y"].rolling(ROLLING_WINDOW, min_periods=1).max() -
        f["centroid_y"].rolling(ROLLING_WINDOW, min_periods=1).min()
    )

    x_norm = f["centroid_x"].clip(0, 1)
    y_norm = f["centroid_y"].clip(0, 1)
    col = np.floor(x_norm * COURT_ZONES_X).clip(0, COURT_ZONES_X - 1).astype(int)
    row = np.floor(y_norm * COURT_ZONES_Y).clip(0, COURT_ZONES_Y - 1).astype(int)
    f["court_zone"] = row * COURT_ZONES_X + col

    pos_std = (
        f["centroid_x"].rolling(ROLLING_WINDOW, min_periods=1).std().fillna(0) +
        f["centroid_y"].rolling(ROLLING_WINDOW, min_periods=1).std().fillna(0)
    )
    f["stability_index"] = 1 / (1 + pos_std)

    baseline_x = f["hip_center_x"].median()
    baseline_y = f["hip_center_y"].median()
    f["recovery_distance"] = np.sqrt(
        (f["hip_center_x"] - baseline_x)**2 +
        (f["hip_center_y"] - baseline_y)**2
    )
    moving = f["speed"] > f["speed"].median()
    recovery_time, counter = [], 0
    for is_moving in moving:
        counter = counter + 1 if is_moving else 0
        recovery_time.append(counter)
    f["recovery_time"] = recovery_time

    return f


# ── _compute_analytics — PATCHED ────────────────────────────────────────────
# Three bugs fixed here so identity_section.py / tactical_section.py /
# alerts.py / coach_report.py work correctly on uploaded videos:
#
#   1. top_strengths / top_weaknesses were plain strings ("speed", "stability").
#      identity_section.py and tactical_section.py both do `s["metric"]` /
#      `s["score"]` on these — that's a TypeError on a plain string. Now
#      shaped as {"metric": ..., "score": ...} dicts, matching demo analytics.json.
#
#   2. court_zone_coverage was RAW FRAME COUNTS with 0-indexed zone keys
#      ("0".."8"). identity_section.py's ZONE_LABELS / ZONE_DEPTH and
#      tactical_section.py's ZONE_DEPTH both expect PERCENTAGES with
#      1-indexed keys ("1".."9"). Without this fix, every zone lookup
#      silently misses and "Court Preference" / depth breakdowns show
#      all-zero / "Unknown" even on a perfectly good upload.
#
#   3. avg_recovery_distance and avg_stance_width were missing entirely —
#      identity_section.py's determine_style_tags() and coach_report.py's
#      generate_recovery_recommendations() both read these fields directly.
def _compute_analytics(landmarks_df, features_df, predictions_df, fps, detected_frame_count):
    total_frames = len(landmarks_df)
    duration = total_frames / fps if fps else 0

    action_counts = predictions_df["prediction"].value_counts().to_dict()
    action_percentages = (
        predictions_df["prediction"].value_counts(normalize=True) * 100
    ).round(1).to_dict()

    avg_speed_raw  = float(features_df["speed"].mean())
    peak_speed_raw = float(features_df["speed"].max())
    avg_speed_px   = round(avg_speed_raw  * fps * 1440, 2)
    peak_speed_px  = round(peak_speed_raw * fps * 1440, 2)
    total_distance = round(float(features_df["distance"].sum()) * 1440, 1)

    avg_path_efficiency   = float(features_df["path_efficiency"].mean())
    avg_stability         = float(features_df["stability_index"].mean())
    avg_recovery_distance = float(features_df["recovery_distance"].mean())
    avg_stance_width      = float(features_df["stance_width"].mean())

    forehand_frames  = sum(v for k, v in action_counts.items() if "Forehand"  in k)
    backhand_frames  = sum(v for k, v in action_counts.items() if "Backhand"  in k)
    recovery_frames  = action_counts.get("Recovery_Ready", 0)
    forehand_pct     = round(forehand_frames  / total_frames * 100, 1) if total_frames else 0
    backhand_pct     = round(backhand_frames  / total_frames * 100, 1) if total_frames else 0
    recovery_ratio   = recovery_frames / total_frames if total_frames else 0

    # FIX #2: percentages + 1-indexed keys ("1".."9"), matching the
    # ZONE_LABELS / ZONE_DEPTH maps used elsewhere in the dashboard.
    zone_counts_0idx = features_df["court_zone"].value_counts()
    zone_total = zone_counts_0idx.sum()
    zone_coverage = {
        str(int(zone) + 1): round(100 * count / zone_total, 1)
        for zone, count in zone_counts_0idx.items()
    } if zone_total else {}

    # Use scoring_engine + grade_engine as the single source of truth for
    # BPS and grade — same formula the Performance section uses, so all
    # sections (Alerts, Tactical, Coach Report, Performance) agree.
    from utils.scoring_engine import run_full_performance_analysis
    from utils.grade_engine import compute_grade

    perf = run_full_performance_analysis(features_df)
    grade_info = compute_grade(perf["bps_score"])
    bps   = perf["bps_score"]
    grade = grade_info["grade"]

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
    top_strengths  = [{"metric": k, "score": v} for k, v in sorted_desc[:3]]
    top_weaknesses = [{"metric": k, "score": v} for k, v in sorted_asc[:3]]

    segments = []
    if len(predictions_df):
        prev_label = None
        seg_start  = 0
        for i, row in predictions_df.iterrows():
            label = row["prediction"]
            if label != prev_label:
                if prev_label is not None:
                    segments.append({
                        "action":      prev_label,
                        "start_frame": seg_start,
                        "end_frame":   i - 1,
                        "frame_count": i - seg_start,
                    })
                prev_label = label
                seg_start  = i
        segments.append({
            "action":      prev_label,
            "start_frame": seg_start,
            "end_frame":   len(predictions_df) - 1,
            "frame_count": len(predictions_df) - seg_start,
        })

    return {
        "total_frames":          total_frames,
        "fps":                   round(fps, 3),
        "duration_seconds":      round(duration, 1),
        "action_counts":         action_counts,
        "action_percentages":    action_percentages,
        "num_segments":          len(segments),
        "segments":              segments,
        "avg_speed":             avg_speed_px,
        "peak_speed":            peak_speed_px,
        "total_distance":        total_distance,
        "avg_path_efficiency":   round(avg_path_efficiency, 4),
        "avg_stability_index":   round(avg_stability, 4),
        "avg_recovery_distance": round(avg_recovery_distance, 4),   # FIX #3
        "avg_stance_width":      round(avg_stance_width, 4),         # FIX #3
        "forehand_usage":        forehand_pct,
        "backhand_usage":        backhand_pct,
        "court_zone_coverage":   zone_coverage,
        "bps":                   bps,
        "session_grade":         grade,
        "top_strengths":         top_strengths,
        "top_weaknesses":        top_weaknesses,
        "pose_detection_rate":   round(detected_frame_count / total_frames, 3) if total_frames else 0,
        "component_scores":      components,
    }


def run_full_pipeline(video_path, model, encoder, progress_callback=None):
    # Import mediapipe HERE (lazy) so module-level import never runs on Streamlit Cloud
    import mediapipe as mp

    import mediapipe as mp

print("DEBUG MEDIAPIPE:", mp)
print("DEBUG FILE:", getattr(mp, "__file__", "NO_FILE"))
print("DEBUG HAS_SOLUTIONS:", hasattr(mp, "solutions"))

mp_pose = mp.solutions.pose

    LANDMARK_INDEX = {
        "nose":           mp_pose.PoseLandmark.NOSE.value,
        "left_shoulder":  mp_pose.PoseLandmark.LEFT_SHOULDER.value,
        "right_shoulder": mp_pose.PoseLandmark.RIGHT_SHOULDER.value,
        "left_elbow":     mp_pose.PoseLandmark.LEFT_ELBOW.value,
        "right_elbow":    mp_pose.PoseLandmark.RIGHT_ELBOW.value,
        "left_wrist":     mp_pose.PoseLandmark.LEFT_WRIST.value,
        "right_wrist":    mp_pose.PoseLandmark.RIGHT_WRIST.value,
        "left_hip":       mp_pose.PoseLandmark.LEFT_HIP.value,
        "right_hip":      mp_pose.PoseLandmark.RIGHT_HIP.value,
        "left_knee":      mp_pose.PoseLandmark.LEFT_KNEE.value,
        "right_knee":     mp_pose.PoseLandmark.RIGHT_KNEE.value,
        "left_ankle":     mp_pose.PoseLandmark.LEFT_ANKLE.value,
        "right_ankle":    mp_pose.PoseLandmark.RIGHT_ANKLE.value,
        "left_foot":      mp_pose.PoseLandmark.LEFT_FOOT_INDEX.value,
        "right_foot":     mp_pose.PoseLandmark.RIGHT_FOOT_INDEX.value,
    }

    run_id      = int(time.time() * 1000)
    output_path = f"video/uploaded_annotated_{run_id}.mp4"
    os.makedirs("video", exist_ok=True)
    temp_output       = output_path.replace(".mp4", "_temp.mp4")
    skeleton_video_path = output_path.replace(".mp4", "_skeleton.mp4")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open input video: {video_path}")

    fps          = cap.get(cv2.CAP_PROP_FPS) or 30
    w            = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h            = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(skeleton_video_path, fourcc, fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"cv2.VideoWriter failed to open for {skeleton_video_path}.")

    landmarks_rows      = []
    detected_frame_count = 0

    # ── PASS 1: Pose detection + draw skeleton ─────────────────────────────
    with mp_pose.Pose(
        model_complexity=1,
        min_detection_confidence=0.3,
        min_tracking_confidence=0.3
    ) as pose:
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            target_long_side = 720
            scale = target_long_side / max(w, h)
            small = cv2.resize(frame, (int(w * scale), int(h * scale)))
            rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            result = pose.process(rgb)

            row = {"frame": frame_idx}
            xs, ys   = [], []
            joint_px = {}

            if result.pose_landmarks:
                detected_frame_count += 1
                lm = result.pose_landmarks.landmark
                for name, idx in LANDMARK_INDEX.items():
                    point = lm[idx]
                    row[f"{name}_x"] = point.x
                    row[f"{name}_y"] = point.y
                    px_, py_ = int(point.x * w), int(point.y * h)
                    joint_px[name] = (px_, py_)
                    xs.append(px_)
                    ys.append(py_)

                for a, b in SKELETON_EDGES:
                    if a in joint_px and b in joint_px:
                        cv2.line(frame, joint_px[a], joint_px[b], (255, 255, 255), 3, cv2.LINE_AA)
                for px_, py_ in joint_px.values():
                    cv2.circle(frame, (px_, py_), 6, (0, 200, 255), -1, cv2.LINE_AA)

            landmarks_rows.append(row)

            if xs and ys:
                cv2.rectangle(
                    frame,
                    (min(xs) - 15, min(ys) - 15),
                    (max(xs) + 15, max(ys) + 15),
                    (0, 0, 255), 3, cv2.LINE_AA
                )

            writer.write(frame)
            frame_idx += 1
            if progress_callback:
                progress_callback("Detecting pose", frame_idx, total_frames)

    cap.release()
    writer.release()

    if detected_frame_count == 0:
        raise RuntimeError(
            "MediaPipe detected ZERO poses in this video. "
            "Check that a person is clearly visible and well-lit in frame."
        )

    landmarks_df = pd.DataFrame(landmarks_rows)

    # ── BATCH: Feature engineering ─────────────────────────────────────────
    if progress_callback:
        progress_callback("Computing movement features", 1, 1)
    features_df = _build_model_features(landmarks_df, fps)

    # ── BATCH: RF prediction ───────────────────────────────────────────────
    predictions_rows  = []
    expected_features = list(getattr(model, "feature_names_in_", [])) if model else []

    if model is not None and expected_features:
        missing = [c for c in expected_features if c not in features_df.columns]
        if missing:
            raise RuntimeError(f"Computed features missing columns the model needs: {missing}")
        X          = features_df[expected_features]
        probs_all  = model.predict_proba(X)
        pred_labels = model.classes_[probs_all.argmax(axis=1)]
        confidences = probs_all.max(axis=1)
        for i, frame_num in enumerate(features_df["frame"]):
            predictions_rows.append({
                "frame":      int(frame_num),
                "prediction": pred_labels[i],
                "confidence": float(confidences[i]),
            })
    else:
        for frame_num in features_df["frame"]:
            predictions_rows.append({
                "frame":      int(frame_num),
                "prediction": "No Model",
                "confidence": 0.0,
            })

    predictions_df = pd.DataFrame(predictions_rows)
    pred_by_frame  = predictions_df.set_index("frame")

    # ── PASS 2: Burn labels onto skeleton video ────────────────────────────
    cap2    = cv2.VideoCapture(skeleton_video_path)
    writer2 = cv2.VideoWriter(temp_output, fourcc, fps, (w, h))
    if not writer2.isOpened():
        raise RuntimeError(f"cv2.VideoWriter failed to open for {temp_output} (pass 2).")

    frame_idx = 0
    while True:
        ret, frame = cap2.read()
        if not ret:
            break
        if frame_idx in pred_by_frame.index:
            pred_label = pred_by_frame.loc[frame_idx, "prediction"]
            confidence = pred_by_frame.loc[frame_idx, "confidence"]
        else:
            pred_label, confidence = "No Pose", 0.0

        label_text    = f"{pred_label} ({confidence * 100:.0f}%)"
        (tw, th), _   = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
        cv2.rectangle(frame, (5, 5), (15 + tw, 15 + th + 15), (0, 0, 0), -1)
        cv2.putText(frame, label_text, (10, 15 + th),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA)

        writer2.write(frame)
        frame_idx += 1
        if progress_callback:
            progress_callback("Burning in labels", frame_idx, total_frames)

    cap2.release()
    writer2.release()

    if os.path.exists(skeleton_video_path):
        os.remove(skeleton_video_path)

    # ── Re-encode to H.264 for browser playback ────────────────────────────
    if progress_callback:
        progress_callback("Re-encoding for browser", 1, 1)
    _reencode_for_browser(temp_output, output_path)

    if os.path.exists(temp_output):
        os.remove(temp_output)

    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        raise RuntimeError(
            f"Final output video at {output_path} is missing or too small — "
            "the writer or ffmpeg re-encode silently failed."
        )

    # ── Compute analytics dict ─────────────────────────────────────────────
    if progress_callback:
        progress_callback("Computing analytics", 1, 1)

    analytics_dict = _compute_analytics(
        landmarks_df, features_df, predictions_df, fps, detected_frame_count
    )

    label_counts     = predictions_df["prediction"].value_counts().to_dict()
    label_confidence = predictions_df.groupby("prediction")["confidence"].mean().to_dict()

    # ── Return everything with CORRECT key names ───────────────────────────
    return {
        "annotated_video_path":  output_path,
        "total_frames":          len(landmarks_df),
        "detected_frame_count":  detected_frame_count,
        "label_counts":          label_counts,
        "label_confidence":      label_confidence,
        "landmarks_df":          landmarks_df,       # used by upload_section
        "predictions_df":        predictions_df,     # used by upload_section
        "features_df":           features_df,        # used by upload_section
        "analytics":             analytics_dict,     # used by upload_section
    }


def _reencode_for_browser(input_path, output_path):
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg_exe, "-y", "-i", input_path,
         "-vcodec", "libx264", "-pix_fmt", "yuv420p", output_path],
        capture_output=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg re-encode failed: {result.stderr.decode(errors='ignore')[-800:]}"
        )
