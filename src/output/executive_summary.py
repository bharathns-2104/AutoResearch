"""
executive_summary.py — Improved Executive Summary Generator

Generates a rich, data-accurate executive summary using LLM when available,
with a structured rule-based fallback that uses real extracted numbers.

Key improvements over original:
  1. Uses actual extracted financial metrics (TAM, growth rate, runway, etc.)
  2. LLM-assisted synthesis with a rich, structured prompt
  3. Rule-based fallback that is data-driven (not just generic phrases)
  4. Data confidence flags injected into the narrative
  5. Competitor intelligence woven into the summary
"""

from __future__ import annotations

import json
from typing import Dict, Any, Optional


_EXEC_SUMMARY_SYSTEM = """You are a senior business strategy analyst writing the executive summary 
of a venture analysis report. Your writing is concise, authoritative, and data-driven.

Given structured analysis data, write a 3-4 paragraph executive summary that:
1. Opens with a crisp statement of what the business is and its core opportunity
2. Cites specific numbers (TAM, CAGR, runway, viability score) naturally in prose
3. Names the competitive landscape concisely
4. Ends with a clear forward-looking recommendation

Rules:
- NEVER make up numbers not in the input data
- If a metric is missing/zero, do not fabricate it — acknowledge the gap
- Write in third person, past tense for findings ("Analysis revealed...")
- Maximum 200 words
- No bullet points — flowing paragraphs only
- Tone: investment memo style
"""

_EXEC_SUMMARY_USER = """Generate an executive summary from this analysis data:

Business: {business_idea}
Industry: {industry}  
Target Market: {target_market}
Budget: ${budget:,}
Timeline: {timeline_months} months

FINANCIAL ANALYSIS:
- Viability Score: {fin_score:.0%}
- Estimated Runway: {runway:.1f} months
- Monthly Burn Rate: ${monthly_burn:,.0f}
- Estimated Revenue (projected): ${est_revenue:,.0f}
- Growth Rate (market): {growth_rate:.1f}%
- Profit Margin (est.): {profit_margin:.1f}%

MARKET ANALYSIS:
- Opportunity Score: {mkt_score:.0%}
- TAM: ${tam:,.0f} {tam_currency}
- SAM: ${sam:,.0f} {tam_currency}
- SOM: ${som:,.0f} {tam_currency}
- Market Growth Rate (CAGR): {market_growth:.1f}%
- Sentiment: {sentiment_label} (score: {sentiment_score:+.2f})

COMPETITIVE ANALYSIS:
- Competitive Intensity: {comp_intensity}
- Competitors Identified: {num_competitors}
- Top Competitors: {top_competitors}
- Viability Rating: {overall_rating}
- Overall Viability Score: {overall_score:.0%}

DECISION: {decision}

DATA CONFIDENCE: Financial={fin_conf}, Market={mkt_conf}, Competitive={comp_conf}
"""


