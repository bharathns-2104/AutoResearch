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
# GLOBAL CSS
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

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

html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
  font-family: 'Inter', -apple-system, sans-serif;
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}
[data-testid="stAppViewContainer"] > .main { background: var(--bg); }
[data-testid="block-container"] {
  padding: 2rem 1.5rem 6rem;
  max-width: 780px;
  margin: 0 auto;
}
* { box-sizing: border-box; }

/* ── Header ── */
.ar-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 2rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border);
}
.ar-logo {
  width: 32px; height: 32px;
  background: linear-gradient(135deg, #6366f1, #818cf8);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 15px; font-weight: 700; color: #fff;
  letter-spacing: -.02em;
  flex-shrink: 0;
  box-shadow: 0 0 16px rgba(99,102,241,.35);
}
.ar-wordmark { font-size: 1rem; font-weight: 600; color: var(--text); letter-spacing: -.02em; }
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
.ar-subtitle {
  margin-left: auto;
  font-size: .75rem;
  color: var(--text-dim);
  font-family: 'JetBrains Mono', monospace;
}

/* ── Chat Container ── */
.chat-container {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-bottom: 1rem;
}

/* ── Chat Message Row ── */
.chat-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  animation: fadeUp .3s ease both;
}
.chat-row.user-row { flex-direction: row-reverse; }

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── Avatars ── */
.chat-av {
  width: 30px; height: 30px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: .58rem; font-weight: 700;
  flex-shrink: 0;
}
.av-bot {
  background: linear-gradient(135deg, #6366f1, #818cf8);
  color: #fff;
  box-shadow: 0 0 10px rgba(99,102,241,.4);
}
.av-user {
  background: var(--surface2);
  color: var(--text-dim);
  border: 1px solid var(--border-lg);
}

/* ── Bubbles ── */
.chat-bubble {
  max-width: 76%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: .875rem;
  line-height: 1.65;
  word-break: break-word;
}
.bubble-bot {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  border-bottom-left-radius: 4px;
}
.bubble-user {
  background: linear-gradient(135deg, rgba(99,102,241,.18), rgba(99,102,241,.08));
  border: 1px solid rgba(99,102,241,.2);
  color: var(--text);
  border-bottom-right-radius: 4px;
}

/* ── Typing Indicator ── */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  animation: fadeUp .3s ease both;
}
.typing-dots {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  border-bottom-left-radius: 4px;
  padding: 12px 16px;
  display: flex;
  gap: 5px;
  align-items: center;
}
.dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--text-xdim);
  animation: bounce 1.2s infinite;
}
.dot:nth-child(2) { animation-delay: .2s; }
.dot:nth-child(3) { animation-delay: .4s; }
@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: .4; }
  30%            { transform: translateY(-5px); opacity: 1; }
}

/* ── Progress chips below input ── */
.progress-bar-wrap {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: .75rem;
}
.slot-chip {
  font-family: 'JetBrains Mono', monospace;
  font-size: .6rem;
  padding: 2px 8px;
  border-radius: 20px;
  letter-spacing: .04em;
}
.chip-done  { background: var(--green-dim);  color: var(--green); border: 1px solid rgba(34,197,94,.2); }
.chip-empty { background: var(--surface2); color: var(--text-xdim); border: 1px solid var(--border); }

/* ── Pipeline ── */
.pipe-container {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin-bottom: 1rem;
}
.pipe-row {
  display: flex; align-items: center; gap: 12px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--border);
  font-size: .85rem; transition: background .2s;
}
.pipe-row:last-child { border-bottom: none; }
.pipe-row.done   { color: var(--green); }
.pipe-row.active { color: var(--text); background: rgba(99,102,241,.05); }
.pipe-row.idle   { color: var(--text-xdim); }
.pipe-icon { width: 18px; font-size: .9rem; text-align: center; }
.pipe-name { flex: 1; font-weight: 500; }
.pipe-status { font-family: 'JetBrains Mono', monospace; font-size: .6rem; letter-spacing: .05em; }
.pipe-track { width: 72px; height: 3px; background: var(--border); border-radius: 2px; overflow: hidden; }
.pipe-fill  { height: 100%; border-radius: 2px; }

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
  font-size: .58rem; letter-spacing: .1em;
  color: var(--text-dim); text-transform: uppercase; margin-bottom: .75rem;
}
.score-big  { font-size: 2.5rem; font-weight: 700; line-height: 1; letter-spacing: -.03em; }
.rating-pill { display: inline-block; font-size: .7rem; font-weight: 600; padding: 3px 10px; border-radius: 20px; letter-spacing: .04em; }
.pill-strong   { background: var(--green-dim); color: var(--green); border: 1px solid rgba(34,197,94,.2); }
.pill-moderate { background: rgba(245,158,11,.1); color: var(--amber); border: 1px solid rgba(245,158,11,.2); }
.pill-weak     { background: rgba(239,68,68,.1); color: var(--red); border: 1px solid rgba(239,68,68,.2); }
.score-bar  { height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; margin-top: .75rem; }
.score-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, var(--accent), var(--green)); }
.sub-score-val { font-size: 1.5rem; font-weight: 700; letter-spacing: -.02em; line-height: 1.1; }

