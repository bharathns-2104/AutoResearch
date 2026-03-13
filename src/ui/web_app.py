# src/ui/web_app.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time
import threading
import streamlit as st

from src.orchestration.workflow_controller import WorkflowController
from src.orchestration.state_manager import StateManager, SystemState
from src.agents.dialog.dialog_engine import DialogEngine


# ─────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AutoResearch — Business Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ─────────────────────────────────────────────────────────────────
# GLOBAL CSS  — Clean, Professional, Minimalist
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Design Tokens ── */
:root {
  --bg:         #0d0d0f;
  --surface:    #161618;
  --surface2:   #1c1c1f;
  --border:     #2a2a2e;
  --border-lg:  #333338;
  --text:       #e8e8ed;
  --text-dim:   #8e8e9a;
  --text-xdim:  #4a4a54;
  --accent:     #6366f1;
  --accent-dim: rgba(99,102,241,.12);
  --green:      #22c55e;
  --green-dim:  rgba(34,197,94,.12);
  --amber:      #f59e0b;
  --red:        #ef4444;
  --radius-sm:  8px;
  --radius-md:  12px;
  --radius-lg:  16px;
}

/* ── Base ── */
html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
  font-family: 'Inter', -apple-system, sans-serif;
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}
[data-testid="stAppViewContainer"] > .main { background: var(--bg); }
[data-testid="block-container"] {
  padding: 3rem 2rem 5rem;
  max-width: 820px;
  margin: 0 auto;
}
* { box-sizing: border-box; }

/* ── Header ── */
.ar-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 2.5rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border);
}
.ar-logo {
  width: 32px; height: 32px;
  background: var(--accent);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 15px; font-weight: 700; color: #fff;
  letter-spacing: -.02em;
  flex-shrink: 0;
}
.ar-wordmark {
  font-size: 1rem; font-weight: 600; color: var(--text);
  letter-spacing: -.02em;
}
.ar-badge {
  margin-left: 2px;
  font-family: 'JetBrains Mono', monospace;
  font-size: .6rem;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--accent-dim);
  color: var(--accent);
  letter-spacing: .04em;
}

/* ── Stepper ── */
.stepper {
  display: flex;
  align-items: center;
  gap: 0;
  margin-bottom: 2rem;
}
.stp-item {
  display: flex;
  align-items: center;
  flex: 1;
}
.stp-dot {
  width: 28px; height: 28px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: .65rem; font-weight: 600; flex-shrink: 0;
  font-family: 'JetBrains Mono', monospace;
  transition: all .3s;
}
.stp-dot.done   { background: var(--green);   color: var(--bg); }
.stp-dot.active { background: var(--accent);  color: #fff; box-shadow: 0 0 0 3px var(--accent-dim); }
.stp-dot.idle   { background: var(--surface2); color: var(--text-xdim); border: 1.5px solid var(--border); }
.stp-label {
  font-size: .65rem; font-weight: 500;
  margin-left: 6px; white-space: nowrap;
  transition: color .3s;
}
.stp-label.done   { color: var(--green); }
.stp-label.active { color: var(--text); }
.stp-label.idle   { color: var(--text-xdim); }
.stp-line {
  flex: 1; height: 1px;
  background: var(--border);
  margin: 0 8px;
  min-width: 12px;
}
.stp-line.done { background: var(--green); }

/* ── Chips ── */
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 1.5rem; }
.chip {
  font-family: 'JetBrains Mono', monospace;
  font-size: .62rem;
  padding: 3px 10px;
  border-radius: 4px;
  line-height: 1.6;
}
.chip.filled { background: var(--green-dim); color: var(--green); border: 1px solid rgba(34,197,94,.2); }
.chip.empty  { background: var(--surface2);  color: var(--text-xdim); border: 1px solid var(--border); }

/* ── Question Card ── */
.q-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  margin-bottom: 1.25rem;
}
.q-step {
  font-family: 'JetBrains Mono', monospace;
  font-size: .58rem;
  color: var(--accent);
  letter-spacing: .1em;
  margin-bottom: .5rem;
}
.q-title { font-size: 1.1rem; font-weight: 600; color: var(--text); margin-bottom: .3rem; line-height: 1.4; }
.q-hint  { font-size: .82rem; color: var(--text-dim); line-height: 1.55; }

