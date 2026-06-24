"""
utils/db.py
───────────
SQLite persistence for the Badminton AI Dashboard.

One table: sessions
One row per processed video upload.

Public API:
    init_db()                        → None   call once at app startup
    save_session(filename, result, analytics) → int (row id)
    get_session_history()            → pd.DataFrame
    delete_session(session_id)       → None
"""

import sqlite3
import os
import pandas as pd
from datetime import datetime

DB_PATH = "data/sessions.db"


def _connect() -> sqlite3.Connection:
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Create the sessions table if it doesn't exist.
    If the table exists but is missing columns (stale schema), migrate it
    by adding any missing columns — never drops data.
    """
    expected_columns = {
        "uploaded_at":     "TEXT    NOT NULL DEFAULT ''",
        "filename":        "TEXT    NOT NULL DEFAULT ''",
        "total_frames":    "INTEGER NOT NULL DEFAULT 0",
        "detected_frames": "INTEGER NOT NULL DEFAULT 0",
        "detection_rate":  "REAL    NOT NULL DEFAULT 0.0",
        "bps":             "REAL    NOT NULL DEFAULT 0.0",
        "grade":           "TEXT    NOT NULL DEFAULT 'N/A'",
        "duration_sec":    "REAL    NOT NULL DEFAULT 0.0",
        "video_path":      "TEXT    DEFAULT ''",
        "forehand_pct":    "REAL    DEFAULT 0.0",
        "backhand_pct":    "REAL    DEFAULT 0.0",
        "top_strength":    "TEXT    DEFAULT NULL",
        "top_weakness":    "TEXT    DEFAULT NULL",
    }
    with _connect() as conn:
        # Create table if completely missing
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                uploaded_at      TEXT    NOT NULL DEFAULT '',
                filename         TEXT    NOT NULL DEFAULT '',
                total_frames     INTEGER NOT NULL DEFAULT 0,
                detected_frames  INTEGER NOT NULL DEFAULT 0,
                detection_rate   REAL    NOT NULL DEFAULT 0.0,
                bps              REAL    NOT NULL DEFAULT 0.0,
                grade            TEXT    NOT NULL DEFAULT 'N/A',
                duration_sec     REAL    NOT NULL DEFAULT 0.0,
                video_path       TEXT    DEFAULT '',
                forehand_pct     REAL    DEFAULT 0.0,
                backhand_pct     REAL    DEFAULT 0.0,
                top_strength     TEXT    DEFAULT NULL,
                top_weakness     TEXT    DEFAULT NULL
            )
        """)
        # Migrate: add any columns that are missing from an older schema
        existing = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
        for col, col_def in expected_columns.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {col_def}")
        conn.commit()


def save_session(filename: str, result: dict, analytics: dict) -> int:
    """
    Insert one row for a completed pipeline run.
    Returns the new row's id.

    result   — dict returned by run_full_pipeline()
    analytics — the analytics dict stored in upload_analytics session key
    """
    strengths  = analytics.get("top_strengths",  [])
    weaknesses = analytics.get("top_weaknesses", [])

    total   = int(result.get("total_frames", 0) or 0)
    detected = int(result.get("detected_frame_count", 0) or 0)

    row = {
        "uploaded_at":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "filename":        filename or "unknown",
        "total_frames":    total,
        "detected_frames": detected,
        "detection_rate":  round(detected / max(total, 1) * 100, 1),
        "bps":             round(float(analytics.get("bps", 0) or 0), 1),
        "grade":           str(analytics.get("session_grade", "N/A") or "N/A"),
        "duration_sec":    round(float(analytics.get("duration_seconds", 0) or 0), 1),
        "video_path":      str(result.get("annotated_video_path", "") or ""),
        "forehand_pct":    round(float(analytics.get("forehand_usage", 0) or 0), 1),
        "backhand_pct":    round(float(analytics.get("backhand_usage", 0) or 0), 1),
        "top_strength":    strengths[0]["metric"].replace("_", " ").title()  if strengths  else None,
        "top_weakness":    weaknesses[0]["metric"].replace("_", " ").title() if weaknesses else None,
    }

    with _connect() as conn:
        cursor = conn.execute("""
            INSERT INTO sessions (
                uploaded_at, filename, total_frames, detected_frames,
                detection_rate, bps, grade, duration_sec, video_path,
                forehand_pct, backhand_pct, top_strength, top_weakness
            ) VALUES (
                :uploaded_at, :filename, :total_frames, :detected_frames,
                :detection_rate, :bps, :grade, :duration_sec, :video_path,
                :forehand_pct, :backhand_pct, :top_strength, :top_weakness
            )
        """, row)
        conn.commit()
        return cursor.lastrowid


def get_session_history() -> pd.DataFrame:
    """Return all sessions newest-first as a DataFrame. Empty DataFrame if none."""
    with _connect() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM sessions ORDER BY id DESC",
            conn
        )
    return df


def delete_session(session_id: int) -> None:
    """Delete a single session row by id."""
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
