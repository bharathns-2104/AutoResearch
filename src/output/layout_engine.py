from reportlab.platypus import SimpleDocTemplate, Paragraph
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


class TOCDocTemplate(SimpleDocTemplate):
    """
    SimpleDocTemplate subclass that emits TOC entries and bookmarks
    for Heading1 / Heading2 paragraphs. Any TableOfContents flowable
    in the story will subscribe to these notifications.
    """

    def afterFlowable(self, flowable):
        try:
            from reportlab.platypus import Paragraph as RLParagraph
        except ImportError:
            return

        if not isinstance(flowable, RLParagraph):
            return

        style_name = getattr(flowable.style, "name", "")
        if style_name == "Heading1Style":
            level = 0
        elif style_name == "Heading2Style":
            level = 1
        else:
            return

        text = flowable.getPlainText()
        key = f"{text}_{self.page}"
        self.canv.bookmarkPage(key)
        self.notify("TOCEntry", (level, text, self.page))


def build_pdf(file_path, elements):
    """
    Builds the final PDF using provided elements.
    """

    doc = TOCDocTemplate(
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