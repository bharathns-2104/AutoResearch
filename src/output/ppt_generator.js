#!/usr/bin/env node
/**
 * ppt_generator.js — Improved PPT Report Generator
 *
 * Usage:
 *   node ppt_generator.js <json_data_path> <output_path>
 *
 * Input: JSON file with mapped_data structure (same as PDF generator)
 * Output: Professional .pptx file
 *
 * Design: "Midnight Executive" palette — navy dominates, teal accents,
 *          white/ice-blue content. Dark title/close slides, light content slides.
 */

const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

// ── Palette ──────────────────────────────────────────────────────────────────
const C = {
  navy:    "0D1B2A",
  steel:   "1B4F72",
  teal:    "148F77",
  tealDim: "A9DFBF",
  amber:   "D4AC0D",
  red:     "C0392B",
  green:   "1E8449",
  greenBg: "EAFAF1",
  light:   "F4F6F7",
  border:  "D5D8DC",
  white:   "FFFFFF",
  text:    "1C2833",
  dimText: "5D6D7E",
  redBg:   "FDDEDE",
  amberBg: "FEF9E7",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtCurrency(val, currency = "USD") {
  if (!val || val === 0) return "N/A";
  if (val >= 1e12) return `$${(val / 1e12).toFixed(2)}T ${currency}`;
  if (val >= 1e9)  return `$${(val / 1e9).toFixed(2)}B ${currency}`;
  if (val >= 1e6)  return `$${(val / 1e6).toFixed(2)}M ${currency}`;
  if (val >= 1e3)  return `$${(val / 1e3).toFixed(0)}K ${currency}`;
  return `$${val.toLocaleString()} ${currency}`;
}

function fmtPct(val, decimals = 1) {
  if (val === null || val === undefined || val === 0) return "N/A";
  return `${parseFloat(val).toFixed(decimals)}%`;
}

function fmtMonths(val) {
  if (!val) return "N/A";
  return `${parseFloat(val).toFixed(1)} months`;
}

function scoreLabel(s) {
  if (s >= 0.65) return "Strong";
  if (s >= 0.40) return "Moderate";
  return "Weak";
}

function scoreColor(s) {
  if (s >= 0.65) return C.green;
  if (s >= 0.40) return C.amber;
  return C.red;
}

function decisionColor(d) {
  if (d === "Proceed") return C.green;
  if (d === "Proceed with Caution") return C.amber;
  return C.red;
}

function clamp(val, min = 0, max = 1) {
  return Math.min(max, Math.max(min, val || 0));
}

// ── Slide builders ────────────────────────────────────────────────────────────

/**
 * Slide 1: Title / Cover
 */
function buildTitleSlide(prs, mapped) {
  const slide = prs.addSlide();
  slide.background = { color: C.navy };

  const tp = mapped.title_page || {};
  const so = mapped.score_overview || {};
  const dec = mapped.decision || {};

  // Top teal accent bar
  slide.addShape(prs.shapes.RECTANGLE, {
    x: 0, y: 0, w: "100%", h: 0.08,
    fill: { color: C.teal }, line: { color: C.teal }
  });

  // Brand label
  slide.addText("AutoResearch", {
    x: 0.5, y: 0.25, w: 9, h: 0.35,
    fontSize: 11, color: C.tealDim, charSpacing: 5,
    fontFace: "Calibri", bold: false, margin: 0
  });

  // Main title
  slide.addText(tp.project_title || "Business Analysis Report", {
    x: 0.5, y: 0.75, w: 9, h: 1.2,
    fontSize: 32, color: C.white, bold: true,
    fontFace: "Cambria", margin: 0
  });

  // Generated date
  slide.addText(`Generated: ${tp.generated_at || new Date().toISOString().split("T")[0]}`, {
    x: 0.5, y: 2.0, w: 6, h: 0.3,
    fontSize: 11, color: C.dimText, fontFace: "Calibri", margin: 0
  });

  // Score card
  const overall = clamp(so.overall_score || 0);
  const rating  = so.rating || "—";
  const sColor  = scoreColor(overall);
  const decision = dec.final_decision || "—";
  const dColor  = decisionColor(decision);

  // Score circle background
  slide.addShape(prs.shapes.OVAL, {
    x: 7.2, y: 0.6, w: 2.3, h: 2.3,
    fill: { color: C.navy },
    line: { color: sColor, width: 3 }
  });
  slide.addText(`${Math.round(overall * 100)}%`, {
    x: 7.2, y: 0.85, w: 2.3, h: 0.8,
    fontSize: 36, color: sColor, bold: true,
    fontFace: "Cambria", align: "center", margin: 0
  });
  slide.addText(rating, {
    x: 7.2, y: 1.65, w: 2.3, h: 0.3,
    fontSize: 12, color: C.white, fontFace: "Calibri",
    align: "center", margin: 0
  });
  slide.addText("VIABILITY", {
    x: 7.2, y: 1.95, w: 2.3, h: 0.25,
    fontSize: 8, color: C.dimText, fontFace: "Calibri",
    charSpacing: 3, align: "center", margin: 0
  });

  // Decision badge
  slide.addShape(prs.shapes.RECTANGLE, {
    x: 0.5, y: 2.5, w: 2.8, h: 0.45,
    fill: { color: dColor }, line: { color: dColor }
  });
  slide.addText(`DECISION: ${decision.toUpperCase()}`, {
    x: 0.5, y: 2.5, w: 2.8, h: 0.45,
    fontSize: 10, color: C.white, bold: true,
    fontFace: "Calibri", align: "center", valign: "middle", margin: 0
  });

  // Divider line
  slide.addShape(prs.shapes.LINE, {
    x: 0.5, y: 3.2, w: 9, h: 0,
    line: { color: "2C3E50", width: 0.5 }
  });

  // Bottom metrics strip
  const ds = mapped.domain_scores || {};
  const metrics = [
    ["Financial", clamp(ds.financial_score || 0)],
    ["Market",    clamp(ds.market_score || 0)],
    ["Competitive", clamp(ds.competitive_score || 0)],
  ];
  metrics.forEach(([label, score], i) => {
    const x = 0.5 + i * 3.1;
    slide.addText(label, {
      x, y: 3.35, w: 2.8, h: 0.25,
      fontSize: 9, color: C.dimText, fontFace: "Calibri",
      charSpacing: 2, align: "center", margin: 0
    });
    slide.addText(`${Math.round(score * 100)}%`, {
      x, y: 3.6, w: 2.8, h: 0.45,
      fontSize: 22, color: scoreColor(score), bold: true,
      fontFace: "Cambria", align: "center", margin: 0
    });
    // Small bar
    const barW = 2.5 * score;
    if (barW > 0) {
      slide.addShape(prs.shapes.RECTANGLE, {
        x: x + 0.15, y: 4.12, w: 2.5, h: 0.07,
        fill: { color: "2C3E50" }, line: { color: "2C3E50" }
      });
      slide.addShape(prs.shapes.RECTANGLE, {
        x: x + 0.15, y: 4.12, w: barW, h: 0.07,
        fill: { color: scoreColor(score) }, line: { color: scoreColor(score) }
      });
    }
  });
}

/**
 * Slide 2: Executive Summary
 */
function buildExecSummarySlide(prs, mapped) {
  const slide = prs.addSlide();
  slide.background = { color: C.white };

  _sectionHeader(slide, prs, "Executive Summary", "01");

  const summary = (mapped.executive_summary || {}).summary_text || "No summary available.";
  const paragraphs = summary.split(/\n\n+/).filter(p => p.trim());

  // Show first 2 paragraphs
  const displayText = paragraphs.slice(0, 2).join("\n\n");

  slide.addText(displayText, {
    x: 0.5, y: 1.1, w: 9, h: 3.4,
    fontSize: 12, color: C.text, fontFace: "Calibri",
    align: "left", valign: "top", margin: 0,
    paraSpaceAfter: 10
  });

  // Key stats sidebar
  const so   = mapped.score_overview || {};
  const conf = mapped.data_confidence || {};
  _statsCard(slide, prs, [
    ["Overall Score",   `${Math.round(clamp(so.overall_score || 0) * 100)}%`],
    ["Rating",          so.rating || "—"],
    ["Data Confidence", conf.overall || "—"],
  ], 0.5, 4.6, 4);
}

/**
 * Slide 3: Score Overview
 */
function buildScoreSlide(prs, mapped) {
  const slide = prs.addSlide();
  slide.background = { color: C.white };

  _sectionHeader(slide, prs, "Viability Score Overview", "02");

  const so = mapped.score_overview || {};
  const ds = mapped.domain_scores || {};
  const conf = mapped.data_confidence || {};

  const overall = clamp(so.overall_score || 0);
  const sColor  = scoreColor(overall);

  // Large score
  slide.addText(`${Math.round(overall * 100)}%`, {
    x: 0.5, y: 1.1, w: 3, h: 1.2,
    fontSize: 60, color: sColor, bold: true,
    fontFace: "Cambria", align: "center", margin: 0
  });
  slide.addText(so.rating || "—", {
    x: 0.5, y: 2.35, w: 3, h: 0.35,
    fontSize: 14, color: sColor, fontFace: "Calibri",
    align: "center", margin: 0
  });
  slide.addText("Overall Viability", {
    x: 0.5, y: 2.7, w: 3, h: 0.25,
    fontSize: 9, color: C.dimText, fontFace: "Calibri",
    charSpacing: 2, align: "center", margin: 0
  });

  // Domain score bars (right side)
  const domains = [
    { label: "Financial",   score: clamp(ds.financial_score || 0),   conf: conf.financial || "—" },
    { label: "Market",      score: clamp(ds.market_score || 0),      conf: conf.market || "—" },
    { label: "Competitive", score: clamp(ds.competitive_score || 0), conf: conf.competitive || "—" },
  ];

  domains.forEach((d, i) => {
    const y  = 1.15 + i * 1.1;
    const bW = 5.0 * d.score;
    const sc = scoreColor(d.score);

    slide.addText(d.label, {
      x: 4.0, y, w: 2.5, h: 0.28,
      fontSize: 11, color: C.text, fontFace: "Calibri", bold: true, margin: 0
    });
    slide.addText(`${Math.round(d.score * 100)}%  (${scoreLabel(d.score)})  · Confidence: ${d.conf}`, {
      x: 4.0, y: y + 0.3, w: 5.5, h: 0.25,
      fontSize: 9, color: C.dimText, fontFace: "Calibri", margin: 0
    });
    // Background bar
    slide.addShape(prs.shapes.RECTANGLE, {
      x: 4.0, y: y + 0.6, w: 5.5, h: 0.2,
      fill: { color: C.light }, line: { color: C.border, width: 0.5 }
    });
    if (bW > 0) {
      slide.addShape(prs.shapes.RECTANGLE, {
        x: 4.0, y: y + 0.6, w: Math.min(bW, 5.5), h: 0.2,
        fill: { color: sc }, line: { color: sc }
      });
    }
  });

  // Bottom confidence note
  const oc = conf.overall || "Unknown";
  slide.addText(
    `Data confidence: ${oc}. ${oc === "High" ? "Results well-supported." : oc === "Medium" ? "Some data gaps — treat projections as directional." : "Sparse data — preliminary estimates only."}`,
    { x: 0.5, y: 4.7, w: 9, h: 0.4, fontSize: 9, color: C.dimText, fontFace: "Calibri", italic: true, margin: 0 }
  );
}

/**
 * Slide 4: Financial Analysis
 */
function buildFinancialSlide(prs, mapped) {
  const slide = prs.addSlide();
  slide.background = { color: C.white };

  _sectionHeader(slide, prs, "Financial Analysis", "03");

  const fin  = mapped.financial_details || {};
  const ds   = mapped.domain_scores || {};
  const conf = mapped.data_confidence || {};

  const fscore = clamp(ds.financial_score || 0);

  // Left: key metrics
  const metrics = [
    ["Viability Score",    `${Math.round(fscore * 100)}%  (${scoreLabel(fscore)})`],
    ["Runway",             fmtMonths(fin.runway_months)],
    ["Monthly Burn",       fmtCurrency(fin.monthly_burn)],
    ["Projected Revenue",  fmtCurrency(fin.estimated_revenue)],
    ["Market Growth Rate", fmtPct(fin.growth_rate)],
    ["Profit Margin (est.)", fmtPct(fin.profit_margin)],
  ];

  _metricTable(slide, prs, metrics, 0.4, 1.1, 4.5, 0.52);

  // Right: visual score gauge
  _scoreGauge(slide, prs, fscore, 5.8, 1.1, "Financial Score");

  // Confidence
  slide.addText(`Data confidence: ${conf.financial || "Unknown"}`, {
    x: 0.4, y: 4.7, w: 9, h: 0.3,
    fontSize: 9, color: C.dimText, fontFace: "Calibri", italic: true, margin: 0
  });
}

/**
 * Slide 5: Market Analysis
 */
function buildMarketSlide(prs, mapped) {
  const slide = prs.addSlide();
  slide.background = { color: C.white };

  _sectionHeader(slide, prs, "Market Analysis", "04");

  const mkt  = mapped.market_details || {};
  const ds   = mapped.domain_scores || {};
  const conf = mapped.data_confidence || {};

  const mscore   = clamp(ds.market_score || 0);
  const currency = mkt.tam_currency || "USD";

  const metrics = [
    ["Market Score",       `${Math.round(mscore * 100)}%  (${scoreLabel(mscore)})`],
    ["Total Addressable Market (TAM)", fmtCurrency(mkt.tam, currency)],
    ["Serviceable Market (SAM)",       fmtCurrency(mkt.sam, currency)],
    ["Obtainable Market (SOM)",        fmtCurrency(mkt.som, currency)],
    ["CAGR",               fmtPct(mkt.growth_rate)],
    ["Market Sentiment",   `${mkt.sentiment_label || "Neutral"} (${parseFloat(mkt.sentiment_score || 0) >= 0 ? "+" : ""}${parseFloat(mkt.sentiment_score || 0).toFixed(2)})`],
  ];

  _metricTable(slide, prs, metrics, 0.4, 1.1, 5.2, 0.52);

  // Insights
  const insights = mkt.key_insights || [];
  if (insights.length > 0) {
    slide.addText("Key Insights", {
      x: 6.0, y: 1.1, w: 3.5, h: 0.3,
      fontSize: 11, color: C.steel, bold: true, fontFace: "Calibri", margin: 0
    });
    insights.slice(0, 4).forEach((ins, i) => {
      slide.addShape(prs.shapes.OVAL, {
        x: 6.0, y: 1.5 + i * 0.75 + 0.07, w: 0.15, h: 0.15,
        fill: { color: C.teal }, line: { color: C.teal }
      });
      slide.addText(ins, {
        x: 6.2, y: 1.5 + i * 0.75, w: 3.3, h: 0.65,
        fontSize: 10, color: C.text, fontFace: "Calibri",
        valign: "middle", margin: 0
      });
    });
  }

  slide.addText(`Data confidence: ${conf.market || "Unknown"}`, {
    x: 0.4, y: 4.7, w: 9, h: 0.3,
    fontSize: 9, color: C.dimText, fontFace: "Calibri", italic: true, margin: 0
  });
}

/**
 * Slide 6: Competitive Analysis
 */
function buildCompetitiveSlide(prs, mapped) {
  const slide = prs.addSlide();
  slide.background = { color: C.white };

  _sectionHeader(slide, prs, "Competitive Analysis", "05");

  const comp = mapped.competitive_details || {};
  const ds   = mapped.domain_scores || {};
  const conf = mapped.data_confidence || {};

  const cscore    = clamp(ds.competitive_score || 0);
  const intensity = comp.competitive_intensity || "Unknown";
  const topComps  = comp.top_competitors || [];

  // Left: metrics
  const metrics = [
    ["Competitive Score",  `${Math.round(cscore * 100)}%  (${scoreLabel(cscore)})`],
    ["Market Intensity",   intensity],
    ["Competitors Found",  String(comp.competitors_found || 0)],
  ];
  if (topComps.length > 0) {
    metrics.push(["Top Players", topComps.slice(0, 3).join(", ")]);
  }
  _metricTable(slide, prs, metrics, 0.4, 1.1, 4.5, 0.55);

  // Right: SWOT mini (2x2 grid)
  const swot = comp.swot || {};
  const quadrants = [
    { label: "Strengths",     items: swot.strengths    || [],  x: 5.5, y: 1.1,  bgColor: "EAFAF1", labelColor: C.green },
    { label: "Weaknesses",    items: swot.weaknesses   || [],  x: 7.75, y: 1.1, bgColor: "FDDEDE", labelColor: C.red   },
    { label: "Opportunities", items: swot.opportunities|| [],  x: 5.5, y: 2.9,  bgColor: "EAF2FF", labelColor: C.steel },
    { label: "Threats",       items: swot.threats      || [],  x: 7.75, y: 2.9, bgColor: C.amberBg, labelColor: C.amber },
  ];

  quadrants.forEach(q => {
    slide.addShape(prs.shapes.RECTANGLE, {
      x: q.x, y: q.y, w: 2.1, h: 1.65,
      fill: { color: q.bgColor }, line: { color: C.border, width: 0.5 }
    });
    slide.addText(q.label, {
      x: q.x + 0.1, y: q.y + 0.05, w: 1.9, h: 0.28,
      fontSize: 9, color: q.labelColor, bold: true, fontFace: "Calibri", margin: 0
    });
    const bodyText = q.items.slice(0, 3).map(i => `• ${i}`).join("\n") || "—";
    slide.addText(bodyText, {
      x: q.x + 0.1, y: q.y + 0.35, w: 1.9, h: 1.2,
      fontSize: 8.5, color: C.text, fontFace: "Calibri",
      valign: "top", margin: 0
    });
  });

  slide.addText(`Data confidence: ${conf.competitive || "Unknown"}`, {
    x: 0.4, y: 4.7, w: 9, h: 0.3,
    fontSize: 9, color: C.dimText, fontFace: "Calibri", italic: true, margin: 0
  });
}

/**
 * Slide 7: Risks
 */
function buildRiskSlide(prs, mapped) {
  const slide = prs.addSlide();
  slide.background = { color: C.white };

  _sectionHeader(slide, prs, "Risk Assessment", "06");

  const risks = (mapped.risk_analysis || {}).risks || [];

  if (risks.length === 0) {
    slide.addText("No significant risk flags identified.", {
      x: 0.5, y: 1.5, w: 9, h: 0.5,
      fontSize: 14, color: C.dimText, fontFace: "Calibri", align: "center", margin: 0
    });
    return;
  }

  // Risk table
  const headers = [
    { text: "Category", options: { bold: true, color: C.white, fill: { color: C.navy }, fontSize: 10 } },
    { text: "Severity",  options: { bold: true, color: C.white, fill: { color: C.navy }, fontSize: 10 } },
    { text: "Description", options: { bold: true, color: C.white, fill: { color: C.navy }, fontSize: 10 } },
  ];

  const severityBg = { High: C.redBg, Medium: C.amberBg, Low: C.greenBg };

  const rows = [headers, ...risks.slice(0, 7).map(r => {
    const sev = r.severity || "Medium";
    const bg  = severityBg[sev] || C.light;
    return [
      { text: r.category || "General",  options: { fontSize: 9, fill: { color: bg } } },
      { text: sev,                       options: { fontSize: 9, fill: { color: bg }, bold: true } },
      { text: (r.message || "—").slice(0, 120), options: { fontSize: 9, fill: { color: bg } } },
    ];
  })];

  slide.addTable(rows, {
    x: 0.4, y: 1.1, w: 9.2, colW: [1.5, 1.1, 6.6],
    border: { pt: 0.4, color: C.border },
  });
}

/**
 * Slide 8: Recommendations
 */
function buildRecommendationsSlide(prs, mapped) {
  const slide = prs.addSlide();
  slide.background = { color: C.white };

  _sectionHeader(slide, prs, "Strategic Recommendations", "07");

  const recs = (mapped.recommendations || {}).recommendations || [];
  const dec  = mapped.decision || {};

  recs.slice(0, 5).forEach((rec, i) => {
    const y = 1.15 + i * 0.7;
    // Number circle
    slide.addShape(prs.shapes.OVAL, {
      x: 0.4, y: y + 0.05, w: 0.35, h: 0.35,
      fill: { color: C.teal }, line: { color: C.teal }
    });
    slide.addText(String(i + 1), {
      x: 0.4, y: y + 0.05, w: 0.35, h: 0.35,
      fontSize: 10, color: C.white, bold: true, fontFace: "Calibri",
      align: "center", valign: "middle", margin: 0
    });
    slide.addText(rec, {
      x: 0.88, y, w: 8.6, h: 0.6,
      fontSize: 11, color: C.text, fontFace: "Calibri",
      valign: "middle", margin: 0
    });
  });
}

/**
 * Slide 9: Decision (closing dark slide)
 */
function buildDecisionSlide(prs, mapped) {
  const slide = prs.addSlide();
  slide.background = { color: C.navy };

  const dec    = mapped.decision || {};
  const so     = mapped.score_overview || {};
  const conf   = mapped.data_confidence || {};
  const decision = dec.final_decision || "—";
  const dColor   = decisionColor(decision);
  const overall  = clamp(so.overall_score || 0);

  // Top teal bar
  slide.addShape(prs.shapes.RECTANGLE, {
    x: 0, y: 0, w: "100%", h: 0.08,
    fill: { color: C.teal }, line: { color: C.teal }
  });

  slide.addText("Final Decision", {
    x: 0.5, y: 0.3, w: 9, h: 0.4,
    fontSize: 12, color: C.tealDim, fontFace: "Calibri", charSpacing: 4, margin: 0
  });

  // Decision banner
  slide.addShape(prs.shapes.RECTANGLE, {
    x: 1.0, y: 0.9, w: 8, h: 1.0,
    fill: { color: dColor }, line: { color: dColor }
  });
  slide.addText(decision.toUpperCase(), {
    x: 1.0, y: 0.9, w: 8, h: 1.0,
    fontSize: 30, color: C.white, bold: true,
    fontFace: "Cambria", align: "center", valign: "middle", margin: 0
  });

  // Supporting stats
  const stats = [
    { label: "Overall Score", value: `${Math.round(overall * 100)}%`, color: scoreColor(overall) },
    { label: "Rating",        value: so.rating || "—",                 color: C.white },
    { label: "Data Confidence", value: conf.overall || "—",           color: C.tealDim },
  ];
  stats.forEach((s, i) => {
    const x = 0.5 + i * 3.2;
    slide.addText(s.label, {
      x, y: 2.15, w: 3, h: 0.28,
      fontSize: 9, color: C.dimText, fontFace: "Calibri", charSpacing: 2, align: "center", margin: 0
    });
    slide.addText(s.value, {
      x, y: 2.45, w: 3, h: 0.5,
      fontSize: 20, color: s.color, bold: true, fontFace: "Cambria", align: "center", margin: 0
    });
  });

  // Rationale
  let rationale = `Assessment based on ${Math.round(overall * 100)}% overall viability with ${conf.overall || "unknown"} data confidence.`;
  if (overall >= 0.65) rationale += " Strong fundamentals support proceeding.";
  else if (overall >= 0.4) rationale += " Proceed with clear milestones and defined exit criteria.";
  else rationale += " Fundamental gaps require resolution before commitment.";

  slide.addText(rationale, {
    x: 0.5, y: 3.2, w: 9, h: 0.7,
    fontSize: 11, color: C.dimText, fontFace: "Calibri",
    align: "center", italic: true, margin: 0
  });

  // AutoResearch footer
  slide.addText("AutoResearch — AI-Powered Business Intelligence", {
    x: 0.5, y: 4.6, w: 9, h: 0.3,
    fontSize: 9, color: C.dimText, fontFace: "Calibri",
    charSpacing: 2, align: "center", margin: 0
  });
}

// ── Component helpers ─────────────────────────────────────────────────────────

function _sectionHeader(slide, prs, title, number) {
  // Teal accent left bar
  slide.addShape(prs.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.08, h: 0.85,
    fill: { color: C.teal }, line: { color: C.teal }
  });
  slide.addText(number, {
    x: 0.15, y: 0.05, w: 0.6, h: 0.35,
    fontSize: 10, color: C.dimText, fontFace: "Calibri", margin: 0
  });
  slide.addText(title, {
    x: 0.15, y: 0.38, w: 9, h: 0.42,
    fontSize: 22, color: C.navy, bold: true, fontFace: "Cambria", margin: 0
  });
  // Thin border under header
  slide.addShape(prs.shapes.LINE, {
    x: 0.15, y: 0.92, w: 9.7, h: 0,
    line: { color: C.border, width: 0.5 }
  });
}

