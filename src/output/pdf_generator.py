import os
from datetime import datetime

from .style_manager import get_styles
from .template_manager import build_sections
from .layout_engine import build_pdf


OUTPUT_DIR = "data/outputs"


def generate_pdf_report(consolidated_data: dict) -> str:
    """
    Main entry point for PDF generation.

    Args:
        consolidated_data (dict): Output from Consolidation Agent

    Returns:
        str: Path to generated PDF file
    """

    if not consolidated_data:
        raise ValueError("Consolidated data is empty. Cannot generate PDF.")

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(
        OUTPUT_DIR,
        f"business_report_{timestamp}.pdf"
    )

    try:
        # Step 1: Load Styles
        styles = get_styles()

        # Step 2: Build Structured Sections
        elements = build_sections(consolidated_data, styles)

        # Step 3: Build Final PDF
        build_pdf(file_path, elements)

        return file_path

    except Exception as e:
        raise RuntimeError(f"PDF generation failed: {str(e)}")