def generate_executive_summary(consolidated: Dict[str, Any]) -> str:
    """
    Generate a high-quality executive summary from consolidated analysis data.
    
    Returns a plain-text summary string.
    Falls back to rule-based generation if LLM is unavailable.
    """
    # Extract all metrics upfront
    fin     = consolidated.get("financial_details", {}) or {}
    mkt     = consolidated.get("market_details", {}) or {}
    comp    = consolidated.get("competitive_details", {}) or {}
    bi      = consolidated.get("agent_results", {}).get("market", {}) or {}
    
    # Business context
    business_input = consolidated.get("business_input", {}) or {}
    # Try multiple key locations for business input fields
    business_idea  = business_input.get("business_idea", "") or consolidated.get("business_idea", "the business concept")
    industry       = business_input.get("industry", "") or consolidated.get("industry", "the target industry")
    target_market  = business_input.get("target_market", "") or consolidated.get("target_market", "the target market")
    budget         = float(business_input.get("budget", 0) or consolidated.get("budget", 0) or 0)
    timeline       = int(business_input.get("timeline_months", 12) or consolidated.get("timeline_months", 12) or 12)
    
    # Financial metrics
    fin_metrics    = fin.get("metrics", {}) or {}
    fin_score      = float(fin.get("viability_score", consolidated.get("financial_score", 0)) or 0)
    runway         = float(fin.get("runway_months", 0) or 0)
    monthly_burn   = float(fin_metrics.get("monthly_burn", 0) or 0)
    est_revenue    = float(fin_metrics.get("estimated_revenue", 0) or 0)
    growth_rate    = float(fin_metrics.get("growth_rate", 0) or 0)
    profit_margin  = float(fin_metrics.get("profit_margin", 0) or 0)
    
    # Market metrics
    mkt_score      = float(consolidated.get("market_score", 0) or 0)
    tam_data       = mkt.get("tam_sam_som", {}) or {}
    tam            = float(mkt.get("tam", tam_data.get("tam", 0)) or 0)
    sam            = float(mkt.get("sam", tam_data.get("sam", 0)) or 0)
    som            = float(mkt.get("som", tam_data.get("som", 0)) or 0)
    tam_currency   = mkt.get("tam_currency", "USD")
    market_growth  = float(mkt.get("growth_rate", 0) or 0)
    sentiment      = mkt.get("sentiment", {}) or {}
    sent_label     = sentiment.get("sentiment_label", sentiment.get("label", "Neutral"))
    sent_score     = float(sentiment.get("sentiment_score", sentiment.get("score", 0)) or 0)
    
    # Competitive metrics
    comp_score     = float(consolidated.get("competitive_score", 0) or 0)
    comp_intensity = comp.get("competitive_intensity", "Medium")
    num_competitors = int(comp.get("competitors_found", 0) or 0)
    top_competitors = comp.get("top_competitors", []) or []
    top_comp_str   = ", ".join(top_competitors[:5]) if top_competitors else "None identified"
    
    # Overall
    overall_score  = float(consolidated.get("overall_viability_score", 0) or 0)
    overall_rating = consolidated.get("overall_rating", "Moderate")
    decision       = consolidated.get("decision", "Proceed with Caution")
    
    # Confidence
    dq = consolidated.get("data_quality", {}) or consolidated.get("metadata", {}) or {}
    fin_conf  = dq.get("financial", "Unknown")
    mkt_conf  = dq.get("market", "Unknown")
    comp_conf = dq.get("competitive", "Unknown")
    
    # Try LLM path
    try:
        from src.orchestration.llm_client import call_llm
        
        user_prompt = _EXEC_SUMMARY_USER.format(
            business_idea=business_idea,
            industry=industry,
            target_market=target_market,
            budget=budget,
            timeline_months=timeline,
            fin_score=fin_score,
            runway=runway,
            monthly_burn=monthly_burn,
            est_revenue=est_revenue,
            growth_rate=growth_rate,
            profit_margin=profit_margin,
            mkt_score=mkt_score,
            tam=tam,
            sam=sam,
            som=som,
            tam_currency=tam_currency,
            market_growth=market_growth,
            sentiment_label=sent_label,
            sentiment_score=sent_score,
            comp_intensity=comp_intensity,
            num_competitors=num_competitors,
            top_competitors=top_comp_str,
            overall_rating=overall_rating,
            overall_score=overall_score,
            decision=decision,
            fin_conf=fin_conf,
            mkt_conf=mkt_conf,
            comp_conf=comp_conf,
        )
        
        result = call_llm(_EXEC_SUMMARY_SYSTEM, user_prompt, expect_json=False)
        if result and len(result.strip()) > 50:
            return result.strip()
    except Exception:
        pass  # Fall through to rule-based
    
    # Rule-based fallback (data-accurate)
    return _rule_based_summary(
        business_idea=business_idea,
        industry=industry,
        target_market=target_market,
        budget=budget,
        fin_score=fin_score,
        runway=runway,
        monthly_burn=monthly_burn,
        tam=tam,
        market_growth=market_growth,
        sent_label=sent_label,
        comp_intensity=comp_intensity,
        num_competitors=num_competitors,
        top_comp_str=top_comp_str,
        overall_score=overall_score,
        overall_rating=overall_rating,
        decision=decision,
        mkt_score=mkt_score,
        fin_conf=fin_conf,
        mkt_conf=mkt_conf,
    )