function _metricTable(slide, prs, metrics, x, y, w, rowH) {
  metrics.forEach(([label, value], i) => {
    const ry = y + i * rowH;
    const bg = i % 2 === 0 ? C.light : C.white;
    slide.addShape(prs.shapes.RECTANGLE, {
      x, y: ry, w, h: rowH - 0.04,
      fill: { color: bg }, line: { color: C.border, width: 0.3 }
    });
    slide.addText(label, {
      x: x + 0.1, y: ry + 0.05, w: w * 0.5, h: rowH - 0.1,
      fontSize: 10, color: C.steel, bold: true, fontFace: "Calibri",
      valign: "middle", margin: 0
    });
    slide.addText(value, {
      x: x + w * 0.5, y: ry + 0.05, w: w * 0.48, h: rowH - 0.1,
      fontSize: 10, color: C.text, fontFace: "Calibri",
      valign: "middle", margin: 0
    });
  });
}

function _scoreGauge(slide, prs, score, x, y, label) {
  const s    = clamp(score);
  const sc   = scoreColor(s);
  const pct  = Math.round(s * 100);

  // Background circle
  slide.addShape(prs.shapes.OVAL, {
    x, y, w: 3.2, h: 3.2,
    fill: { color: C.light }, line: { color: C.border, width: 1 }
  });
  // Score text
  slide.addText(`${pct}%`, {
    x, y: y + 0.8, w: 3.2, h: 1.0,
    fontSize: 44, color: sc, bold: true, fontFace: "Cambria", align: "center", margin: 0
  });
  slide.addText(scoreLabel(s), {
    x, y: y + 1.85, w: 3.2, h: 0.35,
    fontSize: 13, color: sc, fontFace: "Calibri", align: "center", margin: 0
  });
  slide.addText(label, {
    x, y: y + 2.25, w: 3.2, h: 0.3,
    fontSize: 9, color: C.dimText, fontFace: "Calibri",
    charSpacing: 2, align: "center", margin: 0
  });
}

