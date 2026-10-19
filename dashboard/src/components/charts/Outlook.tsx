"use client";

import { useRef, useState } from "react";
import { scaleLinear } from "d3-scale";
import { Frame, niceTicks, Tip, useTip, useView, useWidth } from "../chart";
import { pct, usd } from "@/lib/format";
import type { ForecastT, QualityT } from "@/lib/schema";

const ACTUAL = "var(--teal)";
const FORE = "var(--ochre)";

const METHOD_NAMES: Record<string, string> = {
  'seasonal-naive': 'same quarter last year',
  'seasonal-drift': 'seasonal pattern with recent annual growth',
  'seasonal-trend': 'trend with quarter effects',
  naive: "same as last year",
  drift: "recent growth continues",
  "log-trend": "four-year trend",
};

/** Actual spend, then a two-year forecast with the range the method missed by in its backtest. */
export function ForecastChart({ data, years, scope }: { data: ForecastT[string]; years: number[]; scope: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [box, w] = useWidth<HTMLDivElement>();
  const { tip, atPointer, atElement, hide } = useTip(host);
  const [view, setView] = useView();

  const H = 290;
  const m = { l: 52, r: 72, t: 26, b: 28 };
  const iw = w - m.l - m.r;
  const ih = H - m.t - m.b;
  const allYears = [...years, ...data.forecast.map((f) => f.year)];
  const maxV = Math.max(...data.actual, ...data.forecast.map((f) => f.high));
  const { top, ticks } = niceTicks(maxV);
  const x = scaleLinear().domain([allYears[0], allYears[allYears.length - 1]]).range([0, iw]);
  const y = scaleLinear().domain([0, top]).range([ih, 0]);
  const lastA = data.actual.length - 1;
  const actualPath = data.actual.map((v, i) => `${i ? "L" : "M"}${x(years[i]).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const forePts = [{ year: years[lastA], spend: data.actual[lastA], low: data.actual[lastA], high: data.actual[lastA] }, ...data.forecast];
  const forePath = forePts.map((f, i) => `${i ? "L" : "M"}${x(f.year).toFixed(1)},${y(f.spend).toFixed(1)}`).join(" ");
  const band = `${forePts.map((f, i) => `${i ? "L" : "M"}${x(f.year).toFixed(1)},${y(f.high).toFixed(1)}`).join(" ")} ${[...forePts].reverse().map((f) => `L${x(f.year).toFixed(1)},${y(f.low).toFixed(1)}`).join(" ")} Z`;
  const chosen = data.quarterly.methods.find((b) => b.chosen);
  const naive = data.quarterly.methods.find((b) => b.method === "seasonal-naive");
  const last = data.forecast[data.forecast.length - 1];

  return (
    <Frame
      title={`Where spend may go, ${scope}`}
      sub={chosen && naive ? `Method selected before the test: ${METHOD_NAMES[chosen.method] ?? chosen.method}. Test WAPE ${chosen.test.wape?.toFixed(1)}%, against ${naive.test.wape?.toFixed(1)}% for same quarter last year.` : undefined}
      view={view}
      onView={setView}
      legend={
        <ul className="legend" aria-label="Legend">
          <li><i className="line" style={{ background: ACTUAL }} />Actual</li>
          <li><i className="line" style={{ background: FORE }} />Forecast</li>
          <li><i style={{ background: FORE, opacity: 0.22 }} />Range from backtest errors</li>
        </ul>
      }
      source="Annual forecasts sum eight quarterly predictions. Bands are sums of quarterly empirical error bounds, not calibrated annual confidence intervals. See the independent test and quarterly detail below."
      table={
        <table className="tbl">
          <caption>Forecast and backtest, {scope}</caption>
          <thead><tr><th>Year</th><th className="n">Spend</th><th className="n">Low</th><th className="n">High</th></tr></thead>
          <tbody>
            {years.map((yr, i) => (<tr key={yr}><td>{yr} (actual)</td><td className="n">{usd(data.actual[i])}</td><td className="n" /><td className="n" /></tr>))}
            {data.forecast.map((f) => (<tr key={f.year} className="hl"><td>{f.year} (forecast)</td><td className="n">{usd(f.spend)}</td><td className="n">{usd(f.low)}</td><td className="n">{usd(f.high)}</td></tr>))}
            {data.backtest.map((b) => (<tr key={b.method}><td colSpan={3}>Backtest: {METHOD_NAMES[b.method] ?? b.method}{b.chosen ? " (used)" : ""}</td><td className="n">{b.mape.toFixed(1)}% average miss</td></tr>))}
          </tbody>
        </table>
      }
    >
      <div ref={host} style={{ position: "relative" }}>
        <div ref={box}>
          <svg className="svg" width={w} height={H} role="img" aria-label={`Spend ${usd(data.actual[0])} in ${years[0]}, ${usd(data.actual[lastA])} in ${years[lastA]}, forecast ${usd(last.spend)} in ${last.year} with a range of ${usd(last.low)} to ${usd(last.high)}.`}>
            <g transform={`translate(${m.l},${m.t})`}>
              {ticks.map((t) => (
                <g key={t}>
                  <line className="grid" x1={0} x2={iw} y1={y(t)} y2={y(t)} />
                  <text x={-8} y={y(t)} dy="0.32em" textAnchor="end" className="t-mute">{t === 0 ? "$0" : usd(t, 0)}</text>
                </g>
              ))}
              {allYears.map((yr) => (<text key={yr} x={x(yr)} y={ih + 18} textAnchor="middle" className="t-mute">{yr}</text>))}
              <path d={band} style={{ fill: FORE, opacity: 0.18 }} />
              <path d={actualPath} fill="none" style={{ stroke: ACTUAL }} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
              <path d={forePath} fill="none" style={{ stroke: FORE }} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
              {data.actual.map((v, i) => {
                const rows = [{ label: "Actual", value: usd(v), color: ACTUAL }];
                return (
                  <g key={years[i]}>
                    <circle cx={x(years[i])} cy={y(v)} r={4} style={{ fill: ACTUAL, stroke: "var(--paper)", strokeWidth: 2 }} />
                    <circle cx={x(years[i])} cy={y(v)} r={14} fill="transparent" tabIndex={0} role="img" aria-label={`${years[i]}: ${usd(v)}`}
                      onPointerMove={atPointer(String(years[i]), rows)} onPointerLeave={hide} onFocus={atElement(String(years[i]), rows)} onBlur={hide} />
                  </g>
                );
              })}
              {data.forecast.map((f) => {
                const rows = [{ label: "Forecast", value: usd(f.spend), color: FORE }, { label: "Range", value: `${usd(f.low)} to ${usd(f.high)}` }];
                return (
                  <g key={f.year}>
                    <circle cx={x(f.year)} cy={y(f.spend)} r={4} style={{ fill: FORE, stroke: "var(--paper)", strokeWidth: 2 }} />
                    <circle cx={x(f.year)} cy={y(f.spend)} r={14} fill="transparent" tabIndex={0} role="img" aria-label={`${f.year} forecast: ${usd(f.spend)}, range ${usd(f.low)} to ${usd(f.high)}`}
                      onPointerMove={atPointer(`${f.year} forecast`, rows)} onPointerLeave={hide} onFocus={atElement(`${f.year} forecast`, rows)} onBlur={hide} />
                  </g>
                );
              })}
              <text x={x(years[lastA])} y={y(data.actual[lastA]) - 12} textAnchor="middle" className="t-strong">{usd(data.actual[lastA])}</text>
              <text x={x(last.year) + 10} y={y(last.spend) + 4} className="t-strong">{usd(last.spend)}</text>
              <line className="axis" x1={0} x2={iw} y1={ih} y2={ih} />
            </g>
          </svg>
          <Tip tip={tip} width={w} />
        </div>
      </div>
    </Frame>
  );
}

const BADGE: Record<string, [string, string]> = { pass: ["b-pass", "✓"], warn: ["b-warn", "!"], fail: ["b-fail", "✕"], info: ["b-info", "i"] };

/** The data-quality scorecard: every check, the number it measured, and the rule it was held to. */
export function QualityTable({ quality }: { quality: QualityT }) {
  const [open, setOpen] = useState<string | null>(null);
  const counts = { pass: 0, warn: 0, fail: 0, info: 0 } as Record<string, number>;
  quality.checks.forEach((c) => (counts[c.status] += 1));
  const wf = quality.waterfall;
  const order = ["fail", "warn", "info", "pass"];
  const checks = [...quality.checks].sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status) || a.id.localeCompare(b.id));
  return (
    <div className="stack">
      <div>
        <p className="note" style={{ margin: "0 0 14px" }}>
          <b>{counts.pass} pass, {counts.warn} warn, {counts.fail} fail, {counts.info} info</b> across {quality.checks.length} checks. A warning is a known limit that is measured and explained, not ignored.
        </p>
        <div className="tbl-wrap">
          <table className="tbl">
            <caption className="sr-only">Data-quality checks</caption>
            <thead><tr><th>Check</th><th>Result</th><th>Status</th><th className="n">Spend touched</th></tr></thead>
            <tbody>
              {checks.map((c) => {
                const [cls, glyph] = BADGE[c.status];
                const isOpen = open === c.id;
                return (
                  <tr key={c.id}>
                    <td style={{ maxWidth: 380 }}>
                      <button type="button" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : c.id)} style={{ font: "inherit", background: "none", border: 0, padding: 0, textAlign: "left", cursor: "pointer", color: "var(--ink)" }}>
                        <span className="nm">{c.id}</span> {c.name}
                      </button>
                      {isOpen && <div style={{ marginTop: 6, color: "var(--ink-2)", fontSize: 13 }}>{c.note || "No further note."} <br /><span style={{ color: "var(--ink-3)" }}>Rule: {c.rule}</span></div>}
                    </td>
                    <td style={{ maxWidth: 340 }}>{c.result}</td>
                    <td><span className={`badge ${cls}`}><i aria-hidden="true">{glyph}</i>{c.status.toUpperCase()}</span></td>
                    <td className="n">{c.dollars == null ? "" : usd(c.dollars)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      <Frame
        title="How much spend each harmonising step recovers"
        sub="Share of national spend (all years) by how its product was identified."
        source="Exact pack: the NDC is in the FDA directory. Same product: the labeler and product code match even though that pack is not listed. Not in the FDA directory: the Medicaid product list knows the NDC but the FDA directory does not (mostly discontinued products)."
        table={<table className="tbl"><tbody>{wf.map((r) => (<tr key={r.stage}><td>{r.stage}</td><td className="n">{pct(r.sharePct / 100, 2)}</td><td className="n">{usd(r.dollars)}</td></tr>))}</tbody></table>}
      >
        <div role="img" aria-label={`Match waterfall: ${wf.map((r) => `${r.stage} ${r.sharePct.toFixed(1)}%`).join(", ")}`} style={{ display: "flex", height: 22, gap: 2, margin: "6px 0 10px" }}>
          {wf.map((r, i) => (<div key={r.stage} title={`${r.stage}: ${r.sharePct.toFixed(2)}%`} style={{ flex: `${Math.max(r.sharePct, 0.6)} 1 0`, background: ["var(--teal)", "var(--seq-3)", "var(--ochre)", "var(--rust)"][i % 4], borderRadius: 3 }} />))}
        </div>
        <ul className="legend">{wf.map((r, i) => (<li key={r.stage}><i style={{ background: ["var(--teal)", "var(--seq-3)", "var(--ochre)", "var(--rust)"][i % 4] }} />{r.stage}: {r.sharePct.toFixed(r.sharePct < 1 ? 2 : 1)}%</li>))}</ul>
      </Frame>
    </div>
  );
}
