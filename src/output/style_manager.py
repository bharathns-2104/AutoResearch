from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import Paragraph


def get_styles():
    """
    Returns a dictionary of professionally configured styles
    for the AutoResearch PDF report.
    """

    base_styles = getSampleStyleSheet()

    styles = {}

    # ==============================
    # Title Style
    # ==============================
    styles["TitleStyle"] = ParagraphStyle(
        name="TitleStyle",
        parent=base_styles["Normal"],
        fontSize=24,
        leading=28,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.HexColor("#1F3C88"),  # Professional blue
    )

    # ==============================
    # Heading 1 (Section Titles)
    # ==============================
    styles["Heading1Style"] = ParagraphStyle(
        name="Heading1Style",
        parent=base_styles["Normal"],
        fontSize=18,
        leading=22,
        alignment=TA_LEFT,
        spaceBefore=12,
        spaceAfter=8,
        textColor=colors.HexColor("#0A2647"),
    )

    # ==============================
    # Heading 2 (Subsections)
    # ==============================
    styles["Heading2Style"] = ParagraphStyle(
        name="Heading2Style",
        parent=base_styles["Normal"],
        fontSize=14,
        leading=18,
        alignment=TA_LEFT,
        spaceBefore=8,
        spaceAfter=6,
        textColor=colors.HexColor("#144272"),
    )

    # ==============================
    # Body Text
    # ==============================
    styles["BodyStyle"] = ParagraphStyle(
        name="BodyStyle",
        parent=base_styles["Normal"],
        fontSize=11,
        leading=15,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )

    # ==============================
    # Bullet Text
    # ==============================
    styles["BulletStyle"] = ParagraphStyle(
        name="BulletStyle",
        parent=base_styles["Normal"],
        fontSize=11,
        leading=14,
        leftIndent=15,
        bulletIndent=5,
        spaceAfter=4,
    )

    # ==============================
    # Table Header Style
    # ==============================
    styles["TableHeaderStyle"] = ParagraphStyle(
        name="TableHeaderStyle",
        parent=base_styles["Normal"],
        fontSize=11,
        leading=14,
        textColor=colors.white,
    )

    # ==============================
    # Emphasis (Italic)
    # ==============================
    styles["ItalicStyle"] = ParagraphStyle(
        name="ItalicStyle",
        parent=base_styles["Normal"],
        fontSize=11,
        leading=14,
        fontName="Helvetica-Oblique",
    )

    # ==============================
    # Monospace / Data Style
    # ==============================
    styles["CodeStyle"] = ParagraphStyle(
        name="CodeStyle",
        parent=base_styles["Normal"],
        fontSize=10,
        leading=13,
        fontName="Courier",
        backColor=colors.HexColor("#F4F4F4"),
    )

    return styles