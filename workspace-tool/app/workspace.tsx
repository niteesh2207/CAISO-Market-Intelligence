"use client";

import { FormEvent, useState } from "react";

type Source = { title: string; provider: string; url: string; role: string; asOf?: string };
type Answer = {
  status: string;
  mode: string;
  answer: string;
  summary: string;
  evidence: Array<{ label: string; value: string }>;
  sources: Source[];
  limitations: string[];
};

const prompts = [
  "Where is the solar-curtailment risk concentrated in the demo?",
  "What does the 2026-07-31 SP15 and NP15 reference forecast show?",
  "Which sources control an exact CAISO market-price answer?",
  "Can you scrape Bloomberg or ICE for me?",
];

const sourceLadder = [
  ["01", "Controlling", "CAISO OASIS · EIA API v2 · NRC · FERC · NOAA"],
  ["02", "Authoritative context", "Agency publications · issuer releases · Reuters context"],
  ["03", "Entitled premium", "Bloomberg · ICE · S&P Global · Argus · Wood Mackenzie"],
];

export function MarketWorkspace() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function ask(value = question) {
    const clean = value.trim();
    if (clean.length < 3) return;
    setQuestion(clean);
    setLoading(true);
    setError("");
    setAnswer(null);
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: clean }),
      });
      const payload = (await response.json()) as Answer & { error?: string };
      if (!response.ok) throw new Error(payload.error || "Research request failed.");
      setAnswer(payload);
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

  return (
    <main>
      <header className="masthead">
        <a className="brand" href="#top" aria-label="CAISO Market Intelligence home">
          <span className="brand-mark">C</span>
          <span>CAISO MARKET INTELLIGENCE</span>
        </a>
        <nav aria-label="Workspace navigation">
          <a href="#sources">Source policy</a>
          <a href="https://github.com/niteesh2207/CAISO-Market-Intelligence" target="_blank" rel="noreferrer">Repository ↗</a>
        </nav>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow">PRIVATE ANALYST WORKSPACE · V4.1</p>
          <h1>Ask the market.<br /><span>Inspect the evidence.</span></h1>
          <p className="dek">A trust-first research surface for CAISO prices, curtailment, demand, generation, fuels, outages, weather, and regulation.</p>
        </div>
        <aside className="status-card" aria-label="Research controls">
          <span className="live-dot" />
          <p>RESEARCH CONTROLS ACTIVE</p>
          <strong>Official sources first</strong>
          <small>Freshness · provenance · limitations</small>
        </aside>
      </section>

      <section className="ask-panel" aria-labelledby="ask-heading">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">WORKSPACE</p>
            <h2 id="ask-heading">What do you need to know?</h2>
          </div>
          <span className="mode-pill">TRUST-FIRST MODE</span>
        </div>
        <form onSubmit={submit}>
          <label htmlFor="question">Energy-market question</label>
          <div className="composer">
            <textarea id="question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about SP15 day-ahead prices, solar curtailment, demand, outages, gas or market rules…" rows={3} maxLength={2500} />
            <button type="submit" disabled={loading || question.trim().length < 3}>{loading ? "Researching…" : "Run research →"}</button>
          </div>
        </form>
        <div className="prompt-row" aria-label="Suggested questions">
          {prompts.map((prompt) => <button key={prompt} type="button" onClick={() => void ask(prompt)}>{prompt}</button>)}
        </div>
      </section>

      {error && <section className="error" role="alert"><strong>Request stopped</strong><p>{error}</p></section>}

      {answer && (
        <article className="answer-card" aria-live="polite">
          <header>
            <div><p className="eyebrow">RESEARCH RESULT</p><h2>{answer.answer}</h2></div>
            <span className="mode-pill">{answer.mode.replaceAll("_", " ")}</span>
          </header>
          <p className="answer-summary">{answer.summary}</p>
          {answer.evidence.length > 0 && <div className="evidence-grid">{answer.evidence.map((item) => <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong></div>)}</div>}
          <div className="answer-columns">
            <section>
              <h3>Source record</h3>
              <div className="source-list">{answer.sources.map((source) => <a key={`${source.provider}-${source.url}`} href={source.url} target="_blank" rel="noreferrer"><span><b>{source.provider}</b>{source.title}</span><em>{source.role}{source.asOf ? ` · ${source.asOf}` : ""} ↗</em></a>)}</div>
            </section>
            <section>
              <h3>Limitations</h3>
              <ul>{answer.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
            </section>
          </div>
        </article>
      )}

      <section className="source-policy" id="sources">
        <div className="section-heading"><p className="eyebrow">QUALITY STANDARD</p><h2>Source authority is part of the answer.</h2><p>Premium means entitled delivery—not scraping a paywall, terminal, or subscriber page.</p></div>
        <div className="source-ladder">{sourceLadder.map(([number, title, detail]) => <article key={number}><span>{number}</span><h3>{title}</h3><p>{detail}</p></article>)}</div>
      </section>

      <footer>
        <span>CAISO Market Intelligence · V4.1</span>
        <span>Research only · Not trading or settlement advice</span>
        <span>Source policy verified 7 Aug 2026</span>
      </footer>
    </main>
  );
}
