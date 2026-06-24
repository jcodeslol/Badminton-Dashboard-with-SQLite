import json
from utils.session_utils import get_active_analytics

# DO NOT import from utils.alerts here — this file IS utils.alerts.
# The previous version had: `from utils.alerts import generate_alerts`
# which caused a circular import crash at startup.

THRESHOLDS = {
    # Shot side dependency (%)
    "forehand_dependency_pct":     65.0,
    "backhand_dependency_pct":     65.0,
    "shot_balance_ideal_max_diff": 20.0,   # < 20pp gap = well balanced

    # Recovery (normalised units, 0-1 coord space)
    "poor_recovery_distance":      0.30,
    "good_recovery_distance":      0.15,

    # Court coverage (number of distinct zones used out of 9)
    "low_court_coverage_zones":    3,
    "good_court_coverage_zones":   6,

    # Stability index (0-1 ratio — already multiplied ×100 below)
    "excellent_stability":         80.0,
    "poor_stability":              40.0,

    # Path efficiency (0-1 ratio — already multiplied ×100 below)
    "low_path_efficiency":         45.0,
    "good_path_efficiency":        70.0,

    # BPS (0-100)
    "low_bps":                     50.0,
    "good_bps":                    70.0,
    "excellent_bps":               85.0,

    # Pose detection rate (0-1)
    "low_pose_detection":          0.80,
    "acceptable_pose_detection":   0.90,

    # Duration sanity (seconds)
    "short_session":               30.0,
}


