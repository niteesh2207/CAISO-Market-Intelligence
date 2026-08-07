import { NextRequest, NextResponse } from "next/server";

type Source = { title: string; provider: string; url: string; role: string; asOf?: string };
const source = {
  oasis: { title: "Open Access Same-Time Information System (OASIS)", provider: "California ISO", url: "https://www.caiso.com/systems-applications/portals-applications/open-access-same-time-information-system-oasis", role: "controlling structured source", asOf: "verified 2026-08-07" },
  today: { title: "Today's Outlook", provider: "California ISO", url: "https://www.caiso.com/todays-outlook", role: "official operating context", asOf: "verified 2026-08-07" },
  eia: { title: "API Technical Documentation", provider: "U.S. EIA", url: "https://www.eia.gov/opendata/documentation.php", role: "controlling structured source", asOf: "API v2.1.12, March 2026" },
  ferc: { title: "Understanding FERC APIs", provider: "Federal Energy Regulatory Commission", url: "https://data.ferc.gov/developer/gettingstarted/understanding-our-apis/", role: "official regulatory data", asOf: "verified 2026-08-07" },
  nws: { title: "API Web Service", provider: "National Weather Service", url: "https://www.weather.gov/documentation/services-web-api", role: "official forecast, alert and observation data", asOf: "verified 2026-08-07" },
  cec: { title: "California Energy Commission", provider: "California Energy Commission", url: "https://www.energy.ca.gov/", role: "official California energy context", asOf: "verified 2026-08-07" },
  cpuc: { title: "California Public Utilities Commission", provider: "California Public Utilities Commission", url: "https://www.cpuc.ca.gov/", role: "official California regulatory context", asOf: "verified 2026-08-07" },
  repo: { title: "CAISO Market Intelligence", provider: "GitHub", url: "https://github.com/niteesh2207/CAISO-Market-Intelligence", role: "model and source-policy record", asOf: "V4.1" },
  solar: { title: "Solar Curtailment AI Generator", provider: "GitHub", url: "https://github.com/niteesh2207/Solar-Curtailment-AI-generator", role: "verified demonstration model", asOf: "verified 2026-08-06" },
  reference: { title: "CAISO Reference Model", provider: "GitHub", url: "https://github.com/niteesh2207/CAISO-Reference-Model", role: "verified demonstration model", asOf: "verified 2026-08-06" },
} satisfies Record<string, Source>;

function packet(answer: string, summary: string, evidence: Array<{ label: string; value: string }>, sources: Source[], limitations: string[], followUps: string[] = []) {
  const live = sources.some((item) => item.asOf === "retrieved live");
  return {
    status: "answered",
    mode: "verified_evidence_pack",
    answer,
    summary,
    evidence,
    sources,
    limitations,
    followUps,
    quality: { authority: sources.some((item) => item.role.includes("official") || item.role.includes("controlling")) ? "Official / controlling" : "Verified demo", freshness: live ? "Retrieved live" : "Declared as-of", coverage: limitations.length ? "Bounded" : "Complete" },
    retrievedAt: new Date().toISOString(),
  };
}