function _statsCard(slide, prs, stats, x, y, w) {
  const h = 0.35;
  stats.forEach(([label, value], i) => {
    slide.addShape(prs.shapes.RECTANGLE, {
      x, y: y + i * h, w, h: h - 0.03,
      fill: { color: i % 2 === 0 ? C.navy : "0D2035" }, line: { color: C.navy }
    });
    slide.addText(label + ": " + value, {
      x: x + 0.1, y: y + i * h + 0.04, w: w - 0.2, h: h - 0.1,
      fontSize: 9, color: C.white, fontFace: "Calibri", margin: 0
    });
  });
}

// ── Main entry point ──────────────────────────────────────────────────────────

function generatePPT(mappedData, outputPath) {
  const prs = new pptxgen();
  prs.layout = "LAYOUT_16x9";
  prs.title  = "AutoResearch Business Analysis";
  prs.author = "AutoResearch";

  buildTitleSlide(prs, mappedData);
  buildExecSummarySlide(prs, mappedData);
  buildScoreSlide(prs, mappedData);
  buildFinancialSlide(prs, mappedData);
  buildMarketSlide(prs, mappedData);
  buildCompetitiveSlide(prs, mappedData);
  buildRiskSlide(prs, mappedData);
  buildRecommendationsSlide(prs, mappedData);
  buildDecisionSlide(prs, mappedData);

  prs.writeFile({ fileName: outputPath });
  console.log(`PPT generated: ${outputPath}`);
}

// CLI entry point
if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error("Usage: node ppt_generator.js <data.json> <output.pptx>");
    process.exit(1);
  }
  const data = JSON.parse(fs.readFileSync(args[0], "utf8"));
  generatePPT(data, args[1]);
}

module.exports = { generatePPT };