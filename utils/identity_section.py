"""
utils/identity_section.py
─────────────────────────
Owns the Player Identity Card:
    - build_identity_card(analytics)  → dict   (used by coach_report.py too)
    - render_identity_section()       → None   (Streamlit UI)

No imports from this module — build_identity_card is defined here, not
imported from anywhere, so there is no circular dependency.
"""

import streamlit as st
from utils.session_utils import get_active_analytics


# ---------------------------------------------------------------------------
# Archetype classification
# ---------------------------------------------------------------------------
_ARCHETYPES = [
    {
        "name": "Net Dominator",
        "tags": {"net_rusher", "aggressive", "front_court"},
        "description": "Plays aggressively close to the net, thriving on quick exchanges and tight angles.",
    },
    {
        "name": "Baseline Defender",
        "tags": {"baseline", "defensive", "back_court"},
        "description": "Stays deep, absorbs pressure, and redirects pace with patience and precision.",
    },
    {
        "name": "All-Court Athlete",
        "tags": {"all_court", "balanced", "mid_court"},
        "description": "Covers the full court efficiently, adapting style to each situation.",
    },
    {
        "name": "Power Smasher",
        "tags": {"power", "smash", "aggressive"},
        "description": "Relies on explosive overhead smashes to end rallies early.",
    },
    {
        "name": "Rally Controller",
        "tags": {"consistent", "defensive", "balanced"},
        "description": "Keeps the shuttle in play, waiting for opponents to make errors.",
    },
]

_DEFAULT_ARCHETYPE = {
    "name": "Developing Player",
    "description": "Building foundational skills across all areas of the game.",
}


def _classify_archetype(analytics: dict) -> tuple[str, str, list[str]]:
    """
    Returns (archetype_name, archetype_description, style_tags).
    Derives style tags from analytics fields, then picks the best-matching archetype.
    """
    tags: set[str] = set()

    # Court depth positioning
    zones = analytics.get("court_zone_coverage", {})
    depth_buckets = {"front": 0.0, "mid": 0.0, "back": 0.0}
    zone_depth_map = {
        "1": "front", "2": "front", "3": "front",
        "4": "mid",   "5": "mid",   "6": "mid",
        "7": "back",  "8": "back",  "9": "back",
    }
    for zone_id, pct in zones.items():
        bucket = zone_depth_map.get(str(zone_id))
        if bucket:
            depth_buckets[bucket] += pct

    dominant_depth = max(depth_buckets, key=depth_buckets.get) if any(depth_buckets.values()) else "mid"
    tags.add(f"{dominant_depth}_court")
    if dominant_depth == "front":
        tags.update({"net_rusher", "aggressive"})
    elif dominant_depth == "back":
        tags.update({"baseline", "defensive"})
    else:
        tags.update({"all_court", "balanced", "mid_court"})

    # Shot side balance
    fh = analytics.get("forehand_usage", 50.0)
    bh = analytics.get("backhand_usage", 50.0)
    imbalance = abs(fh - bh)
    if imbalance < 15:
        tags.add("balanced")
    elif fh > bh:
        tags.add("forehand_heavy")
    else:
        tags.add("backhand_heavy")

    # Strength hints
    for s in analytics.get("top_strengths", []):
        m = s.get("metric", "")
        if m in ("stability", "recovery_speed", "recovery"):
            tags.add("consistent")
        if m in ("agility", "avg_speed", "speed"):
            tags.add("power")

    # Match against archetypes by tag overlap
    best, best_overlap = _DEFAULT_ARCHETYPE, -1
    for arch in _ARCHETYPES:
        overlap = len(tags & arch["tags"])
        if overlap > best_overlap:
            best, best_overlap = arch, overlap

    style_tags = sorted(tags)
    return best["name"], best["description"], style_tags


# ---------------------------------------------------------------------------
# Dominant side
# ---------------------------------------------------------------------------
def _dominant_side(analytics: dict) -> dict:
    fh = analytics.get("forehand_usage", 50.0)
    bh = analytics.get("backhand_usage", 50.0)
    side = "Forehand" if fh >= bh else "Backhand"
    return {
        "side": side,
        "forehand_pct": fh,
        "backhand_pct": bh,
    }


