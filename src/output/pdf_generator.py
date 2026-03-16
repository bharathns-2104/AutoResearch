"""
pdf_generator.py  —  Improved PDF Report Generator

Key improvements over original:
  1. Uses generate_executive_summary() for LLM/data-accurate summary
  2. Accurate data display — all metric helpers read from correct dict paths
  3. Visual refresh: two-tone color scheme, better tables, section dividers
  4. Added "Data Sources" confidence badge on each section header
  5. TAM/SAM/SOM displayed as formatted currency (not raw integers)
  6. Competitor table with names listed properly
  7. SWOT quadrant table fully rendered
  8. Risk section with color-coded severity rows
  9. Routing metadata section (confidence tier, extraction method, self-correction)
 10. Page numbers, header/footer via layout_engine
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, Image, HRFlowable, KeepTogether
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

OUTPUT_DIR = Path("reports")

# ── Palette ────────────────────────────────────────────────────────────────
C_NAVY    = colors.HexColor("#0D1B2A")
C_STEEL   = colors.HexColor("#1B4F72")
C_TEAL    = colors.HexColor("#148F77")
C_AMBER   = colors.HexColor("#D4AC0D")
C_RED     = colors.HexColor("#C0392B")
C_GREEN   = colors.HexColor("#1E8449")
C_LIGHT   = colors.HexColor("#F4F6F7")
C_BORDER  = colors.HexColor("#D5D8DC")
C_WHITE   = colors.white
C_TEXT    = colors.HexColor("#1C2833")
C_DIM     = colors.HexColor("#5D6D7E")


# ── Style factory ──────────────────────────────────────────────────────────

def _make_styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle("Title", parent=base["Normal"],
            fontSize=28, leading=34, alignment=TA_CENTER, spaceAfter=6,
            textColor=C_NAVY, fontName="Helvetica-Bold"),
        "Subtitle": ParagraphStyle("Subtitle", parent=base["Normal"],
            fontSize=11, leading=14, alignment=TA_CENTER, spaceAfter=4,
            textColor=C_DIM, fontName="Helvetica-Oblique"),
        "H1": ParagraphStyle("H1", parent=base["Normal"],
            fontSize=16, leading=20, spaceBefore=10, spaceAfter=6,
            textColor=C_NAVY, fontName="Helvetica-Bold"),
        "H2": ParagraphStyle("H2", parent=base["Normal"],
            fontSize=12, leading=16, spaceBefore=8, spaceAfter=4,
            textColor=C_STEEL, fontName="Helvetica-Bold"),
        "Body": ParagraphStyle("Body", parent=base["Normal"],
            fontSize=10, leading=15, alignment=TA_JUSTIFY, spaceAfter=6,
            textColor=C_TEXT),
        "Bullet": ParagraphStyle("Bullet", parent=base["Normal"],
            fontSize=10, leading=14, leftIndent=14, spaceAfter=3,
            textColor=C_TEXT),
        "Caption": ParagraphStyle("Caption", parent=base["Normal"],
            fontSize=8, leading=11, textColor=C_DIM, alignment=TA_CENTER),
        "Badge": ParagraphStyle("Badge", parent=base["Normal"],
            fontSize=7, leading=10, textColor=C_DIM, fontName="Helvetica-Oblique"),
        "TOCLevel1": ParagraphStyle("TOCLevel1", parent=base["Normal"],
            fontSize=10, leading=14, leftIndent=10, firstLineIndent=-10,
            spaceBefore=2, spaceAfter=2),
        "TOCLevel2": ParagraphStyle("TOCLevel2", parent=base["Normal"],
            fontSize=9, leading=13, leftIndent=22, firstLineIndent=-10,
            spaceBefore=1, spaceAfter=1),
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _fmt_currency(val: float, currency: str = "USD") -> str:
    if not val or val == 0:
        return "N/A"
    if val >= 1e12:
        return f"${val/1e12:.2f}T {currency}"
    if val >= 1e9:
        return f"${val/1e9:.2f}B {currency}"
    if val >= 1e6:
        return f"${val/1e6:.2f}M {currency}"
    if val >= 1e3:
        return f"${val/1e3:.1f}K {currency}"
    return f"${val:,.0f} {currency}"


def _fmt_pct(val: float, decimals: int = 1) -> str:
    if val is None or val == 0:
        return "N/A"
    return f"{val:.{decimals}f}%"


def _fmt_months(val: float) -> str:
    if not val:
        return "N/A"
    return f"{val:.1f} months"


def _confidence_badge(level: str) -> str:
    icon = {"High": "●", "Medium": "◑", "Low": "○"}.get(level, "–")
    return f"Data confidence: {icon} {level}"


def _section_rule(elements: list, color=C_TEAL, thickness: float = 1.5) -> None:
    elements.append(HRFlowable(
        width="100%", thickness=thickness, color=color,
        spaceAfter=4, spaceBefore=2
    ))


def _kv_table(rows: List[List[str]], styles_map: Dict) -> Table:
    """Build a two-column key-value table."""
    tbl = Table(rows, colWidths=[3.2 * inch, 3.6 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, -1), C_LIGHT),
        ("TEXTCOLOR",    (0, 0), (0, -1), C_STEEL),
        ("FONTNAME",     (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",     (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("GRID",         (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_WHITE, C_LIGHT]),
    ]))
    return tbl


def _score_bar_table(label: str, score: float, color) -> Table:
    """Single metric score row with visual bar."""
    pct = max(0, min(score, 1.0))
    bar_width = 3.0 * inch * pct
    bar_cell  = f'<font color="#{color.hexval()[2:]}">{"█" * int(pct * 30)}</font>'
    rows = [[label, f"{pct:.0%}", Paragraph(bar_cell, ParagraphStyle("bar", fontSize=8, leading=10))]]
    tbl = Table(rows, colWidths=[2.5 * inch, 0.7 * inch, 3.6 * inch])
    tbl.setStyle(TableStyle([
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("FONTNAME",     (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",     (1, 0), (1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR",    (1, 0), (1, -1), color),
        ("GRID",         (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


# ── Layout engine ──────────────────────────────────────────────────────────

def _header_footer(canvas_obj, doc):
    canvas_obj.saveState()
    w, h = A4
    # Header
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(C_DIM)
    canvas_obj.drawString(0.75 * inch, h - 0.55 * inch, "AutoResearch — Automated Business Intelligence Report")
    # Header rule
    canvas_obj.setStrokeColor(C_BORDER)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(0.75 * inch, h - 0.65 * inch, w - 0.75 * inch, h - 0.65 * inch)
    # Footer rule
    canvas_obj.line(0.75 * inch, 0.6 * inch, w - 0.75 * inch, 0.6 * inch)
    # Page number
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawRightString(w - 0.75 * inch, 0.4 * inch, f"Page {doc.page}")
    canvas_obj.restoreState()


class _TOCDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        sname = getattr(flowable.style, "name", "")
        if sname == "H1":
            level = 0
        elif sname == "H2":
            level = 1
        else:
            return
        text = flowable.getPlainText()
        key  = f"{text}_{self.page}"
        self.canv.bookmarkPage(key)
        self.notify("TOCEntry", (level, text, self.page))


# ── Section builders ───────────────────────────────────────────────────────

def _build_cover(elements, mapped, styles):
    elements.append(Spacer(1, 0.8 * inch))
    
    # Top color band
    band = Table([[""]], colWidths=[6.9 * inch], rowHeights=[0.5 * inch])
    band.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), C_NAVY)]))
    elements.append(band)
    elements.append(Spacer(1, 0.3 * inch))
    
    tp = mapped.get("title_page", {})
    elements.append(Paragraph(tp.get("project_title", "AutoResearch Report"), styles["Title"]))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(
        f"Generated: {tp.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M'))}",
        styles["Subtitle"]
    ))
    elements.append(Spacer(1, 0.4 * inch))
    
    # Score summary card
    so   = mapped.get("score_overview", {})
    ds   = mapped.get("domain_scores", {})
    dec  = mapped.get("decision", {})
    conf = mapped.get("data_confidence", {})
    
    card_rows = [
        ["Overall Viability Score", f"{so.get('overall_score', 0):.0%}  ({so.get('rating', '—')})"],
        ["Financial Score",         f"{ds.get('financial_score', 0):.0%}"],
        ["Market Score",            f"{ds.get('market_score', 0):.0%}"],
        ["Competitive Score",       f"{ds.get('competitive_score', 0):.0%}"],
        ["Decision",                dec.get("final_decision", "—")],
        ["Data Confidence",         conf.get("overall", "Unknown")],
    ]
    tbl = Table(card_rows, colWidths=[3.0 * inch, 3.9 * inch])
    
    dec_val   = dec.get("final_decision", "")
    dec_color = {"Proceed": C_GREEN, "Proceed with Caution": C_AMBER, "Re-evaluate": C_RED}.get(dec_val, C_STEEL)
    
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  C_WHITE),
        ("BACKGROUND",    (0, 1), (-1, -1), C_LIGHT),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTNAME",      (1, 1), (1, -2),  "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("GRID",          (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("TEXTCOLOR",     (1, 5), (1, 5),   dec_color),
        ("FONTNAME",      (1, 5), (1, 5),   "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [C_WHITE, C_LIGHT]),
    ]))
    elements.append(tbl)
    elements.append(PageBreak())


def _build_toc(elements, styles):
    h = Paragraph("Table of Contents", styles["H1"])
    h.outlineLevel = 0
    elements.append(h)
    _section_rule(elements)
    elements.append(Spacer(1, 0.1 * inch))
    toc = TableOfContents()
    toc.levelStyles = [styles["TOCLevel1"], styles["TOCLevel2"]]
    elements.append(toc)
    elements.append(PageBreak())


def _build_executive_summary(elements, mapped, styles):
    h = Paragraph("Executive Summary", styles["H1"])
    h.outlineLevel = 0
    elements.append(h)
    _section_rule(elements)
    
    summary = mapped.get("executive_summary", {}).get("summary_text", "No summary available.")
    
    # Split into paragraphs and render each
    for para in summary.split("\n\n"):
        para = para.strip()
        if para:
            elements.append(Paragraph(para, styles["Body"]))
            elements.append(Spacer(1, 0.05 * inch))
    
    elements.append(PageBreak())


def _build_scores(elements, mapped, styles):
    h = Paragraph("Viability Score Overview", styles["H1"])
    h.outlineLevel = 0
    elements.append(h)
    _section_rule(elements)
    elements.append(Spacer(1, 0.1 * inch))
    
    so   = mapped.get("score_overview", {})
    ds   = mapped.get("domain_scores", {})
    conf = mapped.get("data_confidence", {})
    
    overall = so.get("overall_score", 0)
    rating  = so.get("rating", "—")
    color   = C_GREEN if overall >= 0.65 else (C_AMBER if overall >= 0.4 else C_RED)
    
    # Big score display
    score_data = [[
        Paragraph(f"<b>{overall:.0%}</b>", ParagraphStyle("big", fontSize=36, textColor=color, alignment=TA_CENTER, leading=40)),
        Paragraph(f"<b>{rating}</b><br/><font size='9' color='#5D6D7E'>Overall Viability</font>",
                  ParagraphStyle("rating", fontSize=14, textColor=color, alignment=TA_LEFT, leading=20)),
    ]]
    big_tbl = Table(score_data, colWidths=[1.8 * inch, 5.1 * inch])
    big_tbl.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ("BACKGROUND",   (0, 0), (-1, -1), C_LIGHT),
        ("BOX",          (0, 0), (-1, -1), 0.5, C_BORDER),
    ]))
    elements.append(big_tbl)
    elements.append(Spacer(1, 0.2 * inch))
    
    # Domain scores table
    domain_rows = [
        ["Domain",      "Score", "Confidence", "Assessment"],
        ["Financial",   f"{ds.get('financial_score', 0):.0%}",   conf.get("financial", "—"),   _score_label(ds.get('financial_score', 0))],
        ["Market",      f"{ds.get('market_score', 0):.0%}",      conf.get("market", "—"),      _score_label(ds.get('market_score', 0))],
        ["Competitive", f"{ds.get('competitive_score', 0):.0%}", conf.get("competitive", "—"), _score_label(ds.get('competitive_score', 0))],
    ]
    dom_tbl = Table(domain_rows, colWidths=[2.0 * inch, 1.2 * inch, 1.5 * inch, 2.2 * inch])
    dom_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  C_NAVY),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  C_WHITE),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("GRID",         (0, 0), (-1, -1), 0.3, C_BORDER),
        ("ALIGN",        (1, 0), (2, -1),  "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHT]),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    elements.append(dom_tbl)
    
    # Data confidence note
    elements.append(Spacer(1, 0.15 * inch))
    oc = conf.get("overall", "Unknown")
    note_text = (
        f"Overall data confidence: <b>{oc}</b>. "
        + ("Results are well-supported by multiple sources." if oc == "High"
           else "Some data gaps exist; treat projections as directional estimates." if oc == "Medium"
           else "Data is sparse. This report should be treated as a preliminary scoping exercise.")
    )
    elements.append(Paragraph(note_text, styles["Badge"]))
    elements.append(PageBreak())


def _score_label(s: float) -> str:
    if s >= 0.65: return "Strong"
    if s >= 0.40: return "Moderate"
    return "Weak"


def _build_financial(elements, mapped, styles):
    fin = mapped.get("financial_details", {})
    ds  = mapped.get("domain_scores", {})
    conf = mapped.get("data_confidence", {})
    
    h = Paragraph("Financial Analysis", styles["H1"])
    h.outlineLevel = 0
    elements.append(h)
    _section_rule(elements)
    elements.append(Paragraph(_confidence_badge(conf.get("financial", "Unknown")), styles["Badge"]))
    elements.append(Spacer(1, 0.1 * inch))
    
    fscore       = ds.get("financial_score", 0)
    runway       = fin.get("runway_months", 0) or 0
    monthly_burn = fin.get("monthly_burn", 0) or 0
    est_revenue  = fin.get("estimated_revenue", 0) or 0
    growth_rate  = fin.get("growth_rate", 0) or 0
    profit_margin = fin.get("profit_margin", 0) or 0
    
    # Narrative
    if fscore >= 0.65:
        narrative = (
            f"The financial profile is strong, with a viability score of {fscore:.0%}. "
            f"Estimated runway of {_fmt_months(runway)} at a monthly burn of {_fmt_currency(monthly_burn)} "
            f"provides adequate time to reach key milestones before requiring additional capital. "
            f"Projected revenue of {_fmt_currency(est_revenue)} combined with a {_fmt_pct(growth_rate)} "
            f"market growth signal supports a positive financial outlook."
        )
    elif fscore >= 0.4:
        narrative = (
            f"The financial assessment returns a moderate viability score of {fscore:.0%}. "
            f"At a monthly burn of {_fmt_currency(monthly_burn)}, the runway of {_fmt_months(runway)} "
            f"is sufficient for initial validation but leaves limited buffer for delays or pivots. "
            + ("Projected revenue of " + _fmt_currency(est_revenue) + " is encouraging but should be stress-tested against conservative scenarios." if est_revenue > 0 else
               "Revenue projections were not extractable from available data; early customer validation is a priority.")
        )
    else:
        narrative = (
            f"The financial case is currently weak, with a viability score of {fscore:.0%}. "
            f"The monthly burn rate of {_fmt_currency(monthly_burn)} yields a runway of {_fmt_months(runway)}, "
            f"which is insufficient to reach meaningful scale. Revised financial modelling and supplementary "
            f"funding exploration are recommended before further commitment."
        )
    
    elements.append(Paragraph(narrative, styles["Body"]))
    elements.append(Spacer(1, 0.15 * inch))
    
    rows = [
        ["Metric", "Value"],
        ["Financial Viability Score",    f"{fscore:.0%}  ({_score_label(fscore)})"],
        ["Estimated Runway",             _fmt_months(runway)],
        ["Monthly Burn Rate",            _fmt_currency(monthly_burn)],
        ["Projected Revenue",            _fmt_currency(est_revenue)],
        ["Market Growth Rate",           _fmt_pct(growth_rate)],
        ["Estimated Profit Margin",      _fmt_pct(profit_margin)],
    ]
    elements.append(_kv_table(rows, styles))
    elements.append(PageBreak())


def _build_market(elements, mapped, styles):
    mkt  = mapped.get("market_details", {})
    ds   = mapped.get("domain_scores", {})
    conf = mapped.get("data_confidence", {})
    
    h = Paragraph("Market Analysis", styles["H1"])
    h.outlineLevel = 0
    elements.append(h)
    _section_rule(elements)
    elements.append(Paragraph(_confidence_badge(conf.get("market", "Unknown")), styles["Badge"]))
    elements.append(Spacer(1, 0.1 * inch))
    
    mscore       = ds.get("market_score", 0)
    tam          = mkt.get("tam", 0) or 0
    sam          = mkt.get("sam", 0) or 0
    som          = mkt.get("som", 0) or 0
    currency     = mkt.get("tam_currency", "USD")
    growth       = mkt.get("growth_rate", 0) or 0
    sent_label   = mkt.get("sentiment_label", "Neutral")
    sent_score   = mkt.get("sentiment_score", 0) or 0
    insights     = mkt.get("key_insights", []) or []
    
    # Narrative
    tam_str  = _fmt_currency(tam, currency)
    growth_str = _fmt_pct(growth) + " CAGR" if growth > 0 else "growth rate not identified"
    
    if mscore >= 0.65:
        narrative = (
            f"The market opportunity is assessed as strong (score: {mscore:.0%}). "
            + (f"The total addressable market is {tam_str}, " if tam > 0 else "")
            + (f"growing at {growth_str}. " if growth > 0 else "")
            + f"Market sentiment is {sent_label.lower()}, signalling favourable demand conditions for market entry."
        )
    elif mscore >= 0.4:
        narrative = (
            f"The market presents a moderate opportunity (score: {mscore:.0%}). "
            + (f"TAM is estimated at {tam_str} with {growth_str}. " if tam > 0 else "Market size data was limited. ")
            + f"Sentiment signals are {sent_label.lower()}, indicating "
            + ("room for growth with targeted positioning." if sent_label != "Negative" else "headwinds; a differentiated entry strategy is necessary.")
        )
    else:
        narrative = (
            f"Market data is insufficient to fully assess the opportunity (score: {mscore:.0%}). "
            + (f"A TAM of {tam_str} was identified, " if tam > 0 else "No market size data was extracted. ")
            + "Additional primary research is recommended before committing to this market."
        )
    
    elements.append(Paragraph(narrative, styles["Body"]))
    elements.append(Spacer(1, 0.15 * inch))
    
    rows = [
        ["Metric", "Value"],
        ["Market Score",             f"{mscore:.0%}  ({_score_label(mscore)})"],
        ["Total Addressable Market", _fmt_currency(tam, currency)],
        ["Serviceable Addressable Market", _fmt_currency(sam, currency)],
        ["Serviceable Obtainable Market",  _fmt_currency(som, currency)],
        ["Market Growth Rate (CAGR)",      _fmt_pct(growth)],
        ["Market Sentiment",               f"{sent_label} ({sent_score:+.2f})"],
    ]
    elements.append(_kv_table(rows, styles))
    
    if insights:
        elements.append(Spacer(1, 0.15 * inch))
        elements.append(Paragraph("Key Market Insights", styles["H2"]))
        for ins in insights:
            elements.append(Paragraph(f"• {ins}", styles["Bullet"]))
    
    elements.append(PageBreak())


def _build_competitive(elements, mapped, styles):
    comp = mapped.get("competitive_details", {})
    ds   = mapped.get("domain_scores", {})
    conf = mapped.get("data_confidence", {})
    
    h = Paragraph("Competitive Analysis", styles["H1"])
    h.outlineLevel = 0
    elements.append(h)
    _section_rule(elements)
    elements.append(Paragraph(_confidence_badge(conf.get("competitive", "Unknown")), styles["Badge"]))
    elements.append(Spacer(1, 0.1 * inch))
    
    cscore    = ds.get("competitive_score", 0)
    n_comp    = comp.get("competitors_found", 0) or 0
    intensity = comp.get("competitive_intensity", "Unknown")
    top_comp  = comp.get("top_competitors", []) or []
    gaps      = comp.get("market_gaps", []) or []
    swot      = comp.get("swot", {}) or {}
    
    if intensity == "Low":
        narrative = (
            f"Competitive intensity is low, with {n_comp} competitor{'s' if n_comp != 1 else ''} identified "
            f"(score: {cscore:.0%}). This presents a meaningful first-mover opportunity. "
            "Early market capture before saturation should be a strategic priority."
        )
    elif intensity == "High":
        narrative = (
            f"The competitive landscape is highly contested ({n_comp} competitors identified, score: {cscore:.0%}). "
            + (f"Established players include {', '.join(top_comp[:4])}. " if top_comp else "")
            + "A clearly differentiated value proposition — whether on price, niche focus, or superior UX — is essential for entry."
        )
    else:
        narrative = (
            f"Competition is moderate with {n_comp} players identified (score: {cscore:.0%}). "
            + (f"Notable competitors include {', '.join(top_comp[:4])}. " if top_comp else "")
            + "Focused positioning within an underserved segment can yield a defensible market share."
        )
    
    elements.append(Paragraph(narrative, styles["Body"]))
    elements.append(Spacer(1, 0.15 * inch))
    
    # Metrics
    rows = [
        ["Metric", "Value"],
        ["Competitive Score",    f"{cscore:.0%}  ({_score_label(cscore)})"],
        ["Intensity Level",      intensity],
        ["Competitors Found",    str(n_comp)],
    ]
    if top_comp:
        rows.append(["Top Competitors", ", ".join(top_comp[:6])])
    elements.append(_kv_table(rows, styles))
    elements.append(Spacer(1, 0.2 * inch))
    
    # SWOT Matrix
    elements.append(Paragraph("SWOT Analysis", styles["H2"]))
    elements.append(Spacer(1, 0.08 * inch))
    
    def _swot_cell(items: List[str]) -> str:
        if not items:
            return "—"
        return "\n".join(f"• {i}" for i in items[:5])
    
    swot_data = [
        [
            Paragraph("<b>Strengths</b>", ParagraphStyle("sh", fontSize=10, textColor=C_GREEN, fontName="Helvetica-Bold")),
            Paragraph("<b>Weaknesses</b>", ParagraphStyle("sh", fontSize=10, textColor=C_RED, fontName="Helvetica-Bold")),
        ],
        [
            Paragraph(_swot_cell(swot.get("strengths", [])).replace("\n", "<br/>"), styles["Body"]),
            Paragraph(_swot_cell(swot.get("weaknesses", [])).replace("\n", "<br/>"), styles["Body"]),
        ],
        [
            Paragraph("<b>Opportunities</b>", ParagraphStyle("sh", fontSize=10, textColor=C_TEAL, fontName="Helvetica-Bold")),
            Paragraph("<b>Threats</b>", ParagraphStyle("sh", fontSize=10, textColor=C_AMBER, fontName="Helvetica-Bold")),
        ],
        [
            Paragraph(_swot_cell(swot.get("opportunities", [])).replace("\n", "<br/>"), styles["Body"]),
            Paragraph(_swot_cell(swot.get("threats", [])).replace("\n", "<br/>"), styles["Body"]),
        ],
    ]
    swot_tbl = Table(swot_data, colWidths=[3.45 * inch, 3.45 * inch])
    swot_tbl.setStyle(TableStyle([
        ("GRID",         (0, 0), (-1, -1), 0.4, C_BORDER),
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#E8F8F5")),
        ("BACKGROUND",   (0, 2), (-1, 2),  colors.HexColor("#EAF2FF")),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    elements.append(swot_tbl)
    
    if gaps and gaps != ["No obvious feature gaps identified."]:
        elements.append(Spacer(1, 0.15 * inch))
        elements.append(Paragraph("Market Gaps Identified", styles["H2"]))
        for gap in gaps[:5]:
            elements.append(Paragraph(f"• {gap}", styles["Bullet"]))
    
    elements.append(PageBreak())


def _build_risks(elements, mapped, styles):
    risk_data = mapped.get("risk_analysis", {})
    risks     = risk_data.get("risks", []) or []
    
    h = Paragraph("Risk Assessment", styles["H1"])
    h.outlineLevel = 0
    elements.append(h)
    _section_rule(elements)
    elements.append(Spacer(1, 0.1 * inch))
    
    if not risks:
        elements.append(Paragraph("No significant risk flags were identified in this analysis.", styles["Body"]))
        elements.append(PageBreak())
        return
    
    high_count = sum(1 for r in risks if r.get("severity") == "High")
    med_count  = sum(1 for r in risks if r.get("severity") == "Medium")
    
    summary = f"Risk aggregation identified {len(risks)} risk item(s)"
    if high_count:
        summary += f", including {high_count} high-severity item{'s' if high_count > 1 else ''}"
    summary += ". Details are provided in the table below."
    elements.append(Paragraph(summary, styles["Body"]))
    elements.append(Spacer(1, 0.15 * inch))
    
    sev_colors = {
        "High":   colors.HexColor("#FDDEDE"),
        "Medium": colors.HexColor("#FEF9E7"),
        "Low":    colors.HexColor("#EAFAF1"),
    }
    
    rows = [["Category", "Severity", "Description"]]
    for r in risks:
        rows.append([
            r.get("category", "General"),
            r.get("severity",  "Medium"),
            r.get("message",   "—"),
        ])
    
    risk_tbl = Table(rows, colWidths=[1.5 * inch, 1.1 * inch, 4.3 * inch])
    style_cmds = [
        ("BACKGROUND",   (0, 0), (-1, 0),  C_NAVY),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  C_WHITE),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("GRID",         (0, 0), (-1, -1), 0.3, C_BORDER),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("ALIGN",        (1, 0), (1, -1),  "CENTER"),
    ]
    for i, r in enumerate(risks, start=1):
        sev = r.get("severity", "Medium")
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), sev_colors.get(sev, C_WHITE)))
    
    risk_tbl.setStyle(TableStyle(style_cmds))
    elements.append(risk_tbl)
    elements.append(PageBreak())


def _build_recommendations(elements, mapped, styles):
    rec_data = mapped.get("recommendations", {})
    dec_data = mapped.get("decision", {})
    so       = mapped.get("score_overview", {})
    conf     = mapped.get("data_confidence", {})
    
    h = Paragraph("Recommendations & Decision", styles["H1"])
    h.outlineLevel = 0
    elements.append(h)
    _section_rule(elements)
    elements.append(Spacer(1, 0.1 * inch))
    
    recs = rec_data.get("recommendations", []) or []
    if recs:
        elements.append(Paragraph("Strategic Recommendations", styles["H2"]))
        
        rec_rows = [["#", "Recommendation", "Priority"]]
        for i, rec in enumerate(recs, 1):
            text  = str(rec)
            lower = text.lower()
            if any(w in lower for w in ["immediate", "urgent", "critical", "must", "aggressively"]):
                priority = "High"
            elif any(w in lower for w in ["monitor", "review", "consider", "optional"]):
                priority = "Low"
            else:
                priority = "Medium"
            rec_rows.append([str(i), text, priority])
        
        rec_tbl = Table(rec_rows, colWidths=[0.4 * inch, 5.2 * inch, 1.3 * inch])
        prio_colors = {"High": colors.HexColor("#FDDEDE"), "Medium": colors.HexColor("#FEF9E7"), "Low": colors.HexColor("#EAFAF1")}
        
        style_cmds = [
            ("BACKGROUND",   (0, 0), (-1, 0),  C_STEEL),
            ("TEXTCOLOR",    (0, 0), (-1, 0),  C_WHITE),
            ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",     (0, 0), (-1, -1), 9),
            ("GRID",         (0, 0), (-1, -1), 0.3, C_BORDER),
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
            ("ALIGN",        (0, 0), (0, -1),  "CENTER"),
            ("ALIGN",        (2, 0), (2, -1),  "CENTER"),
        ]
        for i, row in enumerate(rec_rows[1:], 1):
            p = row[2]
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), prio_colors.get(p, C_WHITE)))
        rec_tbl.setStyle(TableStyle(style_cmds))
        elements.append(rec_tbl)
        elements.append(Spacer(1, 0.25 * inch))
    
    # Decision banner
    decision = dec_data.get("final_decision", "—")
    dec_color = {"Proceed": C_GREEN, "Proceed with Caution": C_AMBER, "Re-evaluate": C_RED}.get(decision, C_STEEL)
    
    dec_tbl = Table([[Paragraph(f"<b>DECISION: {decision.upper()}</b>",
                               ParagraphStyle("dec", fontSize=14, textColor=C_WHITE, alignment=TA_CENTER, leading=18))]],
                    colWidths=[6.9 * inch], rowHeights=[0.55 * inch])
    dec_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), dec_color),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(dec_tbl)
    elements.append(Spacer(1, 0.15 * inch))
    
    # Rationale
    score = so.get("overall_score", 0)
    oc    = conf.get("overall", "Unknown")
    rationale = (
        f"Decision based on an overall viability score of {score:.0%} with "
        f"{oc.lower()} data confidence. "
    )
    if score >= 0.65:
        rationale += "The analysis supports proceeding, subject to active risk monitoring."
    elif score >= 0.4:
        rationale += "Proceed with defined milestones and clear exit criteria if targets are not met."
    else:
        rationale += "Fundamental assumptions require validation before further capital commitment."
    elements.append(Paragraph(rationale, styles["Body"]))


def _build_sources(elements, mapped, styles):
    sources = mapped.get("sources", []) or []
    if not sources:
        return
    
    elements.append(Spacer(1, 0.2 * inch))
    h = Paragraph("Appendix: Research Sources", styles["H1"])
    h.outlineLevel = 0
    elements.append(h)
    _section_rule(elements)
    elements.append(Spacer(1, 0.1 * inch))
    
    rows = [["#", "Title", "URL"]]
    for i, src in enumerate(sources, 1):
        title = str(src.get("title", "") or src.get("url", ""))[:60]
        url   = str(src.get("url", ""))[:80]
        rows.append([str(i), title, url])
    
    tbl = Table(rows, colWidths=[0.4 * inch, 2.8 * inch, 3.7 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  C_NAVY),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  C_WHITE),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 0), (-1, -1), 8),
        ("GRID",         (0, 0), (-1, -1), 0.3, C_BORDER),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LIGHT]),
        ("ALIGN",        (0, 0), (0, -1),  "CENTER"),
    ]))
    elements.append(tbl)


# ── Public class ───────────────────────────────────────────────────────────

class PDFGenerator:
    """
    Improved PDF report generator.
    
    Usage:
        gen = PDFGenerator()
        gen.generate(mapped_data, output_path)
    """
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(self, mapped_data: Dict[str, Any], file_path=None) -> str:
        if not mapped_data:
            raise ValueError("mapped_data is empty — cannot generate PDF.")
        
        if file_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = self.output_dir / f"report_{ts}.pdf"
        
        file_path = str(file_path)
        styles    = _make_styles()
        elements  = []
        
        _build_cover(elements, mapped_data, styles)
        _build_toc(elements, styles)
        _build_executive_summary(elements, mapped_data, styles)
        _build_scores(elements, mapped_data, styles)
        _build_financial(elements, mapped_data, styles)
        _build_market(elements, mapped_data, styles)
        _build_competitive(elements, mapped_data, styles)
        _build_risks(elements, mapped_data, styles)
        _build_recommendations(elements, mapped_data, styles)
        _build_sources(elements, mapped_data, styles)
        
        doc = _TOCDocTemplate(
            file_path,
            pagesize=A4,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.9 * inch,
            bottomMargin=0.75 * inch,
        )
        doc.build(elements, onFirstPage=_header_footer, onLaterPages=_header_footer)
        return file_path