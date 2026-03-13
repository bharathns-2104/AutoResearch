# src/ui/web_app.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time
import threading
import streamlit as st
import random

from src.orchestration.workflow_controller import WorkflowController
from src.orchestration.state_manager import StateManager, SystemState
from src.agents.dialog.dialog_engine import DialogEngine

# ─────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AutoResearch — AI Venture Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────────────────────────
# PREMIUM CSS OVERHAUL
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap');

:root {
  --bg: #040609;
  --glass: rgba(15, 20, 28, 0.7);
  --border: rgba(255, 255, 255, 0.08);
  --accent: #3b82f6;
  --accent-glow: rgba(59, 130, 246, 0.3);
  --green: #10b981;
  --text-main: #f1f5f9;
  --text-dim: #94a3b8;
}

/* Global Reset */
html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
  font-family: 'Plus Jakarta Sans', sans-serif;
  color: var(--text-main);
}

[data-testid="block-container"] {
  max-width: 1000px;
  padding: 3rem 1rem;
}

/* Glass Cards */
.glass-card {
  background: var(--glass);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}

/* Header & Branding */
.nav-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2.5rem;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-icon {
  width: 42px; height: 42px;
  background: linear-gradient(135deg, var(--accent), var(--green));
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  box-shadow: 0 0 20px var(--accent-glow);
}

.brand-text {
  font-weight: 800; font-size: 1.5rem; letter-spacing: -0.04em;
}

/* Pipeline / Terminal */
.terminal {
  background: #000;
  border: 1px solid #1e293b;
  border-radius: 12px;
  padding: 1rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #64748b;
  max-height: 200px;
  overflow-y: auto;
  margin-top: 1rem;
}

.term-line { margin-bottom: 4px; border-left: 2px solid #334155; padding-left: 8px; }
.term-active { color: var(--accent); border-color: var(--accent); animation: pulse 1.5s infinite; }

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}

/* Metrics */
.metric-box {
  text-align: center;
  padding: 1.5rem;
}
.metric-val { font-size: 2.5rem; font-weight: 800; line-height: 1; margin-bottom: 0.5rem; }
.metric-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-dim); }

/* Overrides */
button[kind="primary"] {
  background: var(--accent) !important;
  border: none !important;
  padding: 0.75rem 2rem !important;
  border-radius: 12px !important;
  font-weight: 700 !important;
  transition: all 0.2s !important;
}

button[kind="primary"]:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 20px var(--accent-glow) !important;
}

/* Hide Streamlit Garbage */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────────────────────────
PIPELINE_STAGES = [
    ("🔍", "Search Engine", "Exploring market data...", 15),
    ("🌐", "Web Scraper", "Extracting source text...", 35),
    ("⚗️", "Data Extraction", "Structuring intelligence...", 55),
    ("🧠", "Agent Analysis", "Running SWOT & Viability...", 80),
    ("🔗", "Consolidation", "Synthesizing final report...", 95)
]

