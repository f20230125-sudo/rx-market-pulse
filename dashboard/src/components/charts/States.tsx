"use client";

import { useMemo, useRef, useState } from "react";
import { quantile } from "d3-array";
import { Frame, Tip, useTip, useView, useWidth } from "../chart";
import { dollars, pct, signedPct, usd } from "@/lib/format";
import { TILE_GRID, type StateRow } from "@/lib/derive";

const BINS = ["var(--seq-1)", "var(--seq-2)", "var(--seq-3)", "var(--seq-4)", "var(--seq-5)"];

type SortKey = "perEnrollee" | "spend" | "growth" | "name";

/** A tile map of the 51 states coloured by spend per enrollee; states that changed how they report are outlined. */
export function TileMap({ rows, year, lookback, scope, years, onYear }: { rows: StateRow[]; year: number; lookback: number; scope: string; years: number[]; onYear: (y: number) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const [box, w] = useWidth<HTMLDivElement>();
  const { tip, atPointer, atElement, hide } = useTip(host);
  const [view, setView] = useView();
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "perEnrollee", dir: -1 });

  const vals = rows.map((r) => r.perEnrollee).filter((v): v is number => v != null).sort((a, b) => a - b);
  const cuts = [0.2, 0.4, 0.6, 0.8].map((q) => quantile(vals, q) ?? 0);
  const bin = (v: number | null) => (v == null ? -1 : cuts.filter((c) => v > c).length);
  const edges = [vals[0] ?? 0, ...cuts, vals[vals.length - 1] ?? 0];

  const ts = Math.min(60, Math.floor((w - 4) / 11));
  const gap = 3;
  const H = ts * 8 + 4;
  const sorted = [...rows].sort((a, b) => {
    const k = sort.key;
    if (k === "name") return a.name.localeCompare(b.name) * sort.dir;
    const av = (a[k] ?? -Infinity) as number;
    const bv = (b[k] ?? -Infinity) as number;
    return (av - bv) * sort.dir;
  });
  const flagged = rows.filter((r) => r.flagged);
  const head = (key: SortKey, label: string, num = true) => (
    <th className={num ? "n" : undefined} aria-sort={sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <button type="button" onClick={() => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : key === "name" ? 1 : -1 }))}>
        {label}{sort.key === key ? (sort.dir === 1 ? " ↑" : " ↓") : ""}
      </button>
    </th>
  );
  const tipRows = (r: StateRow) => [
    { label: "Spend", value: usd(r.spend) },
    { label: "Per enrollee", value: dollars(r.perEnrollee) },
    { label: `Growth, ${lookback} yrs`, value: r.growth == null ? "n/a" : `${signedPct(r.growth, 1)} a year` },
    { label: "Brand share", value: r.spend ? pct(r.brandSpend / r.spend) : "n/a" },
    ...(r.flagged ? [{ label: "Reporting", value: "break" }] : []),
  ];

  return (
    <Frame
      title={`Spend per Medicaid enrollee by state, ${year}`}
      sub={`${scope}. Colour = fifths of the 51 states. Outlined states changed how they report pharmacy spend in the last ${lookback} years, so their trends are not comparable.`}
      view={view}
      onView={setView}
      controls={
        <div className="field" style={{ marginBottom: 12 }}>
          <label htmlFor="map-year">Year</label>
          <select id="map-year" value={year} onChange={(e) => onYear(Number(e.target.value))}>
            {years.slice(lookback).map((y) => (<option key={y} value={y}>{y}</option>))}
          </select>
        </div>
      }
      legend={
        <ul className="legend" aria-label="Legend">
          {BINS.map((b, i) => (
            <li key={b}><i style={{ background: b }} />{dollars(edges[i])} to {dollars(edges[i + 1])}</li>
          ))}
          <li><i className="ring" style={{ borderColor: "var(--ochre)" }} />Reporting break</li>
        </ul>
      }
      source="State rows exclude small cells the source blanks (about 8% of national spend), so state totals are understated, most in oncology and rare disease. Enrollment is total Medicaid and CHIP, not people with the condition. Puerto Rico is left out."
      table={
        <table className="tbl">
          <caption>States, {scope}, {year}</caption>
          <thead><tr>{head("name", "State", false)}{head("spend", "Spend")}<th className="n">Enrollment</th>{head("perEnrollee", "Per enrollee")}{head("growth", `Growth a year (${lookback} yrs)`)}<th className="n">Brand share</th><th>Reporting</th></tr></thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.code}>
                <td className="nm">{r.name}</td><td className="n">{usd(r.spend)}</td><td className="n">{r.enrollment == null ? "n/a" : r.enrollment.toLocaleString("en-US")}</td>
                <td className="n">{dollars(r.perEnrollee)}</td><td className="n">{r.growth == null ? "n/a" : signedPct(r.growth, 1)}</td>
                <td className="n">{r.spend ? pct(r.brandSpend / r.spend) : "n/a"}</td><td>{r.flagged ? `Check: ${r.reason}` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <div ref={host} style={{ position: "relative" }}>
        <div ref={box}>
          <svg className="svg" width={w} height={H} role="group" aria-label={`Tile map of spend per enrollee by state, ${year}. ${flagged.length} states are flagged for a reporting break.`}>
            {rows.map((r) => {
              const pos = TILE_GRID[r.code];
              if (!pos) return null;
              const b = bin(r.perEnrollee);
              const x = pos[0] * ts;
              const y = pos[1] * ts;
              const light = b >= 3;
              return (
                <g
                  key={r.code} tabIndex={0} role="img"
                  aria-label={`${r.name}: ${r.perEnrollee == null ? "no enrollment" : `${dollars(r.perEnrollee)} per enrollee`}, ${usd(r.spend)} total${r.flagged ? `. Reporting break: ${r.reason}` : ""}`}
                  onPointerMove={atPointer(r.name, tipRows(r))} onPointerLeave={hide}
                  onFocus={atElement(r.name, tipRows(r))} onBlur={hide}
                >
                  <rect x={x + gap / 2} y={y + gap / 2} width={ts - gap} height={ts - gap} rx={3} style={{ fill: b < 0 ? "var(--paper-2)" : BINS[b], stroke: r.flagged ? "var(--ochre)" : "none", strokeWidth: r.flagged ? 2.5 : 0 }} />
                  <text x={x + ts / 2} y={y + ts / 2 + 1} textAnchor="middle" dy="0.2em" style={{ fill: light ? "var(--on-seq-dark)" : "var(--ink)", fontWeight: 600, fontSize: ts < 40 ? 10.5 : 12.5 }}>{r.code}</text>
                </g>
              );
            })}
          </svg>
          <Tip tip={tip} width={w} />
        </div>
      </div>
    </Frame>
  );
}

export function StateCallout({ rows, year, lookback }: { rows: StateRow[]; year: number; lookback: number }) {
  const withVal = useMemo(() => rows.filter((r) => r.perEnrollee != null), [rows]);
  const sorted = [...withVal].sort((a, b) => (b.perEnrollee as number) - (a.perEnrollee as number));
  const hi = sorted[0];
  const lo = sorted[sorted.length - 1];
  const flagged = rows.filter((r) => r.flagged).map((r) => r.name);
  if (!hi || !lo) return null;
  return (
    <p className="callout">
      <b>Read the trends with care.</b> {hi.name} spends {dollars(hi.perEnrollee)} per enrollee and {lo.name} {dollars(lo.perEnrollee)}, a {((hi.perEnrollee as number) / (lo.perEnrollee as number)).toFixed(1)}× gap in {year}.{" "}
      {flagged.length > 0 && <>{flagged.length} states ({flagged.slice(0, 6).join(", ")}{flagged.length > 6 ? ", …" : ""}) moved pharmacy spend between managed-care plans and state fee-for-service, or swung 40% or more in a year, during {year - lookback} to {year}. That changes reported totals without changing demand, so their growth is left out of any ranking.</>}
    </p>
  );
}