function fallback(question: string, scope = "all") {
  const q = question.toLowerCase();
  if (scope === "premium") return packet(
    "Premium research is entitlement-gated until an approved connector is configured.",
    "This workspace will not scrape a terminal, paywall or subscriber page. Connect Bloomberg, ICE, S&P Global, Wood Mackenzie, Argus or NGI through the provider-approved server-side API, bulk, SFTP, cloud delivery or controlled import granted by your license.",
    [{ label: "Entitlement", value: "Required" }, { label: "Credential storage", value: "Server-side" }, { label: "Unlicensed scraping", value: "Blocked" }, { label: "Fallback", value: "Official sources" }],
    [source.repo],
    ["No licensed provider is connected to this deployed site.", "Retention, derived-data and redistribution rights remain provider-specific."],
    ["Which official sources can answer this question now?", "What is the approved premium connector checklist?"],
  );
  if (q.includes("curtail")) return packet(
    "The demonstration concentrates solar-curtailment risk around HE 13.",
    "For the highest-curtailment committed demo day, 2025-03-16 in balanced mode, the verified output totals 6,980 MWh and peaks at hour ending 13. Use the explanation view to connect the peak to its modeled drivers and recommended analyst action.",
    [{ label: "Demo day", value: "2025-03-16" }, { label: "Mode", value: "Balanced" }, { label: "Daily total", value: "6,980 MWh" }, { label: "Peak", value: "HE 13" }],
    [source.solar, source.repo],
    ["This is committed synthetic demonstration data, not a live CAISO curtailment forecast.", "Do not use it for bidding or settlement decisions."],
    ["Which modeled drivers explain the HE 13 peak?", "How would I replace the demo inputs with live CAISO data?"],
  );
  if (["sp15", "sp-15", "np15", "np-15", "reference"].some((term) => q.includes(term))) return packet(
    "The deterministic reference-date demo produces a transparent SP15 and NP15 hourly curve.",
    "For 2026-07-31, the verified demonstration averaged $68.31/MWh at SP15 and $71.63/MWh at NP15, with high confidence and two gas-upside flags. Exact historical or current market prices must be retrieved from CAISO OASIS.",
    [{ label: "Forecast date", value: "2026-07-31" }, { label: "SP15 average", value: "$68.31/MWh" }, { label: "NP15 average", value: "$71.63/MWh" }, { label: "Confidence", value: "High" }],
    [source.reference, source.oasis],
    ["The figures are a model demonstration, not settlement-grade prices.", "The model explicitly reports SAFE FOR TRADING: NO."],
    ["Show the limitations behind this reference forecast.", "Which OASIS dataset would validate these prices?"],
  );
  if (["bloomberg", "ice", "argus", "premium", "scrap"].some((term) => q.includes(term))) return packet(
    "Licensed market data must enter through an entitled connector—not a scraper.",
    "Bloomberg, ICE, S&P Global, Wood Mackenzie, Argus and NGI can be premium Tier 3 sources only when your organization has a valid entitlement and uses an approved server-side API, bulk, SFTP, cloud-delivery or controlled import method.",
    [{ label: "Default", value: "Disabled" }, { label: "Required", value: "Entitlement" }, { label: "Delivery", value: "Approved API" }, { label: "Scraping", value: "Prohibited" }],
    [source.repo],
    ["No premium credentials or licensed records are stored in this site.", "Provider-specific retention and redistribution terms still apply."],
    ["What is the approved premium-data connector pattern?", "Which official sources can cover this question without a license?"],
  );
  if (["source", "oasis", "price"].some((term) => q.includes(term))) return packet(
    "CAISO OASIS is the controlling source for exact CAISO market-price claims.",
    "OASIS publishes market prices, market results, system demand forecasts, transmission outages and capacity status. EIA API v2 supports broader U.S. operating and energy data; official publications provide context but do not replace controlling datasets.",
    [{ label: "Tier 1", value: "Official APIs" }, { label: "Price source", value: "CAISO OASIS" }, { label: "U.S. energy", value: "EIA API v2" }, { label: "Policy", value: "Provenance required" }],
    [source.oasis, source.eia, source.today],
    ["A source link alone is not proof of freshness; live records need interval, units, timezone, observation time and retrieval time."],
    ["What metadata must accompany an exact price?", "How should conflicting sources be resolved?"],
  );
  if (["weather", "temperature", "forecast", "heat", "wind"].some((term) => q.includes(term))) return packet(
    "Weather evidence should come from NWS and be joined to CAISO intervals explicitly.",
    "Use NWS forecasts, alerts and observations as the official weather layer. Normalize station or grid location, ISO-8601 time, timezone and forecast issue time before comparing weather with CAISO load, renewable output or price intervals.",
    [{ label: "Weather authority", value: "NWS API" }, { label: "Market authority", value: "CAISO OASIS" }, { label: "Time standard", value: "ISO-8601" }, { label: "Join key", value: "Location + interval" }],
    [source.nws, source.oasis, source.today],
    ["This evidence pack does not claim a live weather observation.", "Station-to-zone mappings require an explicit methodology."],
    ["How should weather stations map to CAISO zones?", "Which demand intervals should be compared with a heat event?"],
  );
  if (["outage", "regulation", "rule", "tariff", "ferc", "cpuc", "cec"].some((term) => q.includes(term))) return packet(
    "Regulatory and outage questions require separate controlling records.",
    "Use CAISO OASIS and official CAISO notices for operating and outage facts; use FERC for federal records and CEC or CPUC for California policy and regulatory context. Do not let a news summary replace the underlying order, docket, filing or structured market record.",
    [{ label: "Operations", value: "CAISO" }, { label: "Federal", value: "FERC" }, { label: "State energy", value: "CEC" }, { label: "State regulation", value: "CPUC" }],
    [source.oasis, source.ferc, source.cec, source.cpuc],
    ["The exact docket, order or outage interval must be supplied or retrieved live.", "Legal interpretation is outside this research tool."],
    ["Which record controls an outage claim?", "How should a FERC order be cited in the answer?"],
  );
  return packet(
    "This workspace can route CAISO and energy-market research questions.",
    "Ask about the verified solar-curtailment or reference-price demonstrations, source authority, data freshness, or premium-data controls. Configure the V4 FastAPI backend or a server-side OpenAI key to enable open-ended current research.",
    [{ label: "Public sources", value: "Active" }, { label: "Demo models", value: "2 verified" }, { label: "Provenance", value: "Required" }, { label: "Trading use", value: "Not authorized" }],
    [source.repo, source.oasis, source.eia],
    ["Open-ended live synthesis requires a configured backend or OPENAI_API_KEY.", "This fallback never invents current market values."],
    ["What can this workspace answer without credentials?", "How do I connect the V4 research backend?"],
  );
}