def _fmt_currency(val: float) -> str:
    """Format a USD value compactly: $1.2B, $450M, $50K."""
    if val == 0:
        return "N/A"
    if val >= 1e9:
        return f"${val/1e9:.1f}B"
    if val >= 1e6:
        return f"${val/1e6:.1f}M"
    if val >= 1e3:
        return f"${val/1e3:.0f}K"
    return f"${val:,.0f}"


def _rule_based_summary(
    business_idea, industry, target_market, budget,
    fin_score, runway, monthly_burn, tam, market_growth,
    sent_label, comp_intensity, num_competitors, top_comp_str,
    overall_score, overall_rating, decision, mkt_score, fin_conf, mkt_conf,
) -> str:
    
    paragraphs = []

    # Paragraph 1: Business & opportunity overview
    tam_str = _fmt_currency(tam)
    growth_str = f"{market_growth:.1f}% CAGR" if market_growth > 0 else "growth data pending"
    
    p1 = (
        f"Analysis was conducted on {business_idea}, operating within the {industry} sector "
        f"targeting {target_market}. "
    )
    if tam > 0:
        p1 += (
            f"The total addressable market is estimated at {tam_str}, expanding at {growth_str}. "
        )
    if sent_label != "Neutral":
        p1 += f"Market sentiment is {sent_label.lower()}, suggesting "
        p1 += "favourable demand signals." if sent_label == "Positive" else "headwinds that warrant careful positioning."
    
    paragraphs.append(p1.strip())

    # Paragraph 2: Financial health
    runway_str = f"{runway:.0f} months" if runway > 0 else "undetermined"
    burn_str   = _fmt_currency(monthly_burn) if monthly_burn > 0 else "N/A"
    budget_str = _fmt_currency(budget)
    
    p2 = (
        f"Financial analysis returned a viability score of {fin_score:.0%}. "
        f"With a declared budget of {budget_str}, the estimated operational runway stands at "
        f"{runway_str} at a monthly burn rate of {burn_str}. "
    )
    if fin_score >= 0.65:
        p2 += "The financial profile is sufficiently robust to support near-term execution."
    elif fin_score >= 0.4:
        p2 += "The financial position is workable but requires disciplined cost management and early revenue validation."
    else:
        p2 += "The financial case remains weak; a revised cost model or additional funding should be secured before commitment."
    
    if fin_conf and fin_conf != "Unknown":
        p2 += f" (Financial data confidence: {fin_conf}.)"
    
    paragraphs.append(p2.strip())

    # Paragraph 3: Competitive landscape
    if num_competitors > 0:
        p3 = (
            f"The competitive environment is classified as {comp_intensity.lower()}, "
            f"with {num_competitors} distinct competitor{'s' if num_competitors != 1 else ''} identified. "
        )
        if top_comp_str and top_comp_str != "None identified":
            p3 += f"Notable players include {top_comp_str}. "
        if comp_intensity == "High":
            p3 += "Differentiation and niche positioning will be critical to market entry."
        elif comp_intensity == "Low":
            p3 += "Low market density presents a meaningful first-mover opportunity."
        else:
            p3 += "A focused go-to-market strategy targeting an underserved segment is recommended."
    else:
        p3 = (
            "Competitor data was limited in this analysis run. "
            "A targeted competitive scan is recommended prior to finalising market strategy."
        )
    paragraphs.append(p3.strip())

    # Paragraph 4: Verdict
    p4 = (
        f"The consolidated viability score is {overall_score:.0%}, rated {overall_rating}. "
        f"The recommended decision is: {decision}. "
    )
    if overall_score >= 0.65:
        p4 += (
            "The opportunity demonstrates sufficient commercial merit to justify proceeding, "
            "subject to the risk mitigations outlined in this report."
        )
    elif overall_score >= 0.4:
        p4 += (
            "The opportunity has potential, but material uncertainties in the "
            f"{'financial ' if fin_score < 0.5 else ''}{'market ' if mkt_score < 0.5 else ''}"
            "data should be resolved before scaling investment."
        )
    else:
        p4 += (
            "The current assessment does not support full commitment. "
            "A pivot in value proposition or market focus is advised."
        )
    paragraphs.append(p4.strip())

    return "\n\n".join(paragraphs)