# src/ui/web_app.py

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time
import threading
import streamlit as st

from src.orchestration.workflow_controller import WorkflowController
from src.orchestration.state_manager import StateManager, SystemState
from src.agents.intake_agent import IntakeAgent


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------
st.set_page_config(
    page_title="AutoResearch - Business Analysis",
    layout="wide"
)

st.title("🚀 AutoResearch - Automated Business Analysis System")
st.markdown("Generate financial, competitive, and market analysis reports automatically.")


# --------------------------------------------------
# INPUT FORM
# --------------------------------------------------

with st.form("analysis_form"):

    business_idea = st.text_area(
        "Business Idea Description",
        placeholder="Example: AI-powered invoice automation platform for small businesses"
    )

    industry = st.text_input("Industry")

    budget = st.number_input(
        "Budget (USD)",
        min_value=1000,
        step=1000
    )

    timeline = st.slider(
        "Timeline (Months)",
        min_value=1,
        max_value=60,
        value=12
    )

    target_market = st.text_input("Target Market")

    team_size = st.number_input(
        "Team Size",
        min_value=1,
        value=3
    )

    submitted = st.form_submit_button("Start Analysis")


# --------------------------------------------------
# WORKFLOW EXECUTION
# --------------------------------------------------

if submitted:

    if not business_idea or not industry or not target_market:
        st.error("Please fill in all required fields.")
        st.stop()

    # -----------------------------
    # STRUCTURED INPUT
    # -----------------------------
    raw_input = {
        "business_idea": business_idea,
        "industry": industry,
        "budget": budget,
        "timeline_months": timeline,
        "target_market": target_market,
        "team_size": team_size
    }

    controller = WorkflowController()
    state_manager = controller.state_manager

    # -----------------------------
    # FIX: RUN INTAKE AGENT FIRST
    # -----------------------------
    intake_agent = IntakeAgent()
    structured_output = intake_agent.process(raw_input)

    # Store intake output in state
    state_manager.add_data("structured_input", structured_output)

    # IMPORTANT: Make sure search_queries exist
    if not structured_output.get("search_queries"):
        st.error("Intake Agent failed to generate search queries.")
        st.stop()

    state_manager.update_state(SystemState.INPUT_RECEIVED)

    # -----------------------------
    # UI ELEMENTS
    # -----------------------------
    progress_bar = st.progress(0)
    status_text = st.empty()

    # -----------------------------
    # Run Workflow in Background
    # -----------------------------
    def run_workflow():
        controller.run()

    thread = threading.Thread(target=run_workflow)
    thread.start()

    # -----------------------------
    # POLL STATE MANAGER
    # -----------------------------
    while thread.is_alive():
        current_progress = state_manager.progress
        current_state = state_manager.current_state

        progress_bar.progress(current_progress)
        status_text.info(f"Current Stage: {current_state}")

        time.sleep(0.5)

    # -----------------------------
    # FINAL UPDATE
    # -----------------------------
    progress_bar.progress(100)

    if state_manager.current_state == SystemState.ERROR:
        status_text.error("Workflow failed. Check logs.")
    else:
        status_text.success("Pipeline Completed Successfully!")
        st.success("✅ Analysis Completed")

    # -----------------------------
    # OPTIONAL: SHOW EXECUTIVE SUMMARY
    # -----------------------------
    consolidated = state_manager.data.get("consolidated_output")

    if consolidated:
        st.subheader("Executive Summary")
        st.write(consolidated.get("executive_summary"))

        st.subheader("Overall Viability Score")
        st.metric(
            "Score",
            consolidated.get("overall_viability_score"),
            consolidated.get("overall_rating")
        )

        st.subheader("Download Reports")

        report_paths = state_manager.data.get("report_paths")

        if report_paths:
            if report_paths.get("pdf_path"):
                with open(report_paths["pdf_path"], "rb") as f:
                    st.download_button(
                        "Download PDF",
                        data=f,
                        file_name="AutoResearch_Report.pdf",
                        mime="application/pdf"
                    )

            if report_paths.get("ppt_path"):
                with open(report_paths["ppt_path"], "rb") as f:
                    st.download_button(
                        "Download PPT",
                        data=f,
                        file_name="AutoResearch_Report.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