/* ── Chat History ── */
.chat { margin-bottom: 1.25rem; }
.chat-msg {
  display: flex;
  gap: 10px;
  margin-bottom: .75rem;
  align-items: flex-start;
}
.chat-msg.user-msg { flex-direction: row-reverse; }
.chat-avatar {
  width: 26px; height: 26px;
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: .58rem; font-weight: 600;
  flex-shrink: 0; margin-top: 1px;
}
.chat-avatar.bot  { background: var(--accent); color: #fff; }
.chat-avatar.user { background: var(--surface2); color: var(--text-dim); border: 1px solid var(--border-lg); }
.chat-bubble {
  max-width: 80%;
  padding: 9px 13px;
  border-radius: 10px;
  font-size: .85rem;
  line-height: 1.6;
}
.chat-bubble.bot  {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  border-bottom-left-radius: 3px;
}
.chat-bubble.user {
  background: var(--accent-dim);
  border: 1px solid rgba(99,102,241,.2);
  color: var(--text);
  border-bottom-right-radius: 3px;
}

/* ── Pipeline ── */
.pipe-container {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin-bottom: 1rem;
}
.pipe-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--border);
  font-size: .85rem;
  transition: background .2s;
}
.pipe-row:last-child { border-bottom: none; }
.pipe-row.done   { color: var(--green); }
.pipe-row.active { color: var(--text); background: rgba(99,102,241,.05); }
.pipe-row.idle   { color: var(--text-xdim); }
.pipe-icon { width: 18px; font-size: .9rem; text-align: center; }
.pipe-name { flex: 1; font-weight: 500; }
.pipe-status {
  font-family: 'JetBrains Mono', monospace;
  font-size: .6rem;
  letter-spacing: .05em;
}
.pipe-track {
  width: 72px; height: 3px;
  background: var(--border);
  border-radius: 2px; overflow: hidden;
}
.pipe-fill { height: 100%; border-radius: 2px; }

/* ── Result Cards ── */
.res-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.25rem 1.5rem;
  margin-bottom: .875rem;
}
.res-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: .58rem;
  letter-spacing: .1em;
  color: var(--text-dim);
  text-transform: uppercase;
  margin-bottom: .75rem;
}
.score-big {
  font-size: 2.5rem;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -.03em;
}
.rating-pill {
  display: inline-block;
  font-size: .7rem;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  letter-spacing: .04em;
}
.pill-strong   { background: var(--green-dim); color: var(--green); border: 1px solid rgba(34,197,94,.2); }
.pill-moderate { background: rgba(245,158,11,.1); color: var(--amber); border: 1px solid rgba(245,158,11,.2); }
.pill-weak     { background: rgba(239,68,68,.1);  color: var(--red);   border: 1px solid rgba(239,68,68,.2); }
.score-bar { height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; margin-top: .75rem; }
.score-fill {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--accent), var(--green));
}
.sub-score-val {
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -.02em;
  line-height: 1.1;
}

/* ── Buttons ── */
button[kind="primary"] {
  background: var(--accent) !important;
  border: none !important;
  color: #fff !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 600 !important;
  font-size: .85rem !important;
  border-radius: var(--radius-sm) !important;
  padding: .55rem 1.5rem !important;
  letter-spacing: -.01em !important;
  transition: opacity .15s, transform .15s !important;
  box-shadow: none !important;
}
button[kind="primary"]:hover { opacity: .88 !important; transform: translateY(-1px) !important; }

button[kind="secondary"], button[kind="tertiary"] {
  background: var(--surface2) !important;
  border: 1px solid var(--border-lg) !important;
  color: var(--text-dim) !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 500 !important;
  font-size: .82rem !important;
  border-radius: var(--radius-sm) !important;
  padding: .5rem 1.2rem !important;
}
button[kind="secondary"]:hover, button[kind="tertiary"]:hover {
  border-color: var(--accent) !important;
  color: var(--accent) !important;
}

/* ── Inputs ── */
.stTextInput input, .stNumberInput input {
  background: var(--surface2) !important;
  border: 1px solid var(--border-lg) !important;
  color: var(--text) !important;
  border-radius: var(--radius-sm) !important;
  font-family: 'Inter', sans-serif !important;
  font-size: .88rem !important;
  padding: 10px 12px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px var(--accent-dim) !important;
  outline: none !important;
}
.stTextInput input::placeholder, .stNumberInput input::placeholder {
  color: var(--text-xdim) !important;
}

/* ── Slider ── */
div[data-testid="stSlider"] > div > div > div {
  background: linear-gradient(90deg, var(--accent), var(--green)) !important;
}

