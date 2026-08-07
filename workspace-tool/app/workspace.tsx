"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type Source = { title: string; provider: string; url: string; role: string; asOf?: string };
type Evidence = { label: string; value: string };
type Answer = {
  status: string;
  mode: string;
  answer: string;
  summary: string;
  evidence: Evidence[];
  sources: Source[];
  limitations: string[];
  followUps?: string[];
  quality?: { authority: string; freshness: string; coverage: string };
  retrievedAt?: string;
};
type Scope = "all" | "official" | "premium";
type Depth = "quick" | "deep";
type Tab = "answer" | "evidence" | "sources";
type HistoryItem = { question: string; scope: Scope; depth: Depth; at: string };

const prompts = [
  "Where is the solar-curtailment risk concentrated in the demo?",
  "What does the 2026-07-31 SP15 and NP15 reference forecast show?",
  "Which sources control an exact CAISO market-price answer?",
  "How should weather and outage evidence be combined?",
];

const sourceLadder = [
  ["01", "Controlling", "CAISO OASIS · EIA API v2 · FERC · NWS · CEC · CPUC"],
  ["02", "Authoritative context", "Agency publications · issuer releases · high-quality reporting"],
  ["03", "Entitled premium", "Bloomberg · ICE · S&P Global · Argus · Wood Mackenzie · NGI"],
];

const connectors = [
  { name: "CAISO + U.S. agencies", detail: "Official APIs and publications", state: "READY", tone: "ready" },
  { name: "V4 research backend", detail: "Set MARKET_INTELLIGENCE_API_URL", state: "OPTIONAL", tone: "optional" },
  { name: "OpenAI live synthesis", detail: "Server-side key; web citations", state: "OPTIONAL", tone: "optional" },
  { name: "Licensed market feeds", detail: "Entitlement + approved delivery required", state: "GATED", tone: "gated" },
];

function qualityClass(value = "") {
  const normalized = value.toLowerCase();
  if (normalized.includes("high") || normalized.includes("official") || normalized.includes("current")) return "good";
  if (normalized.includes("limited") || normalized.includes("demo")) return "warn";
  return "neutral";
}

