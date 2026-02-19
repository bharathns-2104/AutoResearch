from pptx import Presentation
from pptx.util import Inches
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from src.output.chart_builder import ChartBuilder


class PPTGenerator:

    def generate(self, mapped_data, file_path):

        prs = Presentation()
        chart_builder = ChartBuilder()

        # ----------------------------
        # 1️⃣ Title Slide
        # ----------------------------

        slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(slide_layout)

        slide.shapes.title.text = mapped_data["title_page"]["project_title"]
        subtitle = slide.placeholders[1]
        subtitle.text = f"Generated On: {mapped_data['title_page']['generated_at']}"

        # ----------------------------
        # 2️⃣ Executive Summary Slide
        # ----------------------------

        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)

        slide.shapes.title.text = "Executive Summary"
        slide.placeholders[1].text = mapped_data["executive_summary"]["summary_text"]

        # ----------------------------
        # 3️⃣ Overall Score Slide
        # ----------------------------

        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = "Overall Viability"

        overall_score = mapped_data["score_overview"]["overall_score"]
        rating = mapped_data["score_overview"]["rating"]

        slide.placeholders[1].text = (
            f"Score: {overall_score}\n"
            f"Rating: {rating}"
        )

        # ----------------------------
        # 4️⃣ Domain Score Chart Slide
        # ----------------------------

        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = "Domain Score Comparison"

        domain_chart_path = chart_builder.build_domain_score_chart(mapped_data)

        slide.shapes.add_picture(
            domain_chart_path,
            Inches(1),
            Inches(1.5),
            width=Inches(6)
        )

        # ----------------------------
        # 5️⃣ Risk Analysis Slide
        # ----------------------------

        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = "Risk Analysis"

        risks = mapped_data["risk_analysis"]["risks"]
        risk_text = ""

        for risk in risks:
            risk_text += (
                f"{risk['category']} ({risk['severity']}): "
                f"{risk['message']}\n\n"
            )

        slide.placeholders[1].text = risk_text

        # ----------------------------
        # 6️⃣ Recommendations Slide
        # ----------------------------

        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = "Strategic Recommendations"

        rec_text = ""
        for rec in mapped_data["recommendations"]["recommendations"]:
            rec_text += f"• {rec}\n"

        slide.placeholders[1].text = rec_text

        # ----------------------------
        # 7️⃣ Final Decision Slide
        # ----------------------------

        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = "Final Decision"

        slide.placeholders[1].text = mapped_data["decision"]["final_decision"]

        # ----------------------------
        # Save Presentation
        # ----------------------------

        prs.save(file_path)
