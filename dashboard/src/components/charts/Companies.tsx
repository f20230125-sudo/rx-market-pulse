"use client";

import { useRef } from "react";
import { scaleLinear } from "d3-scale";
import { fit, Frame, roundedBar, Tip, useTip, useView, useWidth } from "../chart";
import { dateLabel, pct, signedPct, signedUsd, usd } from "@/lib/format";
import { cagr, type OwnerRow } from "@/lib/derive";
import type { ProductsT } from "@/lib/schema";

const BAR = "var(--muted-mark)";
const SEL = "var(--teal)";

/** Companies by 2025 spend (bars) with the first year as a ring. Select a company to see its products. */
export function OwnerBars({ rows, selected, onSelect, years, scope }: { rows: OwnerRow[]; selected: string; onSelect: (o: string) => void; years: [number, number]; scope: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [box, w] = useWidth<HTMLDivElement>();
  const { tip, atPointer, atElement, hide } = useTip(host);
  const [view, setView] = useView();

  const rowH = 27;
  const labelW = Math.min(188, Math.max(146, w * 0.4));
  const valueW = 62;
  const H = rows.length * rowH + 8;
  const max = Math.max(...rows.flatMap((r) => [r.spend0, r.spend1]), 1);
  const plotW = Math.max(60, w - labelW - valueW);
  const x = scaleLinear().domain([0, max]).range([0, plotW]);

  return (
    <Frame
      title={`Companies by spend, ${scope}`}
      sub={`Annual spend in ${years[1]} (bar) and ${years[0]} (ring). Owner = parent company today. Select one to see its products.`}
      view={view}
      onView={setView}
      legend={
        <ul className="legend" aria-label="Legend">
          <li><i style={{ background: BAR }} />{years[1]} spend</li>
          <li><i className="ring" style={{ borderColor: "var(--ink)" }} />{years[0]} spend</li>
        </ul>
      }
      source="Manufacturer names are harmonised: spelling variants merge, and completed acquisitions (for example Celgene into Bristol Myers Squibb) roll up. Spin-offs such as Organon stay separate from Merck."
      table={
        <table className="tbl">
          <caption>Companies by spend, {scope}</caption>
          <thead><tr><th>#</th><th>Company</th><th className="n">{years[0]}</th><th className="n">{years[1]}</th><th className="n">Change</th><th className="n">Brand share</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.owner} className={r.owner === selected ? "hl" : undefined}>
                <td>{r.rank}</td><td className="nm">{r.owner}</td><td className="n">{usd(r.spend0)}</td><td className="n">{usd(r.spend1)}</td>
                <td className="n">{signedUsd(r.spend1 - r.spend0)}</td><td className="n">{pct(r.spend1 ? r.brandSpend1 / r.spend1 : 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <div ref={host} style={{ position: "relative" }}>
        <div ref={box}>
          <svg className="svg" width={w} height={H} role="group" aria-label={`Companies by spend, ${scope}`}>
            <g transform="translate(0,4)">
              {rows.map((r, i) => {
                const y0 = i * rowH;
                const isSel = r.owner === selected;
                const rows2 = [
                  { label: String(years[0]), value: usd(r.spend0) },
                  { label: String(years[1]), value: usd(r.spend1) },
                  { label: "Change", value: signedUsd(r.spend1 - r.spend0) },
                  { label: "Brand share", value: pct(r.spend1 ? r.brandSpend1 / r.spend1 : 0) },
                ];
                return (
                  <g
                    key={r.owner} tabIndex={0} role="button" aria-pressed={isSel}
                    aria-label={`${r.owner}, number ${r.rank}: ${usd(r.spend1)} in ${years[1]}, ${usd(r.spend0)} in ${years[0]}. ${isSel ? "Selected." : "Press to see its products."}`}
                    onClick={() => onSelect(r.owner)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(r.owner); } }}
                    onPointerMove={atPointer(r.owner, rows2)} onPointerLeave={hide}
                    onFocus={atElement(r.owner, rows2)} onBlur={hide}
                  >
                    {isSel && <rect x={0} y={y0 - 2} width={w} height={rowH - 1} style={{ fill: "var(--teal-wash)" }} />}
                    <text x={labelW - 12} y={y0 + 13} textAnchor="end" className={isSel ? "t-strong" : undefined}>{fit(r.owner, labelW - 16)}</text>
                    <path d={roundedBar(labelW, y0 + 4, Math.max(1.5, x(r.spend1)), 15, 4, "right")} style={{ fill: isSel ? SEL : BAR }} />
                    <circle cx={labelW + x(r.spend0)} cy={y0 + 11.5} r={5} style={{ fill: "var(--paper)", stroke: "var(--ink)", strokeWidth: 2 }} />
                    <text x={labelW + Math.max(x(r.spend1), x(r.spend0) + 6) + 12} y={y0 + 16} className="t-strong">{usd(r.spend1)}</text>
                  </g>
                );
              })}
              <line className="axis" x1={labelW} x2={labelW} y1={-2} y2={rows.length * rowH} />
            </g>
          </svg>
          <Tip tip={tip} width={w} />
        </div>
      </div>
    </Frame>
  );
}

function Spark({ values, width = 116, height = 28 }: { values: number[]; width?: number; height?: number }) {
  const max = Math.max(...values, 1);
  const pad = 4;
  const sx = scaleLinear().domain([0, values.length - 1]).range([pad, width - pad]);
  const sy = scaleLinear().domain([0, max]).range([height - pad, pad]);
  const d = values.map((v, i) => `${i ? "L" : "M"}${sx(i).toFixed(1)},${sy(v).toFixed(1)}`).join(" ");
  const last = values.length - 1;
  return (
    <svg width={width} height={height} role="img" aria-label={`Trend from ${usd(values[0])} to ${usd(values[last])}`}>
      <path d={d} fill="none" style={{ stroke: "var(--teal)" }} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={sx(last)} cy={sy(values[last])} r={3.5} style={{ fill: "var(--teal)", stroke: "var(--paper)", strokeWidth: 2 }} />
    </svg>
  );
}

function protection(p: ProductsT["owners"][string][number]): { text: string; sub?: string; kind: "date" | "none" | "bio" } {
  if (p.status.startsWith("Biologic")) return { text: "Biologic", sub: "not in the Orange Book", kind: "bio" };
  if (p.coreEnd) {
    const later = p.lastEnd && p.lastEnd.slice(0, 7) !== p.coreEnd.slice(0, 7) ? `last listed ${dateLabel(p.lastEnd)}` : undefined;
    return { text: `Core protection to ${dateLabel(p.coreEnd)}`, sub: later, kind: "date" };
  }
  if (p.status.startsWith("Listed protection has ended")) return { text: "Listed protection has ended", kind: "none" };
  if (p.status.startsWith("No patent")) return { text: "No patent or exclusivity listed", kind: "none" };
  return { text: "No Orange Book entry", kind: "none" };
}

/** A company's largest brands: seven-year trend, current spend and when protection ends. */
export function ProductRows({ owner, items, years }: { owner: string; items: ProductsT["owners"][string]; years: number[] }) {
  const [view, setView] = useView();
  const first = years[0];
  const last = years[years.length - 1];
  const rows = items.slice(0, 10);
  return (
    <Frame
      title={`${owner}: largest brands in this data`}
      sub={`Brand-name products only. Each line is scaled to its own peak, ${first} to ${last}.`}
      view={view}
      onView={setView}
      source="Protection dates come from the FDA Orange Book as of its latest file. They show where legal protection ends, not when a generic will launch. Biologics are not in the Orange Book."
      table={
        <table className="tbl">
          <caption>{owner}: brands by spend</caption>
          <thead><tr><th>Brand</th><th>Area</th>{years.map((y) => <th key={y} className="n">{y}</th>)}<th>Protection</th></tr></thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.family}>
                <td className="nm">{p.family}</td><td>{p.area}</td>
                {p.spend.map((v, i) => <td key={i} className="n">{usd(v)}</td>)}
                <td>{protection(p).text}{protection(p).sub ? `, ${protection(p).sub}` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      {rows.length === 0 ? (
        <p className="note">No brand-name products for this company in the data.</p>
      ) : (
        <div className="tbl-wrap">
          <table className="tbl">
            <caption className="sr-only">{owner}: brands by spend</caption>
            <thead><tr><th>Brand</th><th>Trend</th><th className="n">{last} spend</th><th className="n hide-sm">Per year</th><th className="hide-sm">Protection</th></tr></thead>
            <tbody>
              {rows.map((p) => {
                const g = cagr(p.spend[0], p.spend[p.spend.length - 1], p.spend.length - 1);
                const pr = protection(p);
                return (
                  <tr key={p.family}>
                    <td><span className="nm">{p.family}</span><br /><span style={{ color: "var(--ink-3)", fontSize: 12.5 }}>{p.area}</span><span className="only-sm" style={{ color: pr.kind === "date" ? "var(--ink)" : "var(--ink-3)", fontSize: 12.5 }}><br />{pr.text}{pr.sub ? `, ${pr.sub}` : ""}</span></td>
                    <td><Spark values={p.spend} /></td>
                    <td className="n">{usd(p.spend[p.spend.length - 1])}</td>
                    <td className="n hide-sm">{g == null ? "new" : signedPct(g, 0)}</td>
                    <td className="hide-sm" style={{ color: pr.kind === "date" ? "var(--ink)" : "var(--ink-3)", minWidth: 176 }}>{pr.text}{pr.sub && (<><br /><span style={{ color: "var(--ink-3)", fontSize: 12.5 }}>{pr.sub}</span></>)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Frame>
  );
}
