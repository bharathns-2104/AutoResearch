# src/ui/web_app.py

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time
import threading
import streamlit as st

from src.orchestration.workflow_controller import WorkflowController
from src.orchestration.state_manager import SystemState
from src.agents.dialog.dialog_engine import DialogEngine


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
# SESSION STATE INITIALIZATION
# --------------------------------------------------

if "dialog_engine" not in st.session_state:
    st.session_state.dialog_engine = DialogEngine()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "analysis_started" not in st.session_state:
    st.session_state.analysis_started = False

if "workflow_thread" not in st.session_state:
    st.session_state.workflow_thread = None

if "controller" not in st.session_state:
    st.session_state.controller = None


# --------------------------------------------------
# DISPLAY CONVERSATION HISTORY
# --------------------------------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# --------------------------------------------------
# CHAT INPUT
# --------------------------------------------------

if not st.session_state.analysis_started:
    user_input = st.chat_input("Describe your business idea...")

    if user_input:

        # Display user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })

        with st.chat_message("user"):
            st.markdown(user_input)

        # Process through dialog engine
        result = st.session_state.dialog_engine.process_message(user_input)

        # Display assistant response
        st.session_state.messages.append({
            "role": "assistant",
            "content": result["response"]
        })

        with st.chat_message("assistant"):
            st.markdown(result["response"])

        # If intake complete → start workflow
        if result["status"] == "complete":

            st.session_state.analysis_started = True
            structured_input = result["data"]

            controller = WorkflowController()
            st.session_state.controller = controller

            # Inject structured input into workflow
            controller.state_manager.add_data("test_input", structured_input)
            controller.state_manager.update_state(SystemState.INITIALIZED)

            # Run workflow in background thread
            def run_workflow():
                controller.run()

            thread = threading.Thread(target=run_workflow)
            thread.start()

            st.session_state.workflow_thread = thread


# --------------------------------------------------
# WORKFLOW PROGRESS TRACKING
# --------------------------------------------------

if st.session_state.analysis_started and st.session_state.controller:

    controller = st.session_state.controller
    state_manager = controller.state_manager
    thread = st.session_state.workflow_thread

    progress_bar = st.progress(0)
    status_text = st.empty()

    while thread.is_alive():

        current_progress = state_manager.progress
        current_state = state_manager.current_state

        progress_bar.progress(current_progress)
        status_text.info(f"Current Stage: {current_state}")

        time.sleep(0.5)

    progress_bar.progress(100)

    if state_manager.current_state == SystemState.ERROR:
        status_text.error("Workflow failed. Check logs.")
    else:
        status_text.success("Pipeline Completed Successfully!")
        st.success("✅ Analysis Completed")


    # --------------------------------------------------
    # DISPLAY RESULTS
    # --------------------------------------------------

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

            if report_paths.get("pdf"):
                with open(report_paths["pdf"], "rb") as f:
                    st.download_button(
                        "Download PDF",
                        data=f,
                        file_name="AutoResearch_Report.pdf",
                        mime="application/pdf"
                    )

            if report_paths.get("ppt"):
                with open(report_paths["ppt"], "rb") as f:
                    st.download_button(
                        "Download PPT",
                        data=f,
                        file_name="AutoResearch_Report.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )


# --------------------------------------------------
# RESET OPTION
# --------------------------------------------------

if st.session_state.analysis_started:
    if st.button("Start New Analysis"):
        st.session_state.dialog_engine = DialogEngine()
        st.session_state.messages = []
        st.session_state.analysis_started = False
        st.session_state.workflow_thread = None
        st.session_state.controller = None
        st.rerun()