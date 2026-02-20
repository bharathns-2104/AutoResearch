from reportlab.platypus import Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Image
from reportlab.lib.units import inch

from .chart_creator import (
    create_cost_pie,
    create_runway_chart,
    create_market_size_chart,
    create_score_chart
)


def build_sections(data, styles):
    """
    Converts consolidated JSON data into structured PDF elements.
    Returns a list of flowables (elements).
    """

    elements = []

    # ======================================================
    # 1. TITLE PAGE
    # ======================================================
    elements.append(Paragraph("AutoResearch Business Analysis Report", styles["TitleStyle"]))
    elements.append(Spacer(1, 0.3 * inch))

    idea = data.get("idea_details", {}).get("business_idea", "N/A")
    elements.append(Paragraph(f"Idea: {idea}", styles["BodyStyle"]))
    elements.append(PageBreak())

    # ======================================================
    # 2. EXECUTIVE SUMMARY
    # ======================================================
    elements.append(Paragraph("Executive Summary", styles["Heading1Style"]))
    summary = data.get("executive_summary", "No summary available.")
    elements.append(Paragraph(summary, styles["BodyStyle"]))
    elements.append(PageBreak())

    # ======================================================
    # 3. FINANCIAL ANALYSIS
    # ======================================================
    elements.append(Paragraph("Financial Analysis", styles["Heading1Style"]))

    financial = data.get("financial_analysis", {})
    cost_data = financial.get("estimated_startup_cost", {})

    if cost_data:
        table_data = [["Category", "Amount (USD)"]]
        for key, value in cost_data.items():
            table_data.append([key.capitalize(), f"${value:,}"])

        table = Table(table_data, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A2647")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ]))

        elements.append(table)

    runway = financial.get("runway_months", "N/A")
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f"Estimated Runway: {runway} months", styles["BodyStyle"]))

    viability = financial.get("viability_score", "N/A")
    elements.append(Paragraph(f"Financial Viability Score: {viability}", styles["BodyStyle"]))

    elements.append(PageBreak())

    # ===============================
    # Financial Charts
    # ===============================

    # Cost Pie Chart
    cost_chart_path = create_cost_pie(cost_data)
    if cost_chart_path:
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Image(cost_chart_path, width=4*inch, height=3*inch))

    # Runway Chart
    runway_chart_path = create_runway_chart(runway)
    if runway_chart_path:
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Image(runway_chart_path, width=4*inch, height=3*inch))

    # Viability Score Chart
    score_chart_path = create_score_chart(viability)
    if score_chart_path:
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Image(score_chart_path, width=4*inch, height=3*inch))

    # ======================================================
    # 4. COMPETITIVE ANALYSIS
    # ======================================================
    elements.append(Paragraph("Competitive Analysis", styles["Heading1Style"]))

    competitive = data.get("competitive_analysis", {})
    competitors = competitive.get("top_competitors", [])

    if competitors:
        table_data = [["Competitor", "Pricing Model"]]
        for comp in competitors[:5]:
            table_data.append([
                comp.get("name", "N/A"),
                comp.get("pricing", {}).get("model", "N/A")
            ])

        table = Table(table_data, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#144272")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        elements.append(table)

    intensity = competitive.get("competitive_intensity", "N/A")
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f"Competitive Intensity: {intensity}", styles["BodyStyle"]))

    elements.append(PageBreak())

    # ======================================================
    # 5. MARKET ANALYSIS
    # ======================================================
    elements.append(Paragraph("Market Analysis", styles["Heading1Style"]))

    market = data.get("market_analysis", {})
    market_size = market.get("market_size", {})

    if market_size:
        table_data = [
            ["Metric", "Value"],
            ["Global Market Size", f"${market_size.get('global', 0):,}"],
            ["Target Region Size", f"${market_size.get('target_region', 0):,}"],
        ]

        table = Table(table_data, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#205295")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        elements.append(table)

    growth = market.get("growth_rate", {}).get("trend", "N/A")
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f"Market Growth Trend: {growth}", styles["BodyStyle"]))

    elements.append(PageBreak())
    # ===============================
    # Market Size Chart
    # ===============================

    market_chart_path = create_market_size_chart(market_size)
    if market_chart_path:
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Image(market_chart_path, width=4*inch, height=3*inch))

    # ======================================================
    # 6. SWOT ANALYSIS
    # ======================================================
    elements.append(Paragraph("SWOT Analysis", styles["Heading1Style"]))

    swot = competitive.get("swot_analysis", {})

    for key in ["strengths", "weaknesses", "opportunities", "threats"]:
        elements.append(Paragraph(key.capitalize(), styles["Heading2Style"]))
        for item in swot.get(key, []):
            elements.append(Paragraph(f"• {item}", styles["BulletStyle"]))

    elements.append(PageBreak())

    # ======================================================
    # 7. RECOMMENDATIONS & RISKS
    # ======================================================
    elements.append(Paragraph("Recommendations", styles["Heading1Style"]))

    for rec in data.get("recommendations", []):
        elements.append(Paragraph(f"• {rec}", styles["BulletStyle"]))

    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph("Key Risks", styles["Heading2Style"]))

    for risk in data.get("risks", []):
        elements.append(Paragraph(f"• {risk}", styles["BulletStyle"]))

    elements.append(PageBreak())

    # ======================================================
    # 8. NEXT STEPS
    # ======================================================
    elements.append(Paragraph("Next Steps", styles["Heading1Style"]))

    for step in data.get("next_steps", []):
        elements.append(Paragraph(f"• {step}", styles["BulletStyle"]))

    return elements