/* ── Inputs ── */
.stTextInput input, .stChatInput textarea {
  background: var(--surface2) !important;
  border: 1px solid var(--border-lg) !important;
  color: var(--text) !important;
  border-radius: var(--radius-sm) !important;
  font-family: 'Inter', sans-serif !important;
  font-size: .88rem !important;
}
.stTextInput input:focus, .stChatInput textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px var(--accent-dim) !important;
}

/* ── Chat input container ── */
[data-testid="stChatInputContainer"] {
  background: var(--surface2) !important;
  border: 1px solid var(--border-lg) !important;
  border-radius: var(--radius-md) !important;
}
[data-testid="stChatInputContainer"]:focus-within {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px var(--accent-dim) !important;
}

/* ── Buttons ── */
button[kind="primary"] {
  background: var(--accent) !important; border: none !important;
  color: #fff !important; font-family: 'Inter', sans-serif !important;
  font-weight: 600 !important; font-size: .85rem !important;
  border-radius: var(--radius-sm) !important;
  transition: opacity .15s, transform .15s !important;
}
button[kind="primary"]:hover { opacity: .88 !important; transform: translateY(-1px) !important; }
button[kind="secondary"], button[kind="tertiary"] {
  background: var(--surface2) !important;
  border: 1px solid var(--border-lg) !important;
  color: var(--text-dim) !important;
  font-family: 'Inter', sans-serif !important;
  font-size: .82rem !important;
  border-radius: var(--radius-sm) !important;
}
button[kind="secondary"]:hover, button[kind="tertiary"]:hover {
  border-color: var(--accent) !important; color: var(--accent) !important;
}

/* ── Download Button ── */
.stDownloadButton > button {
  background: var(--surface2) !important; border: 1px solid var(--border-lg) !important;
  color: var(--text) !important; border-radius: var(--radius-sm) !important;
  font-weight: 500 !important;
}
.stDownloadButton > button:hover { border-color: var(--accent) !important; color: var(--accent) !important; }

/* ── Alerts ── */
div[data-testid="stAlert"] {
  background: var(--surface2) !important; border: 1px solid var(--border-lg) !important;
  border-radius: var(--radius-sm) !important; color: var(--text-dim) !important;
}

/* ── Section label ── */
.section-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: .6rem; letter-spacing: .1em;
  color: var(--text-xdim); text-transform: uppercase; margin-bottom: .5rem;
}

