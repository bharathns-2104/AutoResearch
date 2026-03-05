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
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ─────────────────────────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
  --bg:       #080b10;
  --surf:     #0e1219;
  --surf2:    #141925;
  --border:   #1e2535;
  --border2:  #2a3448;
  --text:     #c8d3e8;
  --dim:      #5a6a85;
  --xdim:     #2e3d54;
  --accent:   #4f9cf9;
  --green:    #00e5b0;
  --warn:     #f9a84f;
  --danger:   #f95f5f;
}

html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
  font-family: 'DM Sans', sans-serif;
  color: var(--text);
}
[data-testid="stAppViewContainer"] > .main { background: var(--bg); }
[data-testid="block-container"] {
  padding: 2.5rem 2.5rem 5rem;
  max-width: 880px;
  margin: 0 auto;
}

.ar-hdr { display:flex; align-items:center; gap:14px; margin-bottom:6px; }
.ar-mark {
  width:40px; height:40px; border-radius:10px; flex-shrink:0;
  background:linear-gradient(135deg,#4f9cf9,#00e5b0);
  display:flex; align-items:center; justify-content:center; font-size:20px;
}
.ar-name { font-family:'Syne',sans-serif; font-weight:800; font-size:1.35rem; color:#e8eef8; letter-spacing:-.03em; }
.ar-tag  { font-family:'DM Mono',monospace; font-size:.62rem; background:#0a2518; color:var(--green); border:1px solid rgba(0,229,176,.22); border-radius:4px; padding:2px 7px; }
.ar-rule { height:1px; margin:10px 0 26px; background:linear-gradient(90deg,rgba(79,156,249,.35),rgba(0,229,176,.15),transparent); }

.stepper { display:flex; gap:4px; margin-bottom:22px; }
.stp { flex:1; display:flex; flex-direction:column; align-items:center; gap:4px; padding:10px 4px; border-radius:8px; border:1px solid transparent; font-family:'DM Mono',monospace; font-size:.6rem; letter-spacing:.05em; transition:all .3s; }
.stp.done   { color:var(--green);  background:rgba(0,229,176,.06);  border-color:rgba(0,229,176,.18); }
.stp.active { color:var(--accent); background:rgba(79,156,249,.08); border-color:rgba(79,156,249,.28); }
.stp.idle   { color:var(--xdim); }
.stp-ico { font-size:.95rem; }

.q-wrap { background:var(--surf); border:1px solid var(--border); border-radius:16px; padding:26px 26px 22px; margin-bottom:18px; position:relative; overflow:hidden; }
.q-wrap::before { content:''; position:absolute; top:0; left:0; right:0; height:3px; background:linear-gradient(90deg,var(--accent),var(--green)); }
.q-step  { font-family:'DM Mono',monospace; font-size:.62rem; color:var(--accent); letter-spacing:.1em; margin-bottom:6px; }
.q-title { font-family:'Syne',sans-serif; font-weight:700; font-size:1.2rem; color:#e8eef8; line-height:1.4; margin-bottom:4px; }
.q-hint  { font-size:.83rem; color:var(--dim); line-height:1.5; }

.chips { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:22px; }
.chip { font-family:'DM Mono',monospace; font-size:.68rem; padding:5px 12px; border-radius:6px; }
.chip.filled { background:#0a2518; color:var(--green); border:1px solid rgba(0,229,176,.25); }
.chip.empty  { background:var(--surf2); color:var(--xdim); border:1px solid var(--border); }

.hist-row { display:flex; align-items:flex-start; gap:10px; margin-bottom:12px; }
.hist-row.u { flex-direction:row-reverse; }
.hist-av { width:26px; height:26px; border-radius:50%; flex-shrink:0; margin-top:2px; display:flex; align-items:center; justify-content:center; font-size:.62rem; font-family:'DM Mono',monospace; }
.hist-av.b { background:linear-gradient(135deg,#4f9cf9,#00e5b0); color:#080b10; font-weight:700; }
.hist-av.u { background:var(--surf2); color:var(--dim); border:1px solid var(--border2); }
.hist-bub { max-width:76%; padding:10px 14px; border-radius:12px; font-size:.87rem; line-height:1.6; }
.hist-bub.b { background:var(--surf2); border:1px solid var(--border); color:var(--text); border-bottom-left-radius:3px; }
.hist-bub.u { background:linear-gradient(135deg,#2a5bbf,#1a8870); color:#fff; border-bottom-right-radius:3px; }

.pipe-wrap { background:var(--surf); border:1px solid var(--border); border-radius:12px; overflow:hidden; margin-bottom:16px; }
.pipe-row { display:flex; align-items:center; gap:12px; padding:12px 18px; border-bottom:1px solid var(--border); font-size:.85rem; }
.pipe-row:last-child { border-bottom:none; }
.pipe-row.done   { color:var(--green); }
.pipe-row.active { color:#e8eef8; background:rgba(79,156,249,.05); }
.pipe-row.idle   { color:var(--xdim); }
.pipe-ico { width:22px; text-align:center; }
.pipe-bar { margin-left:auto; width:80px; height:4px; background:var(--border); border-radius:2px; overflow:hidden; }
.pipe-fill { height:100%; border-radius:2px; }

.res-card { background:var(--surf); border:1px solid var(--border); border-radius:14px; padding:22px; margin-bottom:14px; }
.res-lbl  { font-family:'DM Mono',monospace; font-size:.6rem; color:var(--dim); letter-spacing:.09em; text-transform:uppercase; margin-bottom:10px; }
.big-num  { font-family:'Syne',sans-serif; font-weight:800; font-size:3rem; line-height:1; }
.rp { font-size:.8rem; padding:4px 12px; border-radius:20px; font-weight:600; }
.rp-s { background:#0a2f1e; color:var(--green);  border:1px solid rgba(0,229,176,.28); }
.rp-m { background:#2f1f0a; color:var(--warn);   border:1px solid rgba(249,168,79,.28); }
.rp-w { background:#2f0a0a; color:var(--danger); border:1px solid rgba(249,95,95,.28); }
.sbar { height:6px; background:var(--border); border-radius:3px; overflow:hidden; margin-top:12px; }
.sbar-fill { height:100%; border-radius:3px; background:linear-gradient(90deg,var(--accent),var(--green)); }
.dom-num { font-family:'Syne',sans-serif; font-weight:800; font-size:1.8rem; line-height:1.1; }

/* widget overrides */
.stSlider { margin-top:10px !important; }
div[data-testid="stSlider"] > div > div > div { background:linear-gradient(90deg,var(--accent),var(--green)) !important; }
.stTextInput input, .stNumberInput input { background:var(--surf2) !important; border:1px solid var(--border2) !important; color:var(--text) !important; border-radius:10px !important; font-family:'DM Mono',monospace !important; font-size:.9rem !important; padding:12px 14px !important; }
.stTextInput input:focus, .stNumberInput input:focus { border-color:var(--accent) !important; box-shadow:0 0 0 3px rgba(79,156,249,.12) !important; }

/* primary button */
button[kind="primary"] { background:linear-gradient(135deg,#3a7ff5,#00c9a0) !important; border:none !important; color:#fff !important; font-family:'Syne',sans-serif !important; font-weight:700 !important; font-size:.88rem !important; border-radius:10px !important; padding:.6rem 1.6rem !important; box-shadow:0 4px 16px rgba(79,156,249,.22) !important; }
button[kind="primary"]:hover { transform:translateY(-1px) !important; }

/* secondary / tertiary buttons */
button[kind="secondary"], button[kind="tertiary"] { background:var(--surf2) !important; border:1px solid var(--border2) !important; color:var(--dim) !important; font-family:'DM Mono',monospace !important; font-size:.78rem !important; border-radius:10px !important; padding:.5rem 1.2rem !important; }
button[kind="secondary"]:hover, button[kind="tertiary"]:hover { border-color:var(--accent) !important; color:var(--accent) !important; }

.stDownloadButton > button { background:var(--surf2) !important; border:1px solid var(--border2) !important; color:var(--text) !important; border-radius:10px !important; font-family:'DM Mono',monospace !important; font-size:.78rem !important; }
.stDownloadButton > button:hover { border-color:var(--green) !important; color:var(--green) !important; }

#MainMenu, footer, header { visibility:hidden; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────
STEP_DEFS = [
    ("💡","Idea"),("🏭","Industry"),("💰","Budget"),
    ("📅","Timeline"),("🌍","Market"),("👥","Team"),
]
SLOT_ORDER  = ["business_idea","industry","budget","timeline_months","target_market","team_size"]
SLOT_LABELS = {
    "business_idea":"Idea","industry":"Industry","budget":"Budget",
    "timeline_months":"Timeline","target_market":"Market","team_size":"Team"
}
INDUSTRIES = [
    ("🤖","SaaS"),("💳","FinTech"),("🏥","HealthTech"),("📚","EdTech"),
    ("🛒","E-commerce"),("🚛","Logistics"),("🏠","Real Estate"),("⚙️","Manufacturing"),
    ("🌾","AgriTech"),("🎮","Media & Ent."),("✈️","Travel"),("⚖️","Legal Tech"),
    ("👥","HR Tech"),("🚗","Automotive"),
]
PIPELINE_STAGES = [
    ("🔍","Search",20),("🌐","Scraping",42),("⚗️","Extraction",64),
    ("🧠","Analysis",80),("🔗","Consolidate",92),("📄","Report",100),
]
STATE_PROG = {
    SystemState.INPUT_RECEIVED:10, SystemState.SEARCHING:25,
    SystemState.SCRAPING:45,       SystemState.EXTRACTING:65,
    SystemState.ANALYZING:80,      SystemState.CONSOLIDATING:90,
    SystemState.GENERATING_REPORT:95, SystemState.COMPLETED:100,
}


# ─────────────────────────────────────────────────────────────────
# PURE HTML RENDERERS  (no st.empty wrappers — avoids the raw-HTML bug)
# ─────────────────────────────────────────────────────────────────
def render_header():
    st.markdown("""
    <div class="ar-hdr">
      <div class="ar-mark">⚡</div>
      <span class="ar-name">AutoResearch</span>
      <span class="ar-tag">v2</span>
    </div>
    <div class="ar-rule"></div>
    """, unsafe_allow_html=True)


def render_stepper(filled):
    n = len(filled)
    html = '<div class="stepper">'
    for i,(ico,lbl) in enumerate(STEP_DEFS):
        cls = "done" if i < n else ("active" if i == n else "idle")
        html += f'<div class="stp {cls}"><span class="stp-ico">{ico}</span>{lbl}</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_chips(filled):
    html = '<div class="chips">'
    for s in SLOT_ORDER:
        lbl = SLOT_LABELS[s]
        cls = "filled" if s in filled else "empty"
        ico = "✓ " if s in filled else ""
        html += f'<span class="chip {cls}">{ico}{lbl}</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_history(messages):
    html = ""
    for m in messages:
        cls = "b" if m["role"] == "assistant" else "u"
        row = "" if m["role"] == "assistant" else "u"
        av  = "AR" if m["role"] == "assistant" else "You"
        html += f"""<div class="hist-row {row}">
          <div class="hist-av {cls}">{av}</div>
          <div class="hist-bub {cls}">{m['content']}</div>
        </div>"""
    if html:
        st.markdown(html, unsafe_allow_html=True)


def render_q_card(step_n, title, hint=""):
    hint_html = f"<div class='q-hint'>{hint}</div>" if hint else ""
    st.markdown(f"""
    <div class="q-wrap">
      <div class="q-step">STEP {step_n} OF 6</div>
      <div class="q-title">{title}</div>
      {hint_html}
    </div>""", unsafe_allow_html=True)


def render_pipeline(progress):
    html = '<div class="pipe-wrap">'
    for ico,lbl,thresh in PIPELINE_STAGES:
        span = 22
        if progress >= thresh:
            cls,fw,fc = "done","100%","#00e5b0"
        elif progress >= thresh - span:
            pct = int(((progress-(thresh-span))/span)*100)
            cls,fw,fc = "active",f"{pct}%","#4f9cf9"
        else:
            cls,fw,fc = "idle","0%","#1e2535"
        html += f"""<div class="pipe-row {cls}">
          <span class="pipe-ico">{ico}</span><span>{lbl}</span>
          <div class="pipe-bar"><div class="pipe-fill" style="width:{fw};background:{fc}"></div></div>
        </div>"""
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_results(consolidated):
    score  = consolidated.get("overall_viability_score", 0)
    rating = consolidated.get("overall_rating", "—")
    summary = consolidated.get("executive_summary", "")
    rp_cls = {"Strong":"rp-s","Moderate":"rp-m","Weak":"rp-w"}.get(rating,"rp-m")
    color  = "#00e5b0" if score >= 0.7 else ("#f9a84f" if score >= 0.5 else "#f95f5f")

    st.markdown(f"""
    <div class="res-card">
      <div class="res-lbl">Overall Viability</div>
      <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:4px">
        <span class="big-num" style="color:{color}">{score:.0%}</span>
        <span class="rp {rp_cls}">{rating}</span>
      </div>
      <div class="sbar"><div class="sbar-fill" style="width:{score*100:.0f}%"></div></div>
    </div>""", unsafe_allow_html=True)

    if summary:
        st.markdown(f"""
        <div class="res-card">
          <div class="res-lbl">Executive Summary</div>
          <p style="font-size:.9rem;line-height:1.65;margin:0;color:var(--text)">{summary}</p>
        </div>""", unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    for col,lbl,val,clr in [
        (c1,"Financial",  consolidated.get("financial_score",  0),"#4f9cf9"),
        (c2,"Market",     consolidated.get("market_score",     0),"#00e5b0"),
        (c3,"Competitive",consolidated.get("competitive_score",0),"#f9a84f"),
    ]:
        with col:
            st.markdown(f"""
            <div class="res-card">
              <div class="res-lbl">{lbl}</div>
              <div class="dom-num" style="color:{clr}">{val:.0%}</div>
              <div class="sbar"><div class="sbar-fill" style="width:{val*100:.0f}%;background:{clr}"></div></div>
            </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# INTERACTIVE SLOT WIDGETS
# Each returns the collected value, or None if not yet submitted.
# ─────────────────────────────────────────────────────────────────

def widget_business_idea():
    render_q_card(1, "What's your business idea?",
                  "Describe it in a sentence — the more specific, the better.")

    st.markdown("<p style='font-family:DM Mono,monospace;font-size:.65rem;color:#5a6a85;letter-spacing:.07em;margin-bottom:8px'>QUICK START — click to pre-fill</p>", unsafe_allow_html=True)
    suggestions = [
        "AI-powered scheduling SaaS for clinics",
        "EV charging network for apartment buildings",
        "B2B logistics marketplace for last-mile delivery",
        "EdTech platform for online coding bootcamps",
    ]
    c1,c2 = st.columns(2)
    for i,(sug,col) in enumerate(zip(suggestions,[c1,c2,c1,c2])):
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
                  "Pick the closest match — you can always specify a custom one below.")

    selected = st.session_state.get("_ind_sel", "")

    # 4-column clickable grid using st.columns + buttons styled via CSS
    rows_of_4 = [INDUSTRIES[i:i+4] for i in range(0,len(INDUSTRIES),4)]
    for row in rows_of_4:
        cols = st.columns(4)
        for col,(ico,name) in zip(cols,row):
            with col:
                is_sel = selected == name
                border = "#4f9cf9" if is_sel else "#1e2535"
                bg     = "rgba(79,156,249,.12)" if is_sel else "#141925"
                # The visual card is purely decorative HTML; the real click is the button below it
                st.markdown(f"""
                <div style="background:{bg};border:1px solid {border};border-radius:10px;
                  padding:12px 6px;text-align:center;pointer-events:none;margin-bottom:-46px">
                  <div style="font-size:1.4rem">{ico}</div>
                  <div style="font-family:'DM Mono',monospace;font-size:.62rem;color:#c8d3e8;margin-top:4px">{name}</div>
                </div>""", unsafe_allow_html=True)
                if st.button("‎", key=f"ind_{name}", use_container_width=True,
                             help=f"Select {name}"):   # invisible label, visual from card above
                    st.session_state["_ind_sel"] = name
                    st.rerun()

    st.markdown("<p style='font-family:DM Mono,monospace;font-size:.65rem;color:#5a6a85;margin-top:14px;margin-bottom:6px'>OR TYPE A CUSTOM INDUSTRY</p>", unsafe_allow_html=True)
    custom = st.text_input("custom_ind", placeholder="e.g. PropTech, CleanEnergy, BioTech…",
                           key="ind_custom_input", label_visibility="collapsed")

    final = custom.strip() if custom.strip() else selected
    if selected and not custom.strip():
        st.markdown(f"<p style='font-family:DM Mono,monospace;font-size:.75rem;color:#4f9cf9;margin:4px 0'>Selected: {selected}</p>", unsafe_allow_html=True)

    if st.button("Continue →", key="go_ind", type="primary"):
        if final:
            return final
        st.warning("Please select or type an industry.")
    return None


def widget_budget():
    render_q_card(3, "What's your available budget?",
                  "Used to calculate financial runway and viability score.")

    st.markdown("<p style='font-family:DM Mono,monospace;font-size:.65rem;color:#5a6a85;letter-spacing:.07em;margin-bottom:8px'>COMMON RANGES</p>", unsafe_allow_html=True)
    presets = [("Bootstrap","$10k–$50k",25_000),("Seed","$100k–$500k",250_000),
               ("Series A","$1M–$5M",2_000_000),("Scale-up","$5M+",7_500_000)]
    pc = st.columns(4)
    for col,(lbl,rng,amt) in zip(pc,presets):
        with col:
            st.markdown(f"""
            <div style="background:#141925;border:1px solid #1e2535;border-radius:8px;
              padding:10px 8px;text-align:center;margin-bottom:-42px;pointer-events:none">
              <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:.85rem;color:#e8eef8">{lbl}</div>
              <div style="font-family:'DM Mono',monospace;font-size:.62rem;color:#5a6a85;margin-top:2px">{rng}</div>
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
    <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:2rem;
         color:#4f9cf9;margin:10px 0 4px">${budget_usd:,}
    </div>""", unsafe_allow_html=True)

    if st.button("Continue →", key="go_budget", type="primary"):
        return budget_usd
    return None


def widget_timeline():
    render_q_card(4, "What's your target timeline?",
                  "How many months to launch or hit your key milestone?")

    quick = [3,6,9,12,18,24,36,48]
    st.markdown("<p style='font-family:DM Mono,monospace;font-size:.65rem;color:#5a6a85;letter-spacing:.07em;margin-bottom:8px'>QUICK PICK</p>", unsafe_allow_html=True)
    qcols = st.columns(len(quick))
    for col,mo in zip(qcols,quick):
        with col:
            yr = mo // 12; rm = mo % 12
            lbl = (f"{yr}yr" + (f" {rm}mo" if rm else "")) if mo >= 12 else f"{mo}mo"
            if st.button(lbl, key=f"tl_{mo}", use_container_width=True):
                st.session_state["_tl_val"] = mo
                st.rerun()

    selected_tl = st.session_state.get("_tl_val", 12)
    st.markdown("<p style='font-family:DM Mono,monospace;font-size:.65rem;color:#5a6a85;margin-top:14px;margin-bottom:6px'>FINE-TUNE (months)</p>", unsafe_allow_html=True)
    final_tl = st.number_input("tl_num", min_value=1, max_value=60, value=selected_tl,
                               step=1, key="tl_input", label_visibility="collapsed")

    st.markdown(f"""
    <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:2rem;
         color:#4f9cf9;margin:8px 0 4px">{int(final_tl)} months
    </div>""", unsafe_allow_html=True)

    if st.button("Continue →", key="go_tl", type="primary"):
        if 1 <= int(final_tl) <= 60:
            return int(final_tl)
        st.warning("Timeline must be between 1 and 60 months.")
    return None


def widget_target_market():
    render_q_card(5, "Who is your target market?",
                  "Describe the geography or customer segment you're focusing on.")

    regions = [
        ("🇺🇸","United States"),("🇮🇳","India"),("🇬🇧","United Kingdom"),
        ("🇪🇺","Europe"),("🇸🇬","Southeast Asia"),("🌍","Global"),
        ("🏢","US Small Businesses"),("🏥","US Healthcare"),("🎓","University Students"),
    ]
    st.markdown("<p style='font-family:DM Mono,monospace;font-size:.65rem;color:#5a6a85;letter-spacing:.07em;margin-bottom:8px'>COMMON MARKETS</p>", unsafe_allow_html=True)

    rows = [regions[i:i+3] for i in range(0,len(regions),3)]
    for row in rows:
        rcols = st.columns(3)
        for col,(flag,name) in zip(rcols,row):
            with col:
                if st.button(f"{flag} {name}", key=f"mkt_{name}", use_container_width=True):
                    st.session_state["_mkt_val"] = name
                    st.rerun()

    prefill = st.session_state.get("_mkt_val","")
    if prefill:
        st.markdown(f"<p style='font-family:DM Mono,monospace;font-size:.75rem;color:#4f9cf9;margin:8px 0 4px'>Selected: {prefill}</p>", unsafe_allow_html=True)

    st.markdown("<p style='font-family:DM Mono,monospace;font-size:.65rem;color:#5a6a85;margin-top:10px;margin-bottom:6px'>OR DESCRIBE IT</p>", unsafe_allow_html=True)
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
                  "Optional — press Skip if you prefer not to share.")

    personas = [(1,"Solo Founder"),(2,"Co-founders"),(3,"Small trio"),
                (5,"Early team"),(10,"Squad"),(20,"Startup"),(50,"Scale-up")]
    team_val = st.slider("team_slider", min_value=1, max_value=50, value=3, step=1,
                         key="team_slider_w", label_visibility="collapsed")

    label = next((lbl for size,lbl in reversed(personas) if team_val >= size), "Solo Founder")
    st.markdown(f"""
    <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:2rem;
         color:#4f9cf9;margin:8px 0 4px">
      {team_val} <span style="font-size:1rem;color:#5a6a85;font-weight:400">{label}</span>
    </div>""", unsafe_allow_html=True)

    col1,col2,_ = st.columns([1,1,4])
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
            "role":"assistant",
            "content": st.session_state.dialog_engine.get_opening_message()
        }]
    for k,v in [("filled_slots",[]),("current_slot","business_idea"),
                ("analysis_started",False),("workflow_thread",None),("controller",None)]:
        if k not in st.session_state:
            st.session_state[k] = v

_init()


# ─────────────────────────────────────────────────────────────────
# SUBMIT SLOT → dialog engine
# ─────────────────────────────────────────────────────────────────
def submit_slot(slot, value):
    text = (f"${value:,}" if slot=="budget"
            else f"{value} months" if slot=="timeline_months"
            else str(value))

    st.session_state.history.append({"role":"user","content":text})
    result = st.session_state.dialog_engine.process_message(text)
    st.session_state.history.append({"role":"assistant","content":result["response"]})

    prog = st.session_state.dialog_engine.get_progress()
    st.session_state.filled_slots = prog.get("filled",[])
    remaining = prog.get("remaining_required",[])
    st.session_state.current_slot = remaining[0] if remaining else ""

    # clear temp keys
    for k in ["_idea_prefill","_ind_sel","_budget_k","_tl_val","_mkt_val"]:
        st.session_state.pop(k,None)

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

    # History — show last 3 exchanges, rest collapsed
    hist = st.session_state.history
    if len(hist) > 4:
        with st.expander(f"View earlier conversation ({len(hist)-2} messages)", expanded=False):
            render_history(hist[:-2])
        render_history(hist[-2:])
    else:
        render_history(hist)

    # Current interactive widget
    cur = st.session_state.current_slot
    if cur and cur in SLOT_WIDGETS:
        val = SLOT_WIDGETS[cur]()
        if val is not None:
            submit_slot(cur, val)

else:
    # ── PIPELINE + RESULTS PHASE ──────────────────────────────────
    ctrl  = st.session_state.controller
    smgr  = ctrl.state_manager
    thread = st.session_state.workflow_thread

    st.markdown("<p style='font-family:DM Mono,monospace;font-size:.72rem;color:#5a6a85;letter-spacing:.07em;margin-bottom:14px'>PIPELINE RUNNING</p>", unsafe_allow_html=True)

    if thread and thread.is_alive():
        # Poll until done — each rerun refreshes the pipeline visual
        prog  = STATE_PROG.get(smgr.current_state, smgr.progress)
        label = smgr.current_state.value.replace("_"," ").title()
        render_pipeline(prog)
        st.markdown(f"<p style='font-family:DM Mono,monospace;font-size:.72rem;color:#4f9cf9;margin-top:-4px'>↳ {label}…</p>", unsafe_allow_html=True)
        time.sleep(0.8)
        st.rerun()
    else:
        # Final state
        final_prog = STATE_PROG.get(smgr.current_state, 100)
        render_pipeline(final_prog)

        if smgr.current_state == SystemState.ERROR:
            st.markdown("<p style='font-family:DM Mono,monospace;font-size:.8rem;color:#f95f5f;margin:10px 0'>✗ Pipeline error — check logs for details.</p>", unsafe_allow_html=True)
        else:
            st.markdown("<p style='font-family:DM Mono,monospace;font-size:.8rem;color:#00e5b0;margin:10px 0 22px'>✓ Analysis complete</p>", unsafe_allow_html=True)

            consolidated = smgr.data.get("consolidated_output")
            if consolidated:
                render_results(consolidated)

                paths = smgr.data.get("report_paths", {})
                if paths:
                    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
                    d1,d2,_ = st.columns([1,1,4])
                    if paths.get("pdf"):
                        with d1:
                            with open(paths["pdf"],"rb") as f:
                                st.download_button("⬇ PDF Report", data=f,
                                    file_name="AutoResearch_Report.pdf",
                                    mime="application/pdf")
                    if paths.get("ppt"):
                        with d2:
                            with open(paths["ppt"],"rb") as f:
                                st.download_button("⬇ PPT Deck", data=f,
                                    file_name="AutoResearch_Report.pptx",
                                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")

    st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
    if st.button("↺ Start New Analysis", type="secondary"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()