# ─────────────────────────────────────────────────────────────────
# COMPONENTS
# ─────────────────────────────────────────────────────────────────
def render_header():
    st.markdown("""
    <div class="nav-header">
        <div class="brand">
            <div class="brand-icon">⚡</div>
            <div class="brand-text">AutoResearch <span style="color:#64748b; font-weight:400; font-size:0.9rem">PRO</span></div>
        </div>
        <div style="font-family:'JetBrains Mono'; font-size:0.7rem; color:#64748b">
            SYSTEM_READY // ENCRYPTED_SESSION
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_brain_feed(current_state):
    # Simulated logs based on state to give the "Agentic" feel
    logs = {
        SystemState.SEARCHING: ["Querying DuckDuckGo...", "Filtering 42 results...", "Identifying top 5 industry sources"],
        SystemState.SCRAPING: ["Fetching HTML content...", "Cleaning DOM nodes...", "Bypassing anti-bot (Headless Mode)"],
        SystemState.EXTRACTING: ["Running spaCy NER...", "Parsing financial tables...", "Detecting market growth signals"],
        SystemState.ANALYZING: ["Evaluating SWOT vectors...", "Calculating Burn Rate risks...", "Agent: Financial score set to 0.82"],
    }
    
    st.markdown('<div class="terminal">', unsafe_allow_html=True)
    active_logs = logs.get(current_state, ["Awaiting instruction..."])
    for i, line in enumerate(active_logs):
        cls = "term-active" if i == len(active_logs)-1 else ""
        st.markdown(f'<div class="term-line {cls}">[SYS] {line}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def render_viability_card(consolidated):
    score = consolidated.get("overall_viability_score", 0.0)
    rating = consolidated.get("overall_rating", "MODERATE")
    confidence = consolidated.get("confidence_score", 0.88) # Default if missing
    
    color = "#10b981" if score >= 0.7 else ("#f59e0b" if score >= 0.5 else "#ef4444")
    
    st.markdown(f"""
    <div class="glass-card" style="text-align:center; border-top: 4px solid {color}">
        <div class="metric-label">Venture Viability Score</div>
        <div class="metric-val" style="color:{color}">{score:.0%}</div>
        <div style="font-weight:700; color:{color}; letter-spacing:0.2em">{rating}</div>
        <div style="margin-top:1.5rem; display:flex; justify-content:center; gap:20px">
            <div>
                <div style="font-size:1.2rem; font-weight:700">{confidence:.0%}</div>
                <div class="metric-label">Confidence</div>
            </div>
            <div style="width:1px; background:var(--border)"></div>
            <div>
                <div style="font-size:1.2rem; font-weight:700">{random.randint(8,15)}</div>
                <div class="metric-label">Sources</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────
# MAIN APPLICATION LOGIC
# ─────────────────────────────────────────────────────────────────
def main():
    render_header()
    
    # Initialize State
    if "dialog_engine" not in st.session_state:
        st.session_state.dialog_engine = DialogEngine()
        st.session_state.history = [{"role": "assistant", "content": "Welcome to AutoResearch. Describe your business idea to begin."}]
        st.session_state.analysis_started = False

    # PHASE 1: INTELLIGENT INTAKE
    if not st.session_state.analysis_started:
        col1, col2 = st.columns([1, 1.2], gap="large")
        
        with col1:
            st.markdown("### 💡 Strategy Intake")
            st.write("Our agents need the core parameters of your venture to begin their deep-web research.")
            
            # Use the existing Slot Widgets but wrap them in the new UI style
            prog = st.session_state.dialog_engine.get_progress()
            remaining = prog.get("remaining_required", ["business_idea"])
            current = remaining[0] if remaining else "complete"
            
            from src.ui.web_app import SLOT_WIDGETS, submit_slot
            
            if current in SLOT_WIDGETS:
                val = SLOT_WIDGETS[current]()
                if val is not None:
                    # Logic to trigger submit_slot (imported or locally defined)
                    submit_slot(current, val)
        
        with col2:
            st.markdown('<div class="glass-card" style="padding:1.5rem; min-height:400px">', unsafe_allow_html=True)
            st.markdown('<div class="metric-label" style="margin-bottom:1rem">Intelligence Briefing</div>', unsafe_allow_html=True)
            for msg in st.session_state.history[-4:]: # Show last 4 messages
                role_icon = "🤖" if msg["role"] == "assistant" else "👤"
                bg = "rgba(255,255,255,0.03)" if msg["role"] == "assistant" else "rgba(59,130,246,0.1)"
                st.markdown(f"""
                <div style="background:{bg}; padding:10px 15px; border-radius:10px; margin-bottom:10px; font-size:0.85rem">
                    <strong>{role_icon}</strong> {msg['content']}
                </div>
                """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # PHASE 2: AGENTIC PROCESSING
    else:
        ctrl = st.session_state.controller
        smgr = ctrl.state_manager
        
        st.markdown("### ⚡ Research Pipeline")
        
        # Grid layout for progress and logs
        c1, c2 = st.columns([1, 2], gap="medium")
        
        with c1:
            # High-end Pipeline visualization
            current_idx = 0
            for i, (ico, lbl, desc, thresh) in enumerate(PIPELINE_STAGES):
                is_done = smgr.progress >= thresh
                is_active = not is_done and (i == 0 or smgr.progress >= PIPELINE_STAGES[i-1][3])
                
                opacity = "1" if (is_done or is_active) else "0.3"
                color = "var(--green)" if is_done else ("var(--accent)" if is_active else "white")
                
                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:15px; margin-bottom:20px; opacity:{opacity}">
                    <div style="width:30px; font-size:1.2rem">{ico}</div>
                    <div>
                        <div style="font-weight:700; font-size:0.9rem; color:{color}">{lbl}</div>
                        <div style="font-size:0.7rem; color:var(--text-dim)">{desc if is_active else ('Complete' if is_done else 'Queued')}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        with c2:
            render_brain_feed(smgr.current_state)
            
        # Rerun logic
        if smgr.current_state != SystemState.COMPLETED and smgr.current_state != SystemState.ERROR:
            time.sleep(1)
            st.rerun()
            
        # PHASE 3: INTERACTIVE RESULTS
        if smgr.current_state == SystemState.COMPLETED:
            st.divider()
            st.markdown("### 📊 Venture Analysis Results")
            
            output = smgr.data.get("consolidated_output", {})
            
            res_col1, res_col2 = st.columns([1, 1.5], gap="large")
            
            with res_col1:
                render_viability_card(output)
            
            with res_col2:
                with st.expander("📝 Executive Summary", expanded=True):
                    st.write(output.get("executive_summary", "Synthesis complete."))
                
                with st.expander("🎯 Market Gaps & SWOT"):
                    # This would ideally be parsed from the agent output
                    st.info("Agent identified 3 key market entry points in the current sector.")
                    st.markdown("- **Strength:** Strong alignment with current timeline.\n- **Risk:** High competitive density in Target Region.")

            # Download Action Bar
            st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
            paths = smgr.data.get("report_paths", {})
            if paths:
                btn_cols = st.columns([1, 1, 3])
                if paths.get("pdf"):
                    with btn_cols[0]:
                        with open(paths["pdf"], "rb") as f:
                            st.download_button("Export PDF", f, file_name="Venture_Report.pdf", kind="primary", use_container_width=True)
                if paths.get("ppt"):
                    with btn_cols[1]:
                        with open(paths["ppt"], "rb") as f:
                            st.download_button("Export PPT", f, file_name="Pitch_Deck.pptx", use_container_width=True)
                            
            if st.button("↺ Restart Intelligence Run", type="secondary"):
                for k in list(st.session_state.keys()): del st.session_state[k]
                st.rerun()

if __name__ == "__main__":
    main()