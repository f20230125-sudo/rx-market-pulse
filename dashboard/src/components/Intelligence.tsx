"use client";

import { useState } from "react";
import Link from "next/link";
import { EXAMPLES, type Reply } from "@/lib/intelligence/agent";
import { ThemeToggle } from "./ThemeToggle";

const names: Record<string, string> = {
  market_summary: "Market summary",
  growth_bridge: "Growth contributions",
  rank_territories: "Territory ranking",
  product_pipeline: "MSD product pipeline",
  forecast_outlook: "Forecast and test",
};
function value(v: number | string, unit: string) {
  if (typeof v === "string") return v;
  if (unit === "USD")
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(v);
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(v)} ${unit}`;
}

export function Intelligence({ mode }: { mode: string }) {
  const [question, setQuestion] = useState(EXAMPLES[0]);
  const [reply, setReply] = useState<Reply | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function ask(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setReply(null);
    try {
      const response = await fetch("/api/intelligence", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? "The request failed.");
      setReply(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The request failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <a className="skip" href="#main">
        Skip to the analyst
      </a>
      <header className="mast">
        <div className="shell">
          <div className="mast-top">
            <p className="kicker">
              <b>Rx Market Pulse</b> · Commercial intelligence
            </p>
            <ThemeToggle />
          </div>
          <h1>Ask the evidence.</h1>
          <p className="lede">
            Explore pharmaceutical spending, territory priorities and MSD’s
            registered pipeline. Every figure comes from a calculation you can
            inspect.
          </p>
          <p>
            <Link href="/">Read the market report</Link> ·{" "}
            <a href="https://trial-pipeline-benchmark.vercel.app">
              Read the pipeline report
            </a>
          </p>
        </div>
      </header>
      <main
        id="main"
        className="shell"
        style={{ paddingTop: 32, paddingBottom: 64, maxWidth: 1000 }}
      >
        <p className="note">
          US Medicaid, 2019–2025, before manufacturer rebates. Pipeline
          snapshot: 14 October 2026.{" "}
          {mode === "guided"
            ? "Guided mode uses supported question patterns; no language model is connected."
            : "A language model chooses which calculations to run. Final figures are taken directly from those calculations."}
        </p>
        <form onSubmit={ask} className="stack" style={{ gap: 16 }}>
          <label htmlFor="question">
            <b>Your question</b>
          </label>
          <textarea
            id="question"
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={1000}
            required
            minLength={5}
            style={{
              width: "100%",
              font: "inherit",
              padding: 14,
              color: "var(--ink)",
              background: "var(--paper)",
              border: "1px solid var(--rule)",
              borderRadius: 6,
            }}
          />
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <button
              type="submit"
              disabled={busy}
              style={{
                font: "inherit",
                padding: "10px 18px",
                background: "var(--teal)",
                color: "var(--paper)",
                border: "1px solid var(--teal)",
                borderRadius: 6,
                cursor: busy ? "wait" : "pointer",
              }}
            >
              {busy ? "Checking the evidence…" : "Ask the analyst"}
            </button>
            <span role="status" aria-live="polite">
              {busy ? "This can take a minute when a model is connected." : ""}
            </span>
          </div>
        </form>
        <details style={{ margin: "20px 0" }}>
          <summary>Questions to try</summary>
          <ul>
            {EXAMPLES.map((q) => (
              <li key={q}>
                <button
                  type="button"
                  onClick={() => setQuestion(q)}
                  style={{
                    font: "inherit",
                    textAlign: "left",
                    background: "transparent",
                    border: 0,
                    padding: "8px 0",
                    color: "var(--ink)",
                    cursor: "pointer",
                    textDecoration: "underline",
                  }}
                >
                  {q}
                </button>
              </li>
            ))}
          </ul>
        </details>
        {error && <p role="alert">{error}</p>}
        {reply && (
          <section
            aria-label="Analyst answer"
            className="stack"
            style={{ borderTop: "1px solid var(--rule)", paddingTop: 24 }}
          >
            <h2 style={{ fontSize: 26, margin: 0 }}>
              {reply.refused
                ? "Outside the available evidence"
                : "What the evidence shows"}
            </h2>
            <p>{reply.message}</p>
            {!reply.refused && (
              <dl>
                {reply.facts.map((f) => (
                  <div
                    key={f.id}
                    style={{
                      padding: "12px 0",
                      borderBottom: "1px solid var(--rule)",
                    }}
                  >
                    <dt>{f.label}</dt>
                    <dd style={{ margin: 0, fontWeight: 600, fontSize: 24 }}>
                      {value(f.value, f.unit)}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
            {reply.evidence.map((e, i) => (
              <details key={i}>
                <summary>
                  {i + 1}. {names[e.tool] ?? e.tool} · {e.period}
                </summary>
                <p>
                  Selection:{" "}
                  {Object.entries(e.filters)
                    .map(([k, v]) => `${k}: ${String(v)}`)
                    .join(" · ")}
                </p>
                <ul>
                  {e.notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
                {e.rows.length > 0 && (
                  <div className="tbl-wrap">
                    <table className="tbl">
                      <caption>
                        Supporting records · showing{" "}
                        {Math.min(10, e.rows.length)} of {e.rows.length}
                      </caption>
                      <thead>
                        <tr>
                          {Object.keys(e.rows[0])
                            .filter((k) => k !== "url")
                            .map((k) => (
                              <th key={k}>{k}</th>
                            ))}
                        </tr>
                      </thead>
                      <tbody>
                        {e.rows.slice(0, 10).map((row, j) => (
                          <tr key={j}>
                            {Object.entries(row)
                              .filter(([k]) => k !== "url")
                              .map(([k, v]) => (
                                <td key={k}>
                                  {k === "study" &&
                                  typeof row.url === "string" ? (
                                    <a href={row.url}>{String(v)}</a>
                                  ) : typeof v === "number" ? (
                                    value(v, "")
                                  ) : v === null ? (
                                    "—"
                                  ) : (
                                    String(v)
                                  )}
                                </td>
                              ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <ul>
                  {e.sources.map((s) => (
                    <li key={s.url}>
                      <a href={s.url}>{s.title}</a> · snapshot {s.asOf}
                    </li>
                  ))}
                </ul>
              </details>
            ))}
            <p className="note">
              {reply.mode === "model"
                ? `Model: ${reply.model} · ${reply.usage.calls} reasoning calls`
                : "Guided question parser"}{" "}
              · Facts are rendered from observed tool values. Pipeline counts
              describe registered studies, not expected approvals.
            </p>
          </section>
        )}
      </main>
    </>
  );
}