/* ── Download Button ── */
.stDownloadButton > button {
  background: var(--surface2) !important;
  border: 1px solid var(--border-lg) !important;
  color: var(--text) !important;
  border-radius: var(--radius-sm) !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 500 !important;
  font-size: .82rem !important;
}
.stDownloadButton > button:hover {
  border-color: var(--accent) !important;
  color: var(--accent) !important;
}

/* ── Warning / Info ── */
div[data-testid="stAlert"] {
  background: var(--surface2) !important;
  border: 1px solid var(--border-lg) !important;
  border-radius: var(--radius-sm) !important;
  color: var(--text-dim) !important;
}

/* ── Section Label ── */
.section-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: .6rem;
  letter-spacing: .1em;
  color: var(--text-xdim);
  text-transform: uppercase;
  margin-bottom: .5rem;
}

/* ── Expander ── */
.stExpander {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  background: var(--surface) !important;
}

/* ── Hide default Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────
STEP_DEFS = [
    ("01", "Idea"), ("02", "Industry"), ("03", "Budget"),
    ("04", "Timeline"), ("05", "Market"), ("06", "Team"),
]
SLOT_ORDER  = ["business_idea", "industry", "budget", "timeline_months", "target_market", "team_size"]
SLOT_LABELS = {
    "business_idea": "Idea", "industry": "Industry", "budget": "Budget",
    "timeline_months": "Timeline", "target_market": "Market", "team_size": "Team"
}
INDUSTRIES = [
    ("SaaS"), ("FinTech"), ("HealthTech"), ("EdTech"),
    ("E-commerce"), ("Logistics"), ("Real Estate"), ("Manufacturing"),
    ("AgriTech"), ("Media & Ent."), ("Travel"), ("Legal Tech"),
    ("HR Tech"), ("Automotive"),
]
PIPELINE_STAGES = [
    ("🔍", "Search", 20), ("🌐", "Scraping", 42), ("⚗️", "Extraction", 64),
    ("🧠", "Analysis", 80), ("🔗", "Consolidate", 92), ("📄", "Report", 100),
]
STATE_PROG = {
    SystemState.INPUT_RECEIVED: 10, SystemState.SEARCHING: 25,
    SystemState.SCRAPING: 45,       SystemState.EXTRACTING: 65,
    SystemState.ANALYZING: 80,      SystemState.CONSOLIDATING: 90,
    SystemState.GENERATING_REPORT: 95, SystemState.COMPLETED: 100,
}


# ─────────────────────────────────────────────────────────────────
# RENDER FUNCTIONS
# ─────────────────────────────────────────────────────────────────

def render_header():
    st.markdown("""
    <div class="ar-header">
      <div class="ar-logo">AR</div>
      <span class="ar-wordmark">AutoResearch</span>
      <span class="ar-badge">BETA</span>
    </div>
    """, unsafe_allow_html=True)


def render_stepper(filled):
    n = len(filled)
    html = '<div class="stepper">'
    for i, (num, lbl) in enumerate(STEP_DEFS):
        if i < n:
            cls = "done"
            label_html = "✓"
        elif i == n:
            cls = "active"
            label_html = num
        else:
            cls = "idle"
            label_html = num

        is_last = (i == len(STEP_DEFS) - 1)
        line_cls = "done" if i < n else ""
        html += f'<div class="stp-item"><div class="stp-dot {cls}">{label_html}</div><span class="stp-label {cls}">{lbl}</span></div>'
        if not is_last:
            html += f'<div class="stp-line {line_cls}"></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_chips(filled):
    html = '<div class="chips">'
    for s in SLOT_ORDER:
        lbl = SLOT_LABELS[s]
        if s in filled:
            html += f'<span class="chip filled">✓ {lbl}</span>'
        else:
            html += f'<span class="chip empty">{lbl}</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_history(messages):
    html = '<div class="chat">'
    for m in messages:
        is_bot = m["role"] == "assistant"
        msg_cls = "" if is_bot else "user-msg"
        av_cls  = "bot" if is_bot else "user"
        av_lbl  = "AR" if is_bot else "You"
        bub_cls = "bot" if is_bot else "user"
        html += f"""<div class="chat-msg {msg_cls}">
          <div class="chat-avatar {av_cls}">{av_lbl}</div>
          <div class="chat-bubble {bub_cls}">{m['content']}</div>
        </div>"""
    html += "</div>"
    if messages:
        st.markdown(html, unsafe_allow_html=True)


def render_q_card(step_n, title, hint=""):
    hint_html = f"<div class='q-hint'>{hint}</div>" if hint else ""
    st.markdown(f"""
    <div class="q-card">
      <div class="q-step">STEP {step_n} OF 6</div>
      <div class="q-title">{title}</div>
      {hint_html}
    </div>""", unsafe_allow_html=True)


def render_pipeline(progress):
    html = '<div class="pipe-container">'
    for ico, lbl, thresh in PIPELINE_STAGES:
        span = 22
        if progress >= thresh:
            cls, fw, fc, status = "done", "100%", "var(--green)", "Done"
        elif progress >= thresh - span:
            pct = int(((progress - (thresh - span)) / span) * 100)
            cls, fw, fc, status = "active", f"{pct}%", "var(--accent)", "Running"
        else:
            cls, fw, fc, status = "idle", "0%", "var(--border)", "Queued"
        html += f"""<div class="pipe-row {cls}">
          <span class="pipe-icon">{ico}</span>
          <span class="pipe-name">{lbl}</span>
          <span class="pipe-status">{status}</span>
          <div class="pipe-track"><div class="pipe-fill" style="width:{fw};background:{fc}"></div></div>
        </div>"""
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_results(consolidated):
    score  = consolidated.get("overall_viability_score", 0)
    rating = consolidated.get("overall_rating", "—")
    summary = consolidated.get("executive_summary", "")
    color = "var(--green)" if score >= 0.7 else ("var(--amber)" if score >= 0.5 else "var(--red)")
    pill_cls = {"Strong": "pill-strong", "Moderate": "pill-moderate", "Weak": "pill-weak"}.get(rating, "pill-moderate")

    st.markdown(f"""
    <div class="res-card">
      <div class="res-label">Overall Viability</div>
      <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:8px">
        <span class="score-big" style="color:{color}">{score:.0%}</span>
        <span class="rating-pill {pill_cls}">{rating}</span>
      </div>
      <div class="score-bar"><div class="score-fill" style="width:{score*100:.0f}%"></div></div>
    </div>""", unsafe_allow_html=True)

    if summary:
        st.markdown(f"""
        <div class="res-card">
          <div class="res-label">Executive Summary</div>
          <p style="font-size:.88rem;line-height:1.7;margin:0;color:var(--text)">{summary}</p>
        </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    for col, lbl, val, clr in [
        (c1, "Financial",   consolidated.get("financial_score",   0), "var(--accent)"),
        (c2, "Market",      consolidated.get("market_score",      0), "var(--green)"),
        (c3, "Competitive", consolidated.get("competitive_score", 0), "var(--amber)"),
    ]:
        with col:
            st.markdown(f"""
            <div class="res-card">
              <div class="res-label">{lbl}</div>
              <div class="sub-score-val" style="color:{clr}">{val:.0%}</div>
              <div class="score-bar"><div class="score-fill" style="width:{val*100:.0f}%;background:{clr}"></div></div>
            </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# INTERACTIVE SLOT WIDGETS
# ─────────────────────────────────────────────────────────────────

def widget_business_idea():
    render_q_card(1, "What's your business idea?",
                  "A one-sentence description — the more specific, the better.")

    st.markdown("<div class='section-label'>Quick start — click to pre-fill</div>", unsafe_allow_html=True)
    suggestions = [
        "AI-powered scheduling SaaS for clinics",
        "EV charging network for apartment buildings",
        "B2B logistics marketplace for last-mile delivery",
        "EdTech platform for online coding bootcamps",
    ]
    c1, c2 = st.columns(2)
    for i, (sug, col) in enumerate(zip(suggestions, [c1, c2, c1, c2])):
        with col:
            if st.button(sug, key=f"sug_{i}", use_container_width=True):
                st.session_state["_idea_prefill"] = sug
                st.rerun()

    prefill = st.session_state.pop("_idea_prefill", "") or ""
    val = st.text_input("idea_text", value=prefill,
                        placeholder="e.g. On-demand tutoring for STEM students…",
                        key="idea_input", label_visibility="collapsed")

    if st.button("Continue →", key="go_idea", type="primary"):
        if val.strip():
            return val.strip()
        st.warning("Please describe your idea before continuing.")
    return None


def widget_industry():
    render_q_card(2, "Which industry does it belong to?",
                  "Pick the closest match, or type a custom industry below.")

    selected = st.session_state.get("_ind_sel", "")

    rows_of_4 = [INDUSTRIES[i:i+4] for i in range(0, len(INDUSTRIES), 4)]
    for row in rows_of_4:
        cols = st.columns(4)
        for col, name in zip(cols, row):
            with col:
                is_sel = selected == name
                border = "var(--accent)" if is_sel else "var(--border-lg)"
                bg     = "var(--accent-dim)" if is_sel else "var(--surface2)"
                txt    = "var(--accent)" if is_sel else "var(--text-dim)"
                st.markdown(f"""
                <div style="background:{bg};border:1px solid {border};border-radius:8px;
                  padding:10px 6px;text-align:center;pointer-events:none;margin-bottom:-46px">
                  <div style="font-size:.82rem;font-weight:500;color:{txt}">{name}</div>
                </div>""", unsafe_allow_html=True)
                if st.button("‎", key=f"ind_{name}", use_container_width=True, help=f"Select {name}"):
                    st.session_state["_ind_sel"] = name
                    st.rerun()

    st.markdown("<div class='section-label' style='margin-top:14px'>Or type a custom industry</div>", unsafe_allow_html=True)
    custom = st.text_input("custom_ind", placeholder="e.g. PropTech, CleanEnergy, BioTech…",
                           key="ind_custom_input", label_visibility="collapsed")

    final = custom.strip() if custom.strip() else selected
    if selected and not custom.strip():
        st.markdown(f"<p style='font-family:JetBrains Mono,monospace;font-size:.72rem;color:var(--accent);margin:4px 0'>Selected: {selected}</p>", unsafe_allow_html=True)

    if st.button("Continue →", key="go_ind", type="primary"):
        if final:
            return final
        st.warning("Please select or type an industry.")
    return None


def widget_budget():
    render_q_card(3, "What's your available budget?",
                  "Used for financial runway and viability scoring.")

    st.markdown("<div class='section-label'>Common ranges</div>", unsafe_allow_html=True)
    presets = [("Bootstrap", "$10k–$50k", 25_000), ("Seed", "$100k–$500k", 250_000),
               ("Series A", "$1M–$5M", 2_000_000), ("Scale-up", "$5M+", 7_500_000)]
    pc = st.columns(4)
    for col, (lbl, rng, amt) in zip(pc, presets):
        with col:
            st.markdown(f"""
            <div style="background:var(--surface2);border:1px solid var(--border-lg);border-radius:8px;
              padding:10px 8px;text-align:center;margin-bottom:-42px;pointer-events:none">
              <div style="font-weight:600;font-size:.82rem;color:var(--text)">{lbl}</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:.62rem;color:var(--text-dim);margin-top:2px">{rng}</div>
            </div>""", unsafe_allow_html=True)
            if st.button("‎", key=f"bp_{lbl}", use_container_width=True, help=f"Set budget to {rng}"):
                st.session_state["_budget_k"] = amt // 1000
                st.rerun()

    default_k = st.session_state.get("_budget_k", 100)
    budget_k = st.slider("Budget", min_value=1, max_value=10_000,
                         value=default_k, step=5, format="$%dk",
                         key="budget_slider", label_visibility="collapsed")
    st.session_state["_budget_k"] = budget_k
    budget_usd = budget_k * 1000

    st.markdown(f"""
    <div style="font-size:1.8rem;font-weight:700;color:var(--text);letter-spacing:-.03em;margin:8px 0 4px">${budget_usd:,}
    </div>""", unsafe_allow_html=True)

    if st.button("Continue →", key="go_budget", type="primary"):
        return budget_usd
    return None


def widget_timeline():
    render_q_card(4, "What's your target timeline?",
                  "How many months to launch or hit your key milestone?")

    quick = [3, 6, 9, 12, 18, 24, 36, 48]
    st.markdown("<div class='section-label'>Quick pick</div>", unsafe_allow_html=True)
    qcols = st.columns(len(quick))
    for col, mo in zip(qcols, quick):
        with col:
            yr = mo // 12; rm = mo % 12
            lbl = (f"{yr}yr" + (f" {rm}mo" if rm else "")) if mo >= 12 else f"{mo}mo"
            if st.button(lbl, key=f"tl_{mo}", use_container_width=True):
                st.session_state["_tl_val"] = mo
                st.rerun()

    selected_tl = st.session_state.get("_tl_val", 12)
    st.markdown("<div class='section-label' style='margin-top:14px'>Fine-tune (months)</div>", unsafe_allow_html=True)
    final_tl = st.number_input("tl_num", min_value=1, max_value=60, value=selected_tl,
                               step=1, key="tl_input", label_visibility="collapsed")

    st.markdown(f"""
    <div style="font-size:1.8rem;font-weight:700;color:var(--text);letter-spacing:-.03em;margin:8px 0 4px">{int(final_tl)} months
    </div>""", unsafe_allow_html=True)

    if st.button("Continue →", key="go_tl", type="primary"):
        if 1 <= int(final_tl) <= 60:
            return int(final_tl)
        st.warning("Timeline must be between 1 and 60 months.")
    return None


def widget_target_market():
    render_q_card(5, "Who is your target market?",
                  "Geography or customer segment you're focusing on.")

    regions = [
        ("🇺🇸", "United States"), ("🇮🇳", "India"), ("🇬🇧", "United Kingdom"),
        ("🇪🇺", "Europe"), ("🇸🇬", "Southeast Asia"), ("🌍", "Global"),
        ("🏢", "US Small Businesses"), ("🏥", "US Healthcare"), ("🎓", "University Students"),
    ]
    st.markdown("<div class='section-label'>Common markets</div>", unsafe_allow_html=True)

    rows = [regions[i:i+3] for i in range(0, len(regions), 3)]
    for row in rows:
        rcols = st.columns(3)
        for col, (flag, name) in zip(rcols, row):
            with col:
                if st.button(f"{flag} {name}", key=f"mkt_{name}", use_container_width=True):
                    st.session_state["_mkt_val"] = name
                    st.rerun()

    prefill = st.session_state.get("_mkt_val", "")
    if prefill:
        st.markdown(f"<p style='font-family:JetBrains Mono,monospace;font-size:.72rem;color:var(--accent);margin:8px 0 4px'>Selected: {prefill}</p>", unsafe_allow_html=True)

    st.markdown("<div class='section-label' style='margin-top:10px'>Or describe it</div>", unsafe_allow_html=True)
    custom = st.text_input("mkt_custom", value=prefill,
                           placeholder="e.g. Mid-market SaaS companies in North America",
                           key="mkt_input", label_visibility="collapsed")

    final = custom.strip() if custom.strip() else prefill

    if st.button("Continue →", key="go_mkt", type="primary"):
        if final:
            return final
        st.warning("Please specify a target market.")
    return None


def widget_team_size():
    render_q_card(6, "How large is your team?",
                  "Optional — press Skip if you'd prefer not to share.")

    personas = [
        (1, "Solo Founder"), (2, "Co-founders"), (3, "Small trio"),
        (5, "Early team"), (10, "Squad"), (20, "Startup"), (50, "Scale-up")
    ]
    team_val = st.slider("team_slider", min_value=1, max_value=50, value=3, step=1,
                         key="team_slider_w", label_visibility="collapsed")

    label = next((lbl for size, lbl in reversed(personas) if team_val >= size), "Solo Founder")
    st.markdown(f"""
    <div style="font-size:1.8rem;font-weight:700;color:var(--text);letter-spacing:-.03em;margin:8px 0 4px">
      {team_val} <span style="font-size:.95rem;color:var(--text-dim);font-weight:400">{label}</span>
    </div>""", unsafe_allow_html=True)

    col1, col2, _ = st.columns([1, 1, 4])
    with col1:
        if st.button("Continue →", key="go_team", type="primary"):
            return team_val
    with col2:
        if st.button("Skip", key="skip_team", type="secondary"):
            return 1
    return None


SLOT_WIDGETS = {
    "business_idea":   widget_business_idea,
    "industry":        widget_industry,
    "budget":          widget_budget,
    "timeline_months": widget_timeline,
    "target_market":   widget_target_market,
    "team_size":       widget_team_size,
}


# ─────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────
def _init():
    if "dialog_engine" not in st.session_state:
        st.session_state.dialog_engine = DialogEngine()
    if "history" not in st.session_state:
        st.session_state.history = [{
            "role": "assistant",
            "content": st.session_state.dialog_engine.get_opening_message()
        }]
    for k, v in [("filled_slots", []), ("current_slot", "business_idea"),
                 ("analysis_started", False), ("workflow_thread", None), ("controller", None)]:
        if k not in st.session_state:
            st.session_state[k] = v

_init()


# ─────────────────────────────────────────────────────────────────
# SUBMIT SLOT → dialog engine
# ─────────────────────────────────────────────────────────────────
def submit_slot(slot, value):
    text = (f"${value:,}" if slot == "budget"
            else f"{value} months" if slot == "timeline_months"
            else str(value))

    st.session_state.history.append({"role": "user", "content": text})
    result = st.session_state.dialog_engine.process_message(text)
    st.session_state.history.append({"role": "assistant", "content": result["response"]})

    prog = st.session_state.dialog_engine.get_progress()
    st.session_state.filled_slots = prog.get("filled", [])
    remaining = prog.get("remaining_required", [])
    st.session_state.current_slot = remaining[0] if remaining else ""

    for k in ["_idea_prefill", "_ind_sel", "_budget_k", "_tl_val", "_mkt_val"]:
        st.session_state.pop(k, None)

    if result["status"] == "complete":
        _launch_workflow(result["data"])

    st.rerun()


def _launch_workflow(structured_input):
    StateManager.reset()
    ctrl = WorkflowController()
    st.session_state.controller = ctrl
    ctrl.state_manager.add_data("test_input", structured_input)
    ctrl.state_manager.update_state(SystemState.INITIALIZED)

    t = threading.Thread(target=ctrl.run, daemon=True)
    t.start()
    st.session_state.workflow_thread = t
    st.session_state.analysis_started = True


# ─────────────────────────────────────────────────────────────────
# MAIN RENDER
# ─────────────────────────────────────────────────────────────────
render_header()

if not st.session_state.analysis_started:
    # ── INTAKE PHASE ──────────────────────────────────────────────
    render_stepper(st.session_state.filled_slots)
    render_chips(st.session_state.filled_slots)

    hist = st.session_state.history
    if len(hist) > 4:
        with st.expander(f"Earlier conversation ({len(hist) - 2} messages)", expanded=False):
            render_history(hist[:-2])
        render_history(hist[-2:])
    else:
        render_history(hist)

    cur = st.session_state.current_slot
    if cur and cur in SLOT_WIDGETS:
        val = SLOT_WIDGETS[cur]()
        if val is not None:
            submit_slot(cur, val)

else:
    # ── PIPELINE + RESULTS PHASE ──────────────────────────────────
    ctrl   = st.session_state.controller
    smgr   = ctrl.state_manager
    thread = st.session_state.workflow_thread

    st.markdown("<div class='section-label'>Research pipeline</div>", unsafe_allow_html=True)

    if thread and thread.is_alive():
        prog  = STATE_PROG.get(smgr.current_state, smgr.progress)
        label = smgr.current_state.value.replace("_", " ").title()
        render_pipeline(prog)
        st.markdown(f"<p style='font-family:JetBrains Mono,monospace;font-size:.7rem;color:var(--accent);margin-top:-2px'>↳ {label}…</p>", unsafe_allow_html=True)
        time.sleep(0.8)
        st.rerun()
    else:
        final_prog = STATE_PROG.get(smgr.current_state, 100)
        render_pipeline(final_prog)

        if smgr.current_state == SystemState.ERROR:
            st.markdown("<p style='font-family:JetBrains Mono,monospace;font-size:.78rem;color:var(--red);margin:12px 0'>✗ Pipeline error — check logs for details.</p>", unsafe_allow_html=True)
        else:
            st.markdown("<p style='font-family:JetBrains Mono,monospace;font-size:.78rem;color:var(--green);margin:12px 0 20px'>✓ Analysis complete</p>", unsafe_allow_html=True)

            consolidated = smgr.data.get("consolidated_output")
            if consolidated:
                render_results(consolidated)

                paths = smgr.data.get("report_paths", {})
                if paths:
                    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
                    d1, d2, _ = st.columns([1, 1, 4])
                    if paths.get("pdf"):
                        with d1:
                            with open(paths["pdf"], "rb") as f:
                                st.download_button("Export PDF", data=f,
                                    file_name="AutoResearch_Report.pdf",
                                    mime="application/pdf",
                                    use_container_width=True)
                    if paths.get("ppt"):
                        with d2:
                            with open(paths["ppt"], "rb") as f:
                                st.download_button("Export PPT", data=f,
                                    file_name="AutoResearch_Report.pptx",
                                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                    use_container_width=True)

    st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
    if st.button("↺ New Analysis", type="secondary"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()