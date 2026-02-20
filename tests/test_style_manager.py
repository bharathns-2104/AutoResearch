# test_style_manager.py

from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.pagesizes import A4
from src.output.style_manager import get_styles

doc = SimpleDocTemplate("style_test.pdf", pagesize=A4)
styles = get_styles()

elements = []
elements.append(Paragraph("AutoResearch Report", styles["TitleStyle"]))
elements.append(Paragraph("Executive Summary", styles["Heading1Style"]))
elements.append(Paragraph("This is body text for testing formatting.", styles["BodyStyle"]))

doc.build(elements)
print("Style test PDF generated.")