def generate_alerts(analytics: dict) -> list:
    alerts = []

    forehand  = analytics.get("forehand_usage", 0)
    backhand  = analytics.get("backhand_usage", 0)
    recovery  = analytics.get("avg_recovery_distance", 0)
    zones     = analytics.get("court_zone_coverage", {})
    stability = analytics.get("avg_stability_index", 0) * 100   # → 0-100
    path_eff  = analytics.get("avg_path_efficiency", 0) * 100   # → 0-100
    bps       = analytics.get("bps", 0)
    pose_rate = analytics.get("pose_detection_rate", 1.0)
    duration  = analytics.get("duration_seconds", 0)
    grade     = analytics.get("session_grade", "N/A")

    # Pull component scores if available (produced by scoring_engine via run_pipeline fix)
    top_strengths  = analytics.get("top_strengths",  [])
    top_weaknesses = analytics.get("top_weaknesses", [])

    # ── Session duration ──────────────────────────────────────────────────
    if duration > 0 and duration < THRESHOLDS["short_session"]:
        alerts.append({"level": "info",
                        "message": f"Short session ({duration:.0f}s). Some metrics may not reflect full match patterns — longer clips improve accuracy."})

    # ── Pose detection quality ────────────────────────────────────────────
    if pose_rate < THRESHOLDS["low_pose_detection"]:
        alerts.append({"level": "critical",
                        "message": f"Pose detection only {pose_rate*100:.0f}% — more than 1 in 5 frames had no skeleton. Metrics for this session are unreliable. Improve lighting and ensure the full body is visible."})
    elif pose_rate < THRESHOLDS["acceptable_pose_detection"]:
        alerts.append({"level": "warning",
                        "message": f"Pose detection at {pose_rate*100:.0f}%. Some frames were missed — results are mostly reliable but treat edge metrics with caution."})

    # ── Overall BPS ───────────────────────────────────────────────────────
    if bps >= THRESHOLDS["excellent_bps"]:
        alerts.append({"level": "success",
                        "message": f"Outstanding BPS {bps:.1f} (Grade {grade}). Performance is well above target across all movement dimensions."})
    elif bps >= THRESHOLDS["good_bps"]:
        alerts.append({"level": "success",
                        "message": f"Strong BPS {bps:.1f} (Grade {grade}). Above-target performance — focus on closing the remaining gaps."})
    elif bps >= THRESHOLDS["low_bps"]:
        alerts.append({"level": "warning",
                        "message": f"Moderate BPS {bps:.1f} (Grade {grade}). Performance is adequate but below the 70+ target. See Training Priorities for focus areas."})
    else:
        alerts.append({"level": "critical",
                        "message": f"Low BPS {bps:.1f} (Grade {grade}). Multiple performance gaps detected — prioritise the weakest components before next match."})

    # ── Shot side balance ─────────────────────────────────────────────────
    shot_diff = abs(forehand - backhand)
    if forehand >= THRESHOLDS["forehand_dependency_pct"]:
        alerts.append({"level": "warning",
                        "message": f"Forehand dependency — {forehand:.1f}% forehand vs {backhand:.1f}% backhand ({shot_diff:.0f}pp gap). Opponents will target the backhand side."})
    elif backhand >= THRESHOLDS["backhand_dependency_pct"]:
        alerts.append({"level": "warning",
                        "message": f"Backhand dependency — {backhand:.1f}% backhand vs {forehand:.1f}% forehand ({shot_diff:.0f}pp gap). Opponents will target the forehand side."})
    elif shot_diff <= THRESHOLDS["shot_balance_ideal_max_diff"]:
        alerts.append({"level": "success",
                        "message": f"Well-balanced shot usage — {forehand:.1f}% forehand / {backhand:.1f}% backhand. Hard to exploit from either side."})

    # ── Recovery position ─────────────────────────────────────────────────
    if recovery > THRESHOLDS["poor_recovery_distance"]:
        alerts.append({"level": "critical",
                        "message": f"Poor court recovery — avg distance from base {recovery:.2f} (target <{THRESHOLDS['poor_recovery_distance']}). Player is leaving large areas of court exposed after shots. Drill split-step and return-to-base timing."})
    elif recovery <= THRESHOLDS["good_recovery_distance"]:
        alerts.append({"level": "success",
                        "message": f"Excellent recovery discipline — avg base distance {recovery:.2f} (target <{THRESHOLDS['poor_recovery_distance']}). Court is well-covered after each shot."})
    else:
        alerts.append({"level": "warning",
                        "message": f"Recovery distance {recovery:.2f} is manageable but above the ideal {THRESHOLDS['good_recovery_distance']} target. Focus on snappier returns to base."})

    # ── Court coverage ────────────────────────────────────────────────────
    zones_used = len([z for z, pct in zones.items() if pct > 0])
    if zones_used <= THRESHOLDS["low_court_coverage_zones"]:
        alerts.append({"level": "warning",
                        "message": f"Restricted court coverage — only {zones_used}/9 zones used. Movement pattern is predictable and easy to exploit with wide shots."})
    elif zones_used >= THRESHOLDS["good_court_coverage_zones"]:
        alerts.append({"level": "success",
                        "message": f"Wide court coverage — {zones_used}/9 zones reached. Player is moving well across the full court."})

    # ── Stability ─────────────────────────────────────────────────────────
    if stability >= THRESHOLDS["excellent_stability"]:
        alerts.append({"level": "success",
                        "message": f"Excellent balance and stability ({stability:.1f}/100). Strong body control throughout the session."})
    elif stability < THRESHOLDS["poor_stability"]:
        alerts.append({"level": "warning",
                        "message": f"Low stability index ({stability:.1f}/100). Balance is breaking down during movement — core stability and footwork drills recommended."})

    # ── Path efficiency ───────────────────────────────────────────────────
    if path_eff >= THRESHOLDS["good_path_efficiency"]:
        alerts.append({"level": "success",
                        "message": f"Efficient court movement ({path_eff:.1f}/100). Player is taking direct routes — minimising wasted energy."})
    elif path_eff < THRESHOLDS["low_path_efficiency"]:
        alerts.append({"level": "warning",
                        "message": f"Inefficient movement paths ({path_eff:.1f}/100). Player is covering more ground than necessary. Cone-based directional drills can sharpen court routes."})

    # ── Weakest component callout ─────────────────────────────────────────
    if top_weaknesses:
        worst = top_weaknesses[0]
        metric_label = worst["metric"].replace("_", " ").title()
        score = worst["score"]
        if score < 40:
            alerts.append({"level": "critical",
                            "message": f"Critical weakness: {metric_label} scored {score:.1f}/100 — the single biggest drag on overall BPS. This must be the first focus in training."})
        elif score < 55:
            alerts.append({"level": "warning",
                            "message": f"Notable weakness: {metric_label} scored {score:.1f}/100. Targeted drills here would have the biggest BPS impact."})

    # ── Top strength callout ──────────────────────────────────────────────
    if top_strengths:
        best = top_strengths[0]
        metric_label = best["metric"].replace("_", " ").title()
        score = best["score"]
        if score >= 75:
            alerts.append({"level": "success",
                            "message": f"Standout strength: {metric_label} at {score:.1f}/100. Build game patterns around this advantage."})

    # ── Fallback ──────────────────────────────────────────────────────────
    if not alerts:
        alerts.append({"level": "success",
                        "message": "No issues detected. Solid, balanced performance across all tracked metrics."})

    return alerts


def render_alerts_section(*args, **kwargs):
    import streamlit as st

    analytics = get_active_analytics()

    st.markdown("## 🚨 Coach Alert Box")
    alerts = generate_alerts(analytics)

    critical = [a for a in alerts if a["level"] == "critical"]
    warning  = [a for a in alerts if a["level"] == "warning"]
    success  = [a for a in alerts if a["level"] == "success"]
    info     = [a for a in alerts if a["level"] == "info"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 Critical", len(critical))
    c2.metric("🟠 Warnings", len(warning))
    c3.metric("🟢 Positive", len(success))
    c4.metric("🔵 Info",     len(info))

    st.divider()

    if critical:
        st.markdown("#### Critical Issues")
        for a in critical:
            st.error(a["message"], icon="🔴")

    if warning:
        st.markdown("#### Warnings")
        for a in warning:
            st.warning(a["message"], icon="🟠")

    if success:
        st.markdown("#### Positives")
        for a in success:
            st.success(a["message"], icon="🟢")

    if info:
        st.markdown("#### Info")
        for a in info:
            st.info(a["message"], icon="🔵")