/* ── Hide default Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────
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
SLOT_LABELS = {
    "business_idea": "Idea", "industry": "Industry", "budget": "Budget",
    "timeline_months": "Timeline", "target_market": "Market", "team_size": "Team"
}
SLOT_ORDER = ["business_idea", "industry", "budget", "timeline_months", "target_market", "team_size"]


# ─────────────────────────────────────────────────────────────────
# RENDER HELPERS
# ─────────────────────────────────────────────────────────────────

def render_header():
    st.markdown("""
    <div class="ar-header">
      <div class="ar-logo">AR</div>
      <span class="ar-wordmark">AutoResearch</span>
      <span class="ar-badge">BETA</span>
      <span class="ar-subtitle">Business Intelligence · AI-powered</span>
    </div>
    """, unsafe_allow_html=True)


def render_progress_chips(filled_slots: list):
    html = '<div class="progress-bar-wrap">'
    for s in SLOT_ORDER:
        lbl = SLOT_LABELS[s]
        if s in filled_slots:
            html += f'<span class="slot-chip chip-done">✓ {lbl}</span>'
        else:
            html += f'<span class="slot-chip chip-empty">{lbl}</span>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_chat_history(messages: list):
    html = '<div class="chat-container">'
    for m in messages:
        is_bot = m["role"] == "assistant"
        row_cls = "" if is_bot else "user-row"
        av_cls  = "av-bot" if is_bot else "av-user"
        av_lbl  = "AR" if is_bot else "You"
        bub_cls = "bubble-bot" if is_bot else "bubble-user"
        # Escape any raw HTML in content for safety
        content = m["content"].replace("<", "&lt;").replace(">", "&gt;")
        html += f"""<div class="chat-row {row_cls}">
          <div class="chat-av {av_cls}">{av_lbl}</div>
          <div class="chat-bubble {bub_cls}">{content}</div>
        </div>"""
    html += '</div>'
    if messages:
        st.markdown(html, unsafe_allow_html=True)


def render_typing_indicator():
    st.markdown("""
    <div class="typing-indicator">
      <div class="chat-av av-bot">AR</div>
      <div class="typing-dots">
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_pipeline(progress: int):
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
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_results(consolidated: dict):
    score   = consolidated.get("overall_viability_score", 0)
    rating  = consolidated.get("overall_rating", "—")
    summary = consolidated.get("executive_summary", "")
    color   = "var(--green)" if score >= 0.7 else ("var(--amber)" if score >= 0.5 else "var(--red)")
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
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────
def _init():
    if "dialog_engine" not in st.session_state:
        st.session_state.dialog_engine = DialogEngine()
    if "messages" not in st.session_state:
        st.session_state.messages = [{
            "role": "assistant",
            "content": st.session_state.dialog_engine.get_opening_message()
        }]
    for k, v in [
        ("filled_slots", []),
        ("analysis_started", False),
        ("workflow_thread", None),
        ("controller", None),
        ("_show_typing", False),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

_init()


# ─────────────────────────────────────────────────────────────────
# WORKFLOW LAUNCH
# ─────────────────────────────────────────────────────────────────
def _launch_workflow(structured_input: dict):
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
# HANDLE USER MESSAGE
# ─────────────────────────────────────────────────────────────────
def handle_user_message(user_text: str):
    """Process a user message through the DialogEngine and update state."""
    # Append user message
    st.session_state.messages.append({"role": "user", "content": user_text})

    # Run dialog engine
    result = st.session_state.dialog_engine.process_message(user_text)

    # Update progress chips
    prog = st.session_state.dialog_engine.get_progress()
    st.session_state.filled_slots = prog.get("filled", [])

    # Append bot response
    st.session_state.messages.append({"role": "assistant", "content": result["response"]})

    # Launch workflow if all slots filled
    if result["status"] == "complete":
        _launch_workflow(result["data"])


# ─────────────────────────────────────────────────────────────────
# MAIN RENDER
# ─────────────────────────────────────────────────────────────────
render_header()

# ══════════════════════════════════════════════════════════
# INTAKE PHASE — Chatbot
# ══════════════════════════════════════════════════════════
if not st.session_state.analysis_started:

    # Progress chips
    render_progress_chips(st.session_state.filled_slots)

    # Chat history
    render_chat_history(st.session_state.messages)

    # Chat input (at bottom)
    user_input = st.chat_input("Type your message…", key="chat_input")

    if user_input and user_input.strip():
        handle_user_message(user_input.strip())
        st.rerun()

# ══════════════════════════════════════════════════════════
# PIPELINE + RESULTS PHASE
# ══════════════════════════════════════════════════════════
else:
    ctrl   = st.session_state.controller
    smgr   = ctrl.state_manager
    thread = st.session_state.workflow_thread

    st.markdown("<div class='section-label'>Research Pipeline</div>", unsafe_allow_html=True)

    if thread and thread.is_alive():
        prog  = STATE_PROG.get(smgr.current_state, smgr.progress)
        label = smgr.current_state.value.replace("_", " ").title()
        render_pipeline(prog)
        st.markdown(
            f"<p style='font-family:JetBrains Mono,monospace;font-size:.7rem;"
            f"color:var(--accent);margin-top:-2px'>↳ {label}…</p>",
            unsafe_allow_html=True
        )
        time.sleep(0.8)
        st.rerun()
    else:
        final_prog = STATE_PROG.get(smgr.current_state, 100)
        render_pipeline(final_prog)

        if smgr.current_state == SystemState.ERROR:
            errors = smgr.errors if hasattr(smgr, "errors") else []
            err_detail = errors[-1] if errors else "Check server logs for details."
            st.markdown(
                f"<p style='font-family:JetBrains Mono,monospace;font-size:.78rem;"
                f"color:var(--red);margin:12px 0'>✗ Pipeline error — {err_detail}</p>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                "<p style='font-family:JetBrains Mono,monospace;font-size:.78rem;"
                "color:var(--green);margin:12px 0 20px'>✓ Analysis complete</p>",
                unsafe_allow_html=True
            )

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
                                st.download_button(
                                    "Export PDF", data=f,
                                    file_name="AutoResearch_Report.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                    if paths.get("ppt"):
                        with d2:
                            with open(paths["ppt"], "rb") as f:
                                st.download_button(
                                    "Export PPT", data=f,
                                    file_name="AutoResearch_Report.pptx",
                                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                    use_container_width=True
                                )

    st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
    if st.button("↺ New Analysis", type="secondary"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()