import streamlit as st


def apply_custom_theme():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

    /* ── TOKENS ─────────────────────────────────────────────────────────── */
    :root {
        --bg:           #0A0C0B;   /* near-black with a whisper of green warmth */
        --surface:      #111510;   /* card surface */
        --surface-2:    #181D17;   /* elevated surface */
        --border:       #1F2820;   /* hairline borders */
        --border-hi:    #2A3829;   /* highlighted borders */

        --text:         #E8EDE9;   /* primary text — slightly warm white */
        --text-2:       #8A9E8D;   /* secondary / muted */
        --text-3:       #4D5E50;   /* very muted, labels */

        /* accent — court green. Used ONLY on active/positive/selected */
        --green:        #00E5A0;
        --green-dim:    #00B87E;
        --green-glow:   rgba(0, 229, 160, 0.12);

        /* signal palette */
        --good:         #00E5A0;
        --warn:         #F5A623;
        --poor:         #E8503A;
        --info:         #4A9EE8;

        /* warm amber — secondary accent for shot stats */
        --amber:        #F5A623;
    }

    /* ── BASE ────────────────────────────────────────────────────────────── */
    .stApp {
        background: var(--bg) !important;
        color: var(--text);
        font-family: 'DM Sans', sans-serif;
        font-size: 0.9rem;
    }

    /* ── SIDEBAR ─────────────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: #080A08 !important;
        border-right: 1px solid var(--border) !important;
    }

    [data-testid="stSidebar"] .stTitle,
    [data-testid="stSidebar"] h1 {
        font-family: 'Rajdhani', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1.3rem !important;
        letter-spacing: 0.08em !important;
        color: var(--green) !important;
        text-transform: uppercase;
    }

    /* ── HEADINGS ────────────────────────────────────────────────────────── */
    h1 {
        font-family: 'Rajdhani', sans-serif !important;
        font-weight: 700 !important;
        font-size: 2rem !important;
        letter-spacing: 0.04em !important;
        color: var(--text) !important;
        text-transform: uppercase;
        line-height: 1.1 !important;
    }

    h2 {
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.7rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.14em !important;
        color: var(--text-3) !important;
        border: none !important;
        background: none !important;
        padding: 0 0 10px 0 !important;
        margin-top: 2.5rem !important;
        margin-bottom: 1rem !important;
        border-bottom: 1px solid var(--border) !important;
    }

    h3 {
        font-family: 'Rajdhani', sans-serif !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        letter-spacing: 0.03em !important;
        color: var(--text) !important;
        text-transform: uppercase;
    }

    /* ── METRICS ─────────────────────────────────────────────────────────── */
    [data-testid="stMetric"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        padding: 18px 20px 14px 20px !important;
        position: relative;
        overflow: hidden;
        transition: border-color 0.18s ease, background 0.18s ease;
    }

    [data-testid="stMetric"]::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--green) 0%, transparent 100%);
        opacity: 0;
        transition: opacity 0.18s ease;
    }

    [data-testid="stMetric"]:hover {
        border-color: var(--border-hi) !important;
        background: var(--surface-2) !important;
    }

    [data-testid="stMetric"]:hover::before {
        opacity: 1;
    }

    [data-testid="stMetricValue"] {
        font-family: 'Rajdhani', sans-serif !important;
        font-weight: 700 !important;
        color: var(--text) !important;
        font-size: 2rem !important;
        font-variant-numeric: tabular-nums !important;
        line-height: 1.1 !important;
    }

    [data-testid="stMetricLabel"] {
        font-family: 'DM Sans', sans-serif !important;
        color: var(--text-3) !important;
        font-size: 0.66rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        font-weight: 500 !important;
    }

    [data-testid="stMetricDelta"] {
        font-family: 'DM Mono', monospace !important;
        font-size: 0.78rem !important;
    }

    /* ── ALERTS ──────────────────────────────────────────────────────────── */
    [data-testid="stAlert"] {
        border-radius: 5px !important;
        border: 1px solid var(--border) !important;
        background: var(--surface) !important;
        font-size: 0.88rem !important;
    }

    /* success */
    div[data-baseweb="notification"][kind="positive"],
    .stSuccess {
        border-left: 3px solid var(--good) !important;
        background: rgba(0, 229, 160, 0.05) !important;
    }

    /* warning */
    div[data-baseweb="notification"][kind="warning"],
    .stWarning {
        border-left: 3px solid var(--warn) !important;
        background: rgba(245, 166, 35, 0.05) !important;
    }

    /* error/critical */
    div[data-baseweb="notification"][kind="negative"],
    .stError {
        border-left: 3px solid var(--poor) !important;
        background: rgba(232, 80, 58, 0.05) !important;
    }

    /* info */
    div[data-baseweb="notification"][kind="info"],
    .stInfo {
        border-left: 3px solid var(--info) !important;
        background: rgba(74, 158, 232, 0.05) !important;
    }

    /* ── CHARTS ──────────────────────────────────────────────────────────── */
    [data-testid="stPlotlyChart"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        padding: 4px !important;
    }

    /* ── EXPANDER ────────────────────────────────────────────────────────── */
    [data-testid="stExpander"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        margin-bottom: 6px !important;
    }

    [data-testid="stExpander"]:hover {
        border-color: var(--border-hi) !important;
    }

    [data-testid="stExpanderToggleIcon"] {
        color: var(--text-3) !important;
    }

    details summary p {
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.88rem !important;
        color: var(--text-2) !important;
        letter-spacing: 0.01em !important;
    }

    /* ── PROGRESS BAR ────────────────────────────────────────────────────── */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, var(--green-dim), var(--green)) !important;
        border-radius: 2px !important;
    }

    .stProgress > div > div {
        background: var(--border) !important;
        border-radius: 2px !important;
        height: 4px !important;
    }

    /* ── BUTTONS ─────────────────────────────────────────────────────────── */
    .stButton > button {
        background: transparent !important;
        color: var(--green) !important;
        border: 1px solid var(--green) !important;
        border-radius: 4px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        padding: 0.45rem 1.2rem !important;
        transition: background 0.15s ease, color 0.15s ease !important;
    }

    .stButton > button:hover {
        background: var(--green-glow) !important;
        color: var(--green) !important;
    }

    .stButton > button[kind="primary"] {
        background: var(--green) !important;
        color: #0A0C0B !important;
        border-color: var(--green) !important;
    }

    .stButton > button[kind="primary"]:hover {
        background: var(--green-dim) !important;
        border-color: var(--green-dim) !important;
    }

    /* ── NAV MENU ────────────────────────────────────────────────────────── */
    .nav-link {
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 400 !important;
        font-size: 0.82rem !important;
        color: var(--text-2) !important;
        border-radius: 4px !important;
        letter-spacing: 0.02em !important;
    }

    .nav-link:hover {
        background: var(--surface-2) !important;
        color: var(--text) !important;
    }

    .nav-link-selected {
        background: var(--surface-2) !important;
        color: var(--green) !important;
        border-left: 2px solid var(--green) !important;
        font-weight: 600 !important;
    }

    .nav-link .icon-selected {
        color: var(--green) !important;
    }

    /* ── DIVIDER ─────────────────────────────────────────────────────────── */
    hr {
        border: none !important;
        border-top: 1px solid var(--border) !important;
        margin: 1.8rem 0 !important;
    }

    /* ── FILE UPLOADER ───────────────────────────────────────────────────── */
    [data-testid="stFileUploader"] {
        background: var(--surface) !important;
        border: 1px dashed var(--border-hi) !important;
        border-radius: 6px !important;
        padding: 1rem !important;
    }

    [data-testid="stFileUploader"]:hover {
        border-color: var(--green) !important;
        background: var(--green-glow) !important;
    }

    /* ── CAPTION / SMALL TEXT ────────────────────────────────────────────── */
    .stCaption, small, caption {
        font-family: 'DM Sans', sans-serif !important;
        color: var(--text-3) !important;
        font-size: 0.74rem !important;
        letter-spacing: 0.01em !important;
    }

    /* ── TEXT AREA (full report) ─────────────────────────────────────────── */
    .stTextArea textarea {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 5px !important;
        color: var(--text-2) !important;
        font-family: 'DM Mono', monospace !important;
        font-size: 0.8rem !important;
    }

    /* ── SPINNER ─────────────────────────────────────────────────────────── */
    .stSpinner > div {
        border-top-color: var(--green) !important;
    }

    /* ── SCROLLBAR ───────────────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 4px; height: 4px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 2px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--text-3); }

    /* ── SELECTBOX / INPUTS ──────────────────────────────────────────────── */
    [data-testid="stSelectbox"] > div > div,
    [data-testid="stTextInput"] > div > div {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 4px !important;
        color: var(--text) !important;
    }

    /* ── INFO / WARNING / SUCCESS / ERROR OVERRIDE for uniformity ────────── */
    .stSuccess > div { color: var(--text) !important; }
    .stWarning > div { color: var(--text) !important; }
    .stError   > div { color: var(--text) !important; }
    .stInfo    > div { color: var(--text) !important; }

    </style>
    """, unsafe_allow_html=True)


# ── Helper utilities ──────────────────────────────────────────────────────────

def signal_color(score: float, good: float = 70, mid: float = 40) -> str:
    """Return a CSS color string based on score performance tier."""
    if score >= good:
        return "#00E5A0"
    elif score >= mid:
        return "#F5A623"
    return "#E8503A"


def render_hero_stat(score, label: str, sublabel: str = ""):
    """
    Full-width hero BPS card — use once per page, not repeatedly.
    The green top-bar and mono number treatment is the signature visual.
    """
    color = signal_color(score)
    st.markdown(f"""
    <div style="
        background: #111510;
        border: 1px solid #1F2820;
        border-top: 3px solid {color};
        border-radius: 6px;
        padding: 28px 28px 22px 28px;
        position: relative;
    ">
        <div style="
            font-family: 'DM Sans', sans-serif;
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: #4D5E50;
            font-weight: 500;
            margin-bottom: 8px;
        ">{label}</div>
        <div style="
            font-family: 'Rajdhani', sans-serif;
            font-weight: 700;
            font-size: 4rem;
            color: {color};
            line-height: 1;
            font-variant-numeric: tabular-nums;
            letter-spacing: -0.01em;
        ">{score}</div>
        <div style="
            font-family: 'DM Sans', sans-serif;
            font-size: 0.8rem;
            color: #8A9E8D;
            margin-top: 6px;
            font-weight: 300;
        ">{sublabel}</div>
    </div>
    """, unsafe_allow_html=True)


def render_stat_pill(label: str, value: str, color: str = "#00E5A0"):
    """Inline pill for quick stat callouts inside text sections."""
    st.markdown(f"""
    <span style="
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(0,229,160,0.08);
        border: 1px solid rgba(0,229,160,0.2);
        border-radius: 3px;
        padding: 3px 10px;
        font-family: 'DM Mono', monospace;
        font-size: 0.78rem;
        color: {color};
        margin: 2px;
    ">
        <span style="color:#4D5E50; font-family:'DM Sans'; font-size:0.7rem;
                     text-transform:uppercase; letter-spacing:0.08em;">{label}</span>
        {value}
    </span>
    """, unsafe_allow_html=True)
