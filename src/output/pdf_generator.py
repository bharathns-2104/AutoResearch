from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Image
from src.output.chart_builder import ChartBuilder


class PDFGenerator:

    def generate(self, mapped_data, file_path):
        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=60,
            bottomMargin=40
        )

        elements = []
        styles = getSampleStyleSheet()

        # Custom Styles
        title_style = styles["Title"]
        heading_style = styles["Heading1"]
        body_style = styles["BodyText"]

        # ============================
        # TITLE PAGE
        # ============================

        elements.append(Paragraph(
            mapped_data["title_page"]["project_title"],
            title_style
        ))
        elements.append(Spacer(1, 0.5 * inch))

        elements.append(Paragraph(
            f"Generated On: {mapped_data['title_page']['generated_at']}",
            body_style
        ))
        elements.append(PageBreak())

        # ============================
        # EXECUTIVE SUMMARY
        # ============================

        elements.append(Paragraph("Executive Summary", heading_style))
        elements.append(Spacer(1, 0.2 * inch))

        elements.append(Paragraph(
            mapped_data["executive_summary"]["summary_text"],
            body_style
        ))
        elements.append(PageBreak())

        # ============================
        # OVERALL SCORE
        # ============================

        elements.append(Paragraph("Overall Viability Assessment", heading_style))
        elements.append(Spacer(1, 0.2 * inch))

        score = mapped_data["score_overview"]["overall_score"]
        rating = mapped_data["score_overview"]["rating"]

        elements.append(Paragraph(
            f"Overall Score: <b>{score}</b>",
            body_style
        ))
        elements.append(Paragraph(
            f"Rating: <b>{rating}</b>",
            body_style
        ))

        elements.append(Spacer(1, 0.3 * inch))

        # ============================
        # DOMAIN SCORES TABLE
        # ============================

        elements.append(Paragraph("Domain-Level Scores", heading_style))
        elements.append(Spacer(1, 0.2 * inch))

        domain_scores = mapped_data["domain_scores"]

        table_data = [
            ["Domain", "Score"],
            ["Financial", domain_scores["financial_score"]],
            ["Market", domain_scores["market_score"]],
            ["Competitive", domain_scores["competitive_score"]],
        ]

        table = Table(table_data, colWidths=[3 * inch, 1.5 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ]))

        elements.append(table)
        elements.append(PageBreak())

        # ============================
        # DOMAIN SCORE CHART
        # ============================

        chart_builder = ChartBuilder()
        domain_chart_path = chart_builder.build_domain_score_chart(mapped_data)

        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph("Domain Score Visualization", heading_style))
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Image(domain_chart_path, width=4*inch, height=3*inch))
        elements.append(PageBreak())


        # ============================
        # RISK ANALYSIS
        # ============================

        elements.append(Paragraph("Risk Analysis", heading_style))
        elements.append(Spacer(1, 0.2 * inch))

        risk_data = [["Category", "Severity", "Description"]]

        for risk in mapped_data["risk_analysis"]["risks"]:
            risk_data.append([
                risk["category"],
                risk["severity"],
                risk["message"]
            ])

        risk_table = Table(risk_data, colWidths=[1.5 * inch, 1 * inch, 2.5 * inch])
        risk_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        elements.append(risk_table)
        elements.append(PageBreak())

        # ============================
        # RECOMMENDATIONS
        # ============================

        elements.append(Paragraph("Strategic Recommendations", heading_style))
        elements.append(Spacer(1, 0.2 * inch))

        for rec in mapped_data["recommendations"]["recommendations"]:
            elements.append(Paragraph(f"• {rec}", body_style))
            elements.append(Spacer(1, 0.1 * inch))

        elements.append(PageBreak())

        # ============================
        # FINAL DECISION
        # ============================

        elements.append(Paragraph("Final Decision", heading_style))
        elements.append(Spacer(1, 0.2 * inch))

        elements.append(Paragraph(
            f"<b>{mapped_data['decision']['final_decision']}</b>",
            body_style
        ))

        # ============================
        # OVERALL SCORE CHART
        # ============================

        overall_chart_path = chart_builder.build_overall_score_chart(mapped_data)

        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph("Overall Score Visualization", heading_style))
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Image(overall_chart_path, width=4*inch, height=2*inch))
        elements.append(PageBreak())


        # ============================
        # BUILD DOCUMENT
        # ============================

        doc.build(elements)