function outputText(payload: any): string {
  if (typeof payload.output_text === "string") return payload.output_text;
  return (payload.output || []).flatMap((item: any) => item.content || []).filter((item: any) => item.type === "output_text").map((item: any) => item.text).join("\n");
}

function citations(payload: any): Source[] {
  const seen = new Set<string>();
  const values: Source[] = [];
  for (const item of payload.output || []) for (const content of item.content || []) for (const annotation of content.annotations || []) {
    const cite = annotation.url_citation || annotation;
    if (cite?.url && !seen.has(cite.url)) {
      seen.add(cite.url);
      values.push({ title: cite.title || cite.url, provider: new URL(cite.url).hostname, url: cite.url, role: "research citation", asOf: "retrieved live" });
    }
  }
  return values;
}

async function callOpenAI(question: string, apiKey: string, scope: string, depth: string) {
  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: { authorization: `Bearer ${apiKey}`, "content-type": "application/json" },
    body: JSON.stringify({
      model: "gpt-5.6-sol",
      reasoning: { effort: depth === "deep" ? "medium" : "low" },
      text: { verbosity: depth === "deep" ? "medium" : "low" },
      tools: [{ type: "web_search" }],
      instructions: `You are a trust-first CAISO energy-market analyst. The requested source scope is ${scope} and research depth is ${depth}. Prefer controlling sources from caiso.com, oasis.caiso.com, eia.gov, nrc.gov, ferc.gov, noaa.gov, weather.gov, energy.ca.gov and cpuc.ca.gov. If scope is official, do not use secondary reporting. Otherwise supporting reporting is context only. Never scrape or imply access to licensed Bloomberg, ICE, S&P Global, Wood Mackenzie, Argus or NGI content. State units, timezone, observation time and retrieval time when available. Distinguish observation time from publication and retrieval time. If controlling evidence is unavailable, say so. Do not provide trading instructions. Answer directly in fewer than ${depth === "deep" ? 500 : 220} words.`,
      input: `Question: ${question}`,
      store: false,
    }),
  });
  if (!response.ok) throw new Error(`OpenAI research returned ${response.status}.`);
  const payload = await response.json();
  return packet(outputText(payload) || "No answer was returned.", "Current web research was synthesized under the workspace source policy.", [], citations(payload), ["Verify exact prices and settlement facts against the cited controlling dataset before operational use."], ["Which source most strongly controls this answer?", "What evidence would change this conclusion?"]);
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const question = typeof body.question === "string" ? body.question.trim() : "";
    const scope = ["all", "official", "premium"].includes(body.scope) ? body.scope : "all";
    const depth = ["quick", "deep"].includes(body.depth) ? body.depth : "deep";
    if (question.length < 3 || question.length > 2500) return NextResponse.json({ error: "Enter a question between 3 and 2,500 characters." }, { status: 400 });
    const backend = process.env.MARKET_INTELLIGENCE_API_URL;
    if (backend) {
      try {
        const response = await fetch(`${backend.replace(/\/$/, "")}/api/search`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ question, allow_web_fallback: scope !== "premium", source_scope: scope, research_depth: depth }), signal: AbortSignal.timeout(55000) });
        if (response.ok) return NextResponse.json({ ...(await response.json()), mode: "v4_research_backend" });
      } catch { /* use another safe path */ }
    }
    if (process.env.OPENAI_API_KEY && scope !== "premium") {
      try { return NextResponse.json(await callOpenAI(question, process.env.OPENAI_API_KEY, scope, depth)); } catch { /* deterministic evidence remains available */ }
    }
    return NextResponse.json(fallback(question, scope));
  } catch {
    return NextResponse.json({ error: "The request could not be parsed." }, { status: 400 });
  }
}