export function MarketWorkspace() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [scope, setScope] = useState<Scope>("all");
  const [depth, setDepth] = useState<Depth>("deep");
  const [tab, setTab] = useState<Tab>("answer");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [connectorsOpen, setConnectorsOpen] = useState(false);
  const [copied, setCopied] = useState("");

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("caiso-research-history") || "[]");
      if (Array.isArray(stored)) setHistory(stored.slice(0, 8));
      const incoming = new URLSearchParams(location.search).get("q");
      if (incoming) setQuestion(incoming.slice(0, 2500));
    } catch { /* local history is optional */ }
  }, []);

  const answerPacket = useMemo(() => {
    if (!answer) return "";
    const evidence = answer.evidence.map((item) => `- ${item.label}: ${item.value}`).join("\n");
    const sources = answer.sources.map((item) => `- ${item.provider}: ${item.title} — ${item.url}`).join("\n");
    const limits = answer.limitations.map((item) => `- ${item}`).join("\n");
    return `${answer.answer}\n\n${answer.summary}\n\nEVIDENCE\n${evidence || "No structured evidence."}\n\nSOURCES\n${sources || "No cited sources."}\n\nLIMITATIONS\n${limits || "None stated."}`;
  }, [answer]);

  async function ask(value = question, nextScope = scope, nextDepth = depth) {
    const clean = value.trim();
    if (clean.length < 3) return;
    setQuestion(clean);
    setScope(nextScope);
    setDepth(nextDepth);
    setLoading(true);
    setError("");
    setAnswer(null);
    setTab("answer");
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: clean, scope: nextScope, depth: nextDepth }),
      });
      const payload = (await response.json()) as Answer & { error?: string };
      if (!response.ok) throw new Error(payload.error || "Research request failed.");
      const normalized: Answer = {
        status: payload.status || "answered",
        mode: payload.mode || "research_backend",
        answer: payload.answer || payload.summary || "Research complete.",
        summary: payload.summary || payload.answer || "",
        evidence: Array.isArray(payload.evidence) ? payload.evidence : [],
        sources: Array.isArray(payload.sources) ? payload.sources : [],
        limitations: Array.isArray(payload.limitations) ? payload.limitations : [],
        followUps: Array.isArray(payload.followUps) ? payload.followUps : [],
        quality: payload.quality,
        retrievedAt: payload.retrievedAt,
      };
      setAnswer(normalized);
      const next = [{ question: clean, scope: nextScope, depth: nextDepth, at: new Date().toISOString() }, ...history.filter((item) => item.question !== clean)].slice(0, 8);
      setHistory(next);
      localStorage.setItem("caiso-research-history", JSON.stringify(next));
      window.history.replaceState(null, "", `?q=${encodeURIComponent(clean)}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Research request failed.");
    } finally {
      setLoading(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void ask();
  }

  async function copy(value: string, label: string) {
    await navigator.clipboard.writeText(value);
    setCopied(label);
    window.setTimeout(() => setCopied(""), 1600);
  }

  async function share() {
    const url = `${location.origin}${location.pathname}?q=${encodeURIComponent(question)}`;
    if (navigator.share) await navigator.share({ title: "CAISO Market Intelligence", text: question, url });
    else await copy(url, "Link copied");
  }

  return (
    <main>
      <header className="masthead">
        <a className="brand" href="#top" aria-label="CAISO Market Intelligence home"><span className="brand-mark">C</span><span>CAISO MARKET INTELLIGENCE</span></a>
        <nav aria-label="Workspace navigation">
          <button type="button" onClick={() => setHistoryOpen(!historyOpen)}>History <span>{history.length}</span></button>
          <button type="button" onClick={() => setConnectorsOpen(!connectorsOpen)}>Data connections</button>
          <a href="https://github.com/niteesh2207/CAISO-Market-Intelligence" target="_blank" rel="noreferrer">Repository ↗</a>
        </nav>
      </header>

      {(historyOpen || connectorsOpen) && <div className="utility-tray" role="region" aria-label={historyOpen ? "Recent research" : "Data connections"}>
        {historyOpen ? <>
          <div className="tray-title"><strong>Recent research</strong><button type="button" onClick={() => { setHistory([]); localStorage.removeItem("caiso-research-history"); }}>Clear</button></div>
          {history.length === 0 ? <p>No searches saved on this device.</p> : history.map((item) => <button className="history-item" key={`${item.question}-${item.at}`} onClick={() => { setHistoryOpen(false); void ask(item.question, item.scope, item.depth); }}><span>{item.question}</span><small>{item.scope} · {item.depth}</small></button>)}
        </> : <>
          <div className="tray-title"><strong>Data connections</strong><small>Capability, not a claim of live credentials</small></div>
          <div className="connector-grid">{connectors.map((item) => <div key={item.name}><span className={`connector-state ${item.tone}`}>{item.state}</span><strong>{item.name}</strong><small>{item.detail}</small></div>)}</div>
        </>}
      </div>}

      <section className="hero" id="top">
        <div className="hero-copy"><p className="eyebrow">PRIVATE ANALYST WORKSPACE · V4.2</p><h1>One question.<br /><span>Auditable answers.</span></h1><p className="dek">Search CAISO markets across prices, curtailment, demand, generation, fuels, outages, weather, and regulation—with evidence attached.</p></div>
        <aside className="status-card" aria-label="Research controls"><span className="live-dot" /><p>RESEARCH CONTROLS ACTIVE</p><strong>Official sources first</strong><small>Freshness · provenance · limitations</small></aside>
      </section>

      <section className={`ask-panel ${answer ? "compact" : ""}`} aria-labelledby="ask-heading">
        <div className="panel-heading"><div><p className="eyebrow">UNIFIED SEARCH</p><h2 id="ask-heading">What do you need to know?</h2></div><span className="mode-pill">TRUST-FIRST MODE</span></div>
        <form onSubmit={submit}>
          <label htmlFor="question">Energy-market question</label>
          <div className="composer"><span className="search-glyph" aria-hidden="true">⌕</span><textarea id="question" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") void ask(); }} placeholder="Ask about SP15 prices, solar curtailment, demand, outages, gas, weather or market rules…" rows={answer ? 1 : 2} maxLength={2500} /><button type="submit" disabled={loading || question.trim().length < 3}>{loading ? "Researching…" : "Search →"}</button></div>
          <div className="search-controls">
            <fieldset><legend>Source scope</legend>{(["all", "official", "premium"] as Scope[]).map((item) => <button className={scope === item ? "active" : ""} type="button" key={item} onClick={() => setScope(item)}>{item === "premium" ? "Premium · entitled" : item}</button>)}</fieldset>
            <fieldset><legend>Research depth</legend>{(["quick", "deep"] as Depth[]).map((item) => <button className={depth === item ? "active" : ""} type="button" key={item} onClick={() => setDepth(item)}>{item}</button>)}</fieldset>
            <small>⌘/Ctrl + Enter to search</small>
          </div>
        </form>
        {!answer && <div className="prompt-row" aria-label="Suggested questions">{prompts.map((prompt) => <button key={prompt} type="button" onClick={() => void ask(prompt)}>{prompt}</button>)}</div>}
      </section>

      {loading && <section className="researching" aria-live="polite"><div className="research-line" /><strong>Building an evidence-first answer</strong><span>Checking authority, freshness, units and limitations…</span></section>}
      {error && <section className="error" role="alert"><strong>Request stopped</strong><p>{error}</p></section>}

      {answer && <article className="answer-card" aria-live="polite">
        <header className="result-header"><div><p className="eyebrow">RESEARCH RESULT</p><h2>{answer.answer}</h2></div><span className="mode-pill">{answer.mode.replaceAll("_", " ")}</span></header>
        <div className="result-toolbar">
          <div className="result-tabs" role="tablist">{(["answer", "evidence", "sources"] as Tab[]).map((item) => <button role="tab" aria-selected={tab === item} className={tab === item ? "active" : ""} key={item} onClick={() => setTab(item)}>{item}{item === "evidence" && ` · ${answer.evidence.length}`}{item === "sources" && ` · ${answer.sources.length}`}</button>)}</div>
          <div className="result-actions"><button type="button" onClick={() => void copy(answer.summary, "Answer copied")}>Copy answer</button><button type="button" onClick={() => void copy(answerPacket, "Packet copied")}>Copy packet</button><button type="button" onClick={() => void share()}>Share</button><span aria-live="polite">{copied}</span></div>
        </div>

        {tab === "answer" && <div className="tab-panel"><p className="answer-summary">{answer.summary}</p>
          {answer.quality && <div className="quality-strip">{Object.entries(answer.quality).map(([label, value]) => <div key={label}><span>{label}</span><strong className={qualityClass(value)}>{value}</strong></div>)}</div>}
          <div className="limitations"><h3>Known limitations</h3><ul>{answer.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
        </div>}
        {tab === "evidence" && <div className="tab-panel"><div className="evidence-grid">{answer.evidence.length ? answer.evidence.map((item) => <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong></div>) : <p>No structured values were returned. Inspect the cited sources before using the synthesis operationally.</p>}</div></div>}
        {tab === "sources" && <div className="tab-panel"><div className="source-list">{answer.sources.length ? answer.sources.map((item, index) => <a key={`${item.provider}-${item.url}`} href={item.url} target="_blank" rel="noreferrer"><b>{String(index + 1).padStart(2, "0")}</b><span><strong>{item.provider}</strong>{item.title}</span><em>{item.role}{item.asOf ? ` · ${item.asOf}` : ""} ↗</em></a>) : <p>No citations were returned. Treat the answer as unverified.</p>}</div></div>}

        {!!answer.followUps?.length && <footer className="follow-ups"><span>Keep researching</span>{answer.followUps.map((item) => <button key={item} type="button" onClick={() => void ask(item)}>{item}<b>→</b></button>)}</footer>}
      </article>}

      <section className="source-policy" id="sources"><div className="section-heading"><p className="eyebrow">QUALITY STANDARD · VERIFIED 7 AUG 2026</p><h2>Source authority is part of the answer.</h2><p>Premium means entitled server-side delivery—not scraping a paywall, terminal, subscriber page, or redistributing licensed records.</p></div><div className="source-ladder">{sourceLadder.map(([number, title, detail]) => <article key={number}><span>{number}</span><h3>{title}</h3><p>{detail}</p></article>)}</div></section>

      <footer className="site-footer"><span>CAISO Market Intelligence · V4.2</span><span>Research only · Not trading or settlement advice</span><span>Source registry verified 7 Aug 2026</span></footer>
    </main>
  );
}
