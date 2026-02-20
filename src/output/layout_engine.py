from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors


def _add_header_footer(canvas_obj, doc):
    """
    Adds header and footer to each page.
    """

    canvas_obj.saveState()

    # Header
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.setFillColor(colors.grey)
    canvas_obj.drawString(inch, A4[1] - 0.75 * inch,
                          "AutoResearch - Automated Business Idea Analysis")

    # Footer Line
    canvas_obj.setStrokeColor(colors.lightgrey)
    canvas_obj.line(inch, 0.75 * inch, A4[0] - inch, 0.75 * inch)

    # Page Number
    page_number_text = f"Page {doc.page}"
    canvas_obj.drawRightString(A4[0] - inch, 0.5 * inch, page_number_text)

    canvas_obj.restoreState()


def build_pdf(file_path, elements):
    """
    Builds the final PDF using provided elements.
    """

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )

    doc.build(
        elements,
        onFirstPage=_add_header_footer,
        onLaterPages=_add_header_footer
    )