# ---------------------------------------------------------------------------
# Court preference label
# ---------------------------------------------------------------------------
def _court_preference(analytics: dict) -> dict:
    zones = analytics.get("court_zone_coverage", {})
    depth_buckets = {"front": 0.0, "mid": 0.0, "back": 0.0}
    zone_depth_map = {
        "1": "front", "2": "front", "3": "front",
        "4": "mid",   "5": "mid",   "6": "mid",
        "7": "back",  "8": "back",  "9": "back",
    }
    for zone_id, pct in zones.items():
        bucket = zone_depth_map.get(str(zone_id))
        if bucket:
            depth_buckets[bucket] += pct

    dominant = max(depth_buckets, key=depth_buckets.get) if any(depth_buckets.values()) else "mid"
    labels = {"front": "Front Court", "mid": "Mid Court", "back": "Back Court"}
    return {
        "label": labels[dominant],
        "top_zone_pct": round(depth_buckets[dominant], 1),
    }


# ---------------------------------------------------------------------------
# Strongest / weakest single metric
# ---------------------------------------------------------------------------
def _best_metric(analytics: dict) -> dict:
    strengths = analytics.get("top_strengths", [])
    if strengths:
        return {"metric": strengths[0]["metric"], "score": strengths[0]["score"]}
    return {"metric": "unknown", "score": 0.0}


def _worst_metric(analytics: dict) -> dict:
    weaknesses = sorted(analytics.get("top_weaknesses", []), key=lambda w: w["score"])
    if weaknesses:
        return {"metric": weaknesses[0]["metric"], "score": weaknesses[0]["score"]}
    return {"metric": "unknown", "score": 0.0}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_identity_card(analytics: dict) -> dict:
    """
    Build a serialisable identity card dict from an analytics payload.
    Called by both render_identity_section() and coach_report.py.

    Returns:
    {
        "archetype":              str,
        "archetype_description":  str,
        "style_tags":             list[str],
        "dominant_side":          {"side", "forehand_pct", "backhand_pct"},
        "court_preference":       {"label", "top_zone_pct"},
        "strongest_area":         {"metric", "score"},
        "improvement_area":       {"metric", "score"},
    }
    """
    archetype, archetype_desc, style_tags = _classify_archetype(analytics)
    return {
        "archetype":             archetype,
        "archetype_description": archetype_desc,
        "style_tags":            style_tags,
        "dominant_side":         _dominant_side(analytics),
        "court_preference":      _court_preference(analytics),
        "strongest_area":        _best_metric(analytics),
        "improvement_area":      _worst_metric(analytics),
    }


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
def render_identity_section():
    analytics = get_active_analytics()
    if not analytics:
        st.warning("No data found. Please upload a session.")
        return

    card = build_identity_card(analytics)

    st.markdown("## 🧍 Player Identity Card")
    st.markdown(f"### {card['archetype']}")
    st.caption(card["archetype_description"])

    col1, col2, col3 = st.columns(3)
    dom = card["dominant_side"]
    col1.metric("Dominant Side", dom["side"])
    col2.metric(
        "Strongest Area",
        card["strongest_area"]["metric"].replace("_", " ").title(),
        f"{card['strongest_area']['score']:.1f}",
    )
    col3.metric(
        "Improvement Area",
        card["improvement_area"]["metric"].replace("_", " ").title(),
        f"{card['improvement_area']['score']:.1f}",
    )

    st.divider()

    cp = card["court_preference"]
    st.markdown(
        f"**Court Preference:** {cp['label']} — {cp['top_zone_pct']:.0f}% of time  \n"
        f"**Shot Balance:** {dom['forehand_pct']:.0f}% forehand / {dom['backhand_pct']:.0f}% backhand  \n"
        f"**Style Tags:** {', '.join(card['style_tags'])}"
    )
