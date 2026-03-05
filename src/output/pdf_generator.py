"""
pdf_generator.py  –  Phase 11 Enhanced PDF Report Generator

Key fixes vs. previous version:
  1. PDFGenerator is now a CLASS (was a bare function) — fixes ImportError in report_generator.py
  2. Reads from the MAPPED data schema (title_page, executive_summary, score_overview,
     domain_scores, risk_analysis, recommendations, decision) — not the raw consolidated JSON
  3. Adds rule-based NLG narrative paragraphs for Financial, Market, and Competitive sections
  4. Adds charts inline using matplotlib via ChartBuilder
  5. Proper ReportLab Platypus flow with header/footer via layout_engine
"""

import os
from datetime import datetime
from pathlib import Path

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, Image, HRFlowable
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4

from src.output.style_manager import get_styles
from src.output.chart_builder import ChartBuilder
from src.output.layout_engine import build_pdf
from src.orchestration.logger import setup_logger

logger = setup_logger()

OUTPUT_DIR = Path("reports")


# ==============================================================
# NLG NARRATIVE ENGINE  (rule-based, zero-cost)
# ==============================================================

def _nlg_financial(domain_scores, score_overview):
    """Generate a plain-English paragraph about financial health."""
    fscore = domain_scores.get("financial_score", 0)
    overall = score_overview.get("overall_score", 0)
    rating = score_overview.get("rating", "Moderate")

    if fscore >= 0.7:
        outlook = "strong financial foundations"
        advice = "The business is well-positioned to scale operations."
    elif fscore >= 0.5:
        outlook = "moderate financial health"
        advice = "Careful cost management and phased investment are recommended."
    else:
        outlook = "financial challenges that require immediate attention"
        advice = "A revised cost structure and additional funding should be explored before committing capital."

    return (
        f"The financial assessment reveals {outlook}, with a domain score of "
        f"{fscore:.0%}. The overall viability rating is <b>{rating}</b> "
        f"(score: {overall:.0%}). {advice}"
    )


def _nlg_competitive(domain_scores):
    """Generate a plain-English paragraph about competitive position."""
    cscore = domain_scores.get("competitive_score", 0)

    if cscore >= 0.7:
        intensity_label = "low"
        narrative = (
            "The market shows limited rivalry, presenting a strong window "
            "to capture early market share before saturation occurs."
        )
    elif cscore >= 0.5:
        intensity_label = "moderate"
        narrative = (
            "The competitive landscape offers room for differentiation. "
            "A focused niche strategy or superior user experience can yield "
            "a defensible market position."
        )
    else:
        intensity_label = "high"
        narrative = (
            "The market is highly contested. Entry requires a clearly differentiated "
            "value proposition, aggressive pricing, or a partnership strategy to "
            "overcome established incumbents."
        )

    return (
        f"Competitive intensity is classified as <b>{intensity_label}</b> "
        f"(competitive score: {cscore:.0%}). {narrative}"
    )


def _nlg_market(domain_scores):
    """Generate a plain-English paragraph about market opportunity."""
    mscore = domain_scores.get("market_score", 0)

    if mscore >= 0.7:
        label = "highly attractive"
        narrative = (
            "Market signals indicate strong growth potential and positive industry sentiment, "
            "suggesting favourable conditions for entry and scale."
        )
    elif mscore >= 0.5:
        label = "moderately attractive"
        narrative = (
            "Market conditions are promising but warrant further validation. "
            "Focused go-to-market experiments are advised before full-scale launch."
        )
    else:
        label = "limited"
        narrative = (
            "Current market signals are weak or mixed. "
            "The business concept may benefit from pivoting to an adjacent segment "
            "with stronger demand characteristics."
        )

    return (
        f"The market opportunity is assessed as <b>{label}</b> "
        f"(market score: {mscore:.0%}). {narrative}"
    )


def _nlg_risks(risks):
    """Summarise risk flags into a short narrative."""
    if not risks:
        return "No significant risk flags were identified during this assessment."

    high = [r for r in risks if r.get("severity") == "High"]
    med  = [r for r in risks if r.get("severity") == "Medium"]

    parts = []
    if high:
        parts.append(f"{len(high)} high-severity risk(s) demand immediate mitigation")
    if med:
        parts.append(f"{len(med)} medium-severity risk(s) require monitoring")

    return (
        "Risk aggregation identified " + " and ".join(parts) + ". "
        "Refer to the risk table below for specific details and recommended actions."
    )


# ==============================================================
# SECTION BUILDERS
# ==============================================================

def _build_title_page(elements, mapped_data, styles):
    title_data = mapped_data.get("title_page", {})
    elements.append(Spacer(1, 1.0 * inch))

    # Brand-colored banner
    banner_data = [[""]]
    banner = Table(
        banner_data,
        colWidths=[6 * inch],
        rowHeights=[0.6 * inch],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1F3C88")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#0A2647")),
    ]))
    elements.append(banner)
    elements.append(Spacer(1, 0.4 * inch))

    title_para = Paragraph(
        title_data.get("project_title", "AutoResearch Report"),
        styles["TitleStyle"],
    )
    elements.append(title_para)
    elements.append(Spacer(1, 0.3 * inch))

    elements.append(Paragraph(
        f"Generated: {title_data.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M'))}",
        styles["ItalicStyle"]
    ))
    elements.append(PageBreak())


def _build_executive_summary(elements, mapped_data, styles):
    heading = Paragraph("Executive Summary", styles["Heading1Style"])
    heading.outlineLevel = 0
    elements.append(heading)
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 0.1 * inch))

    summary = mapped_data.get("executive_summary", {}).get("summary_text", "No summary available.")
    score_data = mapped_data.get("score_overview", {})
    domain_data = mapped_data.get("domain_scores", {})
    decision = mapped_data.get("decision", {}).get("final_decision", "—")
    confidence = mapped_data.get("data_confidence", {})

    metrics_lines = [
        f"<b>Overall score:</b> {score_data.get('overall_score', 0):.0%} ({score_data.get('rating', '—')})",
        f"<b>Financial:</b> {domain_data.get('financial_score', 0):.0%}",
        f"<b>Market:</b> {domain_data.get('market_score', 0):.0%}",
        f"<b>Competitive:</b> {domain_data.get('competitive_score', 0):.0%}",
        f"<b>Decision:</b> {decision}",
        f"<b>Data confidence:</b> {confidence.get('overall', 'Medium')}",
    ]
    metrics_html = "<br/>".join(metrics_lines)

    metrics_cell = Paragraph(metrics_html, styles["BodyStyle"])
    summary_cell = Paragraph(summary, styles["BodyStyle"])

    table = Table(
        [[metrics_cell, summary_cell]],
        colWidths=[2.5 * inch, 3.3 * inch],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F4F8FF")),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    elements.append(PageBreak())


def _build_table_of_contents(elements, styles):
    heading = Paragraph("Contents", styles["Heading1Style"])
    heading.outlineLevel = 0
    elements.append(heading)
    elements.append(Spacer(1, 0.15 * inch))

    toc = TableOfContents()
    toc.levelStyles = [
        styles["TOCLevel1Style"],
        styles["TOCLevel2Style"],
    ]
    elements.append(toc)
    elements.append(PageBreak())


def _build_score_overview(elements, mapped_data, styles, chart_builder):
    score_data = mapped_data.get("score_overview", {})
    domain_data = mapped_data.get("domain_scores", {})

    heading = Paragraph("Viability Score Overview", styles["Heading1Style"])
    heading.outlineLevel = 0
    elements.append(heading)
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 0.15 * inch))

    overall = score_data.get("overall_score", 0)
    rating  = score_data.get("rating", "—")

    # Summary table
    score_table_data = [
        ["Dimension", "Score", "Rating"],
        ["Overall Viability", f"{overall:.0%}", rating],
        ["Financial",         f"{domain_data.get('financial_score', 0):.0%}", ""],
        ["Market",            f"{domain_data.get('market_score', 0):.0%}",    ""],
        ["Competitive",       f"{domain_data.get('competitive_score', 0):.0%}", ""],
    ]

    tbl = Table(score_table_data, colWidths=[3 * inch, 1.5 * inch, 1.5 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#1F3C88")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("ALIGN",        (1, 0), (-1, -1), "CENTER"),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F8FF")]),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.2 * inch))

    # Data confidence caveat
    confidence = mapped_data.get("data_confidence", {})
    overall_conf = confidence.get("overall", "Medium")
    conf_text = f"Overall data confidence: <b>{overall_conf}</b>."
    if overall_conf in ("Low", "Medium"):
        conf_text += " Interpret this assessment with caution as some domains have limited data coverage."
    elements.append(Paragraph(conf_text, styles["BodyStyle"]))
    elements.append(Spacer(1, 0.2 * inch))

    # Domain score bar chart
    chart_path = chart_builder.build_domain_score_chart(mapped_data)
    if chart_path and os.path.exists(chart_path):
        elements.append(Image(chart_path, width=4.5 * inch, height=3 * inch))

    elements.append(PageBreak())


def _build_financial_section(elements, mapped_data, styles, chart_builder):
    domain_data  = mapped_data.get("domain_scores", {})
    score_data   = mapped_data.get("score_overview", {})
    fin_details  = mapped_data.get("financial_details", {})

    heading = Paragraph("Financial Analysis", styles["Heading1Style"])
    heading.outlineLevel = 0
    elements.append(heading)
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 0.15 * inch))

    # NLG narrative
    narrative = _nlg_financial(domain_data, score_data)
    elements.append(Paragraph(narrative, styles["BodyStyle"]))
    elements.append(Spacer(1, 0.2 * inch))

    # Metrics table
    fscore = domain_data.get("financial_score", 0)
    runway = fin_details.get("runway_months", 0)
    monthly_burn = fin_details.get("monthly_burn", 0)
    est_revenue = fin_details.get("estimated_revenue", 0)
    fin_growth = fin_details.get("growth_rate", 0)
    margin = fin_details.get("profit_margin", 0)

    fin_table_data = [
        ["Metric",                    "Value"],
        ["Financial Viability Score", f"{fscore:.0%}"],
        ["Score Interpretation",
         "Strong" if fscore >= 0.7 else ("Moderate" if fscore >= 0.5 else "Weak")],
        ["Runway (months)",           f"{runway:.1f}"],
        ["Monthly burn (USD)",        f"{monthly_burn:,.0f}"],
        ["Estimated revenue (USD)",   f"{est_revenue:,.0f}"],
        ["Growth rate (%)",           f"{fin_growth:.1f}"],
        ["Estimated profit margin (%)", f"{margin:.1f}"],
    ]
    tbl = Table(fin_table_data, colWidths=[3.5 * inch, 2.5 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#0A2647")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F8FF")]),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.3 * inch))

    # Overall score horizontal chart
    chart_path = chart_builder.build_overall_score_chart(mapped_data)
    if chart_path and os.path.exists(chart_path):
        elements.append(Image(chart_path, width=4.5 * inch, height=2.5 * inch))

    elements.append(PageBreak())


def _build_market_section(elements, mapped_data, styles):
    domain_data = mapped_data.get("domain_scores", {})
    mkt_details = mapped_data.get("market_details", {})

    heading = Paragraph("Market Analysis", styles["Heading1Style"])
    heading.outlineLevel = 0
    elements.append(heading)
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 0.15 * inch))

    # NLG narrative
    narrative = _nlg_market(domain_data)
    elements.append(Paragraph(narrative, styles["BodyStyle"]))
    elements.append(Spacer(1, 0.2 * inch))

    mscore = domain_data.get("market_score", 0)
    tam = mkt_details.get("tam", 0)
    sam = mkt_details.get("sam", 0)
    som = mkt_details.get("som", 0)
    currency = mkt_details.get("tam_currency", "USD")
    growth = mkt_details.get("growth_rate", 0)
    sent_label = mkt_details.get("sentiment_label", "Neutral")
    sent_score = mkt_details.get("sentiment_score", 0)
    mkt_table_data = [
        ["Metric",                 "Value"],
        ["Market Score",           f"{mscore:.0%}"],
        ["Opportunity Level",
         "High" if mscore >= 0.7 else ("Medium" if mscore >= 0.5 else "Low")],
        ["TAM",                    f"{tam:,.0f} {currency}"],
        ["SAM",                    f"{sam:,.0f} {currency}"],
        ["SOM",                    f"{som:,.0f} {currency}"],
        ["Growth rate (%)",        f"{growth:.1f}"],
        ["Sentiment",              f"{sent_label} ({sent_score:+.2f})"],
    ]
    tbl = Table(mkt_table_data, colWidths=[3.5 * inch, 2.5 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#205295")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F8FF")]),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.2 * inch))

    # Key insights
    insights = mkt_details.get("key_insights", [])
    if insights:
        elements.append(Paragraph("Key market insights:", styles["Heading2Style"]))
        for ins in insights:
            elements.append(Paragraph(f"&#8226; {ins}", styles["BulletStyle"]))

    elements.append(PageBreak())


def _build_competitive_section(elements, mapped_data, styles):
    domain_data = mapped_data.get("domain_scores", {})
    comp_details = mapped_data.get("competitive_details", {})

    heading = Paragraph("Competitive Analysis", styles["Heading1Style"])
    heading.outlineLevel = 0
    elements.append(heading)
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 0.15 * inch))

    narrative = _nlg_competitive(domain_data)
    elements.append(Paragraph(narrative, styles["BodyStyle"]))
    elements.append(Spacer(1, 0.2 * inch))

    cscore = domain_data.get("competitive_score", 0)
    competitors_found = comp_details.get("competitors_found", 0)
    top_competitors = comp_details.get("top_competitors", [])
    intensity = comp_details.get("competitive_intensity", "Unknown")
    comp_table_data = [
        ["Metric",                    "Value"],
        ["Competitive Score",         f"{cscore:.0%}"],
        ["Market Saturation",
         "Low" if cscore >= 0.7 else ("Medium" if cscore >= 0.5 else "High")],
        ["Competitors found",         str(competitors_found)],
        ["Intensity classification",  intensity],
    ]
    tbl = Table(comp_table_data, colWidths=[3.5 * inch, 2.5 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#144272")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F8FF")]),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.2 * inch))

    # Top competitors
    if top_competitors:
        elements.append(Paragraph("Top competitors:", styles["Heading2Style"]))
        for name in top_competitors:
            elements.append(Paragraph(f"&#8226; {name}", styles["BulletStyle"]))
        elements.append(Spacer(1, 0.15 * inch))

    # SWOT matrix
    swot = comp_details.get("swot", {})
    swot_table_data = [
        ["Strengths", "Weaknesses"],
        [
            "<br/>".join(swot.get("strengths", []) or ["—"]),
            "<br/>".join(swot.get("weaknesses", []) or ["—"]),
        ],
        ["Opportunities", "Threats"],
        [
            "<br/>".join(swot.get("opportunities", []) or ["—"]),
            "<br/>".join(swot.get("threats", []) or ["—"]),
        ],
    ]
    swot_tbl = Table(swot_table_data, colWidths=[3 * inch, 3 * inch])
    swot_tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F4F8FF")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F4F8FF")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(swot_tbl)
    elements.append(Spacer(1, 0.2 * inch))

    # Market gaps
    gaps = comp_details.get("market_gaps", [])
    if gaps:
        elements.append(Paragraph("Observed market gaps:", styles["Heading2Style"]))
        for gap in gaps:
            elements.append(Paragraph(f"&#8226; {gap}", styles["BulletStyle"]))

    elements.append(PageBreak())


def _build_risk_section(elements, mapped_data, styles):
    risk_data = mapped_data.get("risk_analysis", {})
    risks = risk_data.get("risks", [])

    heading = Paragraph("Risk Analysis", styles["Heading1Style"])
    heading.outlineLevel = 0
    elements.append(heading)
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 0.15 * inch))

    # NLG narrative
    narrative = _nlg_risks(risks)
    elements.append(Paragraph(narrative, styles["BodyStyle"]))
    elements.append(Spacer(1, 0.2 * inch))

    if risks:
        risk_table_data = [["Category", "Severity", "Description"]]
        for r in risks:
            sev = r.get("severity", "Medium")
            risk_table_data.append([
                r.get("category", "—"),
                sev,
                r.get("message", "—")
            ])

        sev_colors = {"High": colors.HexColor("#FFDADA"), "Medium": colors.HexColor("#FFF4CC"), "Low": colors.HexColor("#DAFFD4")}

        tbl = Table(risk_table_data, colWidths=[1.5 * inch, 1.2 * inch, 3.8 * inch])
        style_cmds = [
            ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#2C3E50")),
            ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("GRID",         (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("FONTSIZE",     (0, 0), (-1, -1), 10),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ]
        for i, r in enumerate(risks, start=1):
            sev = r.get("severity", "Medium")
            bg  = sev_colors.get(sev, colors.white)
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

        tbl.setStyle(TableStyle(style_cmds))
        elements.append(tbl)

    elements.append(PageBreak())


def _build_recommendations_decision(elements, mapped_data, styles):
    rec_data  = mapped_data.get("recommendations", {})
    dec_data  = mapped_data.get("decision", {})

    heading = Paragraph("Recommendations &amp; Decision", styles["Heading1Style"])
    heading.outlineLevel = 0
    elements.append(heading)
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 0.15 * inch))

    # Recommendations as priority-coloured table
    raw_recs = rec_data.get("recommendations", [])
    if raw_recs:
        rec_rows = [["Action", "Priority"]]
        for rec in raw_recs:
            text = str(rec)
            priority = "Medium"
            lowered = text.lower()
            if "immediate" in lowered or "aggressively" in lowered:
                priority = "High"
            elif "caution" in lowered or "phased" in lowered:
                priority = "Medium"
            elif "monitor" in lowered:
                priority = "Low"
            rec_rows.append([text, priority])

        rec_tbl = Table(rec_rows, colWidths=[4.2 * inch, 1.8 * inch])
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        for i in range(1, len(rec_rows)):
            prio = rec_rows[i][1]
            if prio == "High":
                bg = colors.HexColor("#FFDADA")
            elif prio == "Medium":
                bg = colors.HexColor("#FFF4CC")
            else:
                bg = colors.HexColor("#DAFFD4")
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

        rec_tbl.setStyle(TableStyle(style_cmds))
        elements.append(rec_tbl)

    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph("Final Decision", styles["Heading2Style"]))

    decision = dec_data.get("final_decision", "—")
    decision_color = {
        "Proceed": colors.HexColor("#2ECC71"),
        "Proceed with Caution": colors.HexColor("#F39C12"),
        "Re-evaluate": colors.HexColor("#E74C3C"),
    }.get(decision, colors.grey)

    dec_tbl = Table([[decision]], colWidths=[6 * inch])
    dec_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), decision_color),
        ("TEXTCOLOR",     (0, 0), (-1, -1), colors.white),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 14),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    elements.append(dec_tbl)

    # Decision rationale
    score_data = mapped_data.get("score_overview", {})
    confidence = mapped_data.get("data_confidence", {})
    risk_data = mapped_data.get("risk_analysis", {})
    risks = risk_data.get("risks", [])

    rationale_parts = [
        f"The decision is based on an overall viability score of {score_data.get('overall_score', 0):.0%}",
        f"with overall data confidence rated as {confidence.get('overall', 'Medium')}.",
    ]
    if risks:
        rationale_parts.append(f"{len(risks)} consolidated risk item(s) were identified across financial, market, and competitive domains.")

    rationale_text = " ".join(rationale_parts)
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(rationale_text, styles["BodyStyle"]))


def _build_data_sources_section(elements, mapped_data, styles):
    sources = mapped_data.get("sources", [])
    if not sources:
        return

    heading = Paragraph("Appendix: Data Sources", styles["Heading1Style"])
    heading.outlineLevel = 0
    elements.append(heading)
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 0.15 * inch))

    table_data = [["Title", "URL"]]
    for src in sources:
        title = src.get("title", "") or src.get("url", "")
        url = src.get("url", "")
        table_data.append([title, url])

    tbl = Table(table_data, colWidths=[3 * inch, 3 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3C88")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(tbl)


# ==============================================================
# PDFGenerator CLASS  (fixes ImportError — was a bare function)
# ==============================================================

class PDFGenerator:
    """
    Generates a structured, NLG-enhanced PDF report from mapped report data.

    Usage:
        generator = PDFGenerator()
        generator.generate(mapped_data, output_path)
    """

    def __init__(self, output_dir="reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.chart_builder = ChartBuilder()

    def generate(self, mapped_data: dict, file_path=None) -> str:
        """
        Build the full PDF report.

        Args:
            mapped_data (dict): Output from ReportDataMapper.map()
            file_path (Path|str|None): Target path; auto-generated if None

        Returns:
            str: Path to the generated PDF
        """
        if not mapped_data:
            raise ValueError("mapped_data is empty — cannot generate PDF.")

        if file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = self.output_dir / f"final_report_{timestamp}.pdf"

        file_path = str(file_path)
        styles = get_styles()
        elements = []

        try:
            # Section 0: Title page
            _build_title_page(elements, mapped_data, styles)

            # Section 1: Table of contents
            _build_table_of_contents(elements, styles)

            # Section 2: Executive summary
            _build_executive_summary(elements, mapped_data, styles)

            # Section 3: Score overview (with domain chart)
            _build_score_overview(elements, mapped_data, styles, self.chart_builder)

            # Section 4: Financial Analysis + NLG
            _build_financial_section(elements, mapped_data, styles, self.chart_builder)

            # Section 5: Market Analysis + NLG
            _build_market_section(elements, mapped_data, styles)

            # Section 6: Competitive Analysis + NLG
            _build_competitive_section(elements, mapped_data, styles)

            # Section 7: Risk Analysis
            _build_risk_section(elements, mapped_data, styles)

            # Section 8: Recommendations + Decision
            _build_recommendations_decision(elements, mapped_data, styles)

            # Section 9: Appendix – Data Sources
            _build_data_sources_section(elements, mapped_data, styles)

            build_pdf(file_path, elements)
            logger.info(f"PDF generated: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise RuntimeError(f"PDF generation failed: {e}") from e
        finally:
            self.chart_builder.clear_temp_charts()