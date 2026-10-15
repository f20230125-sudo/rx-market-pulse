"use client";

import { useMemo, useRef, useState } from "react";
import { scaleLinear } from "d3-scale";
import { Frame, niceTicks, roundedBar, Tip, useTip, useView, useWidth } from "../chart";
import { dateLabel, pct, usd } from "@/lib/format";
import { medianAt, medianCurve, type ProtectionBar } from "@/lib/derive";
import type { ErosionT, LoeT } from "@/lib/schema";

const MEDIAN = "var(--teal)";
const LINE = "var(--muted-mark)";
const PICK = "var(--ochre)";

/** Brand spend after generics arrive: every molecule (grey), the median (teal), one chosen brand (ochre). */
export function ErosionChart({ erosion }: { erosion: ErosionT }) {
  const host = useRef<HTMLDivElement>(null);
  const [box, w] = useWidth<HTMLDivElement>();
  const { hide } = useTip(host);
  const [view, setView] = useView();
  const [pick, setPick] = useState("");
  const [k, setK] = useState<number | null>(null);

  const curve = useMemo(() => medianCurve(erosion), [erosion]);
  const events = useMemo(() => [...erosion.events].filter((e) => erosion.curves[e.ingredient]).sort((a, b) => (b.runRateMusd ?? 0) - (a.runRateMusd ?? 0)), [erosion]);
  const H = 330;
  const m = { l: 44, r: 16, t: 30, b: 40 };
  const iw = w - m.l - m.r;
  const ih = H - m.t - m.b;
  const kMin = -8;
  const kMax = 16;
  const x = scaleLinear().domain([kMin, kMax]).range([0, iw]);
  const top = 160;
  const y = scaleLinear().domain([0, top]).range([ih, 0]);
  const path = (ks: number[], vs: (number | null)[]) => {
    let d = "";
    let open = false;
    ks.forEach((kk, i) => {
      const v = vs[i];
      if (v == null) { open = false; return; }
      d += `${open ? "L" : "M"}${x(kk).toFixed(1)},${y(v).toFixed(1)} `;
      open = true;
    });
    return d.trim();
  };
  const m8 = medianAt(curve, 8);
  const m4 = medianAt(curve, 4);
  const picked = pick ? erosion.curves[pick] : null;
  const pickedEvent = events.find((e) => e.ingredient === pick);
  const active = k ?? 8;
  const act = medianAt(curve, active);
  const below50 = Object.values(erosion.curves).filter((c) => { const i = c.k.indexOf(active); return i >= 0 && c.brandIndex[i] != null && (c.brandIndex[i] as number) < 50; }).length;
  const withData = Object.values(erosion.curves).filter((c) => { const i = c.k.indexOf(active); return i >= 0 && c.brandIndex[i] != null; }).length;
  const pickVal = picked ? picked.brandIndex[picked.k.indexOf(active)] : null;

  const move = (clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    if (!r) return;
    const kk = Math.round(x.invert(clientX - r.left - m.l));
    setK(Math.max(kMin, Math.min(kMax, kk)));
  };
  const rowsTip = [
    { label: "Median brand", value: act ? `${Math.round(act.median)}` : "n/a", color: MEDIAN },
    { label: "Brands below 50", value: `${below50} of ${withData}` },
    ...(picked && pickedEvent ? [{ label: pickedEvent.brand ?? pickedEvent.ingredient, value: pickVal == null ? "n/a" : String(Math.round(pickVal)), color: PICK }] : []),
  ];
  const tipTitle = active === 0 ? "The quarter generics enter" : active < 0 ? `${-active} quarter${active === -1 ? "" : "s"} before` : `${active} quarter${active === 1 ? "" : "s"} after`;

  return (
    <Frame
      title="What happens to a brand when generics arrive"
      sub={`Brand spend, indexed to 100 for the year before generics took 10% of prescriptions. ${events.length} molecules where the switch happened between 2019 and 2025.`}
      view={view}
      onView={setView}
      controls={
        <div className="field" style={{ marginBottom: 10 }}>
          <label htmlFor="erosion-pick">Highlight a brand</label>
          <select id="erosion-pick" value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">None</option>
            {events.map((e) => (<option key={e.ingredient} value={e.ingredient}>{e.brand ?? e.ingredient}</option>))}
          </select>
        </div>
      }
      legend={
        <ul className="legend" aria-label="Legend">
          <li><i className="line" style={{ background: MEDIAN }} />Median of {events.length} brands</li>
          <li><i className="line" style={{ background: LINE }} />Each brand</li>
          {picked && <li><i className="line" style={{ background: PICK }} />{pickedEvent?.brand ?? pick}</li>}
        </ul>
      }
      source={`Generic entry is the first quarter generics reach 10% of the molecule's prescriptions; only molecules that started 2019 below 5% and had at least $20M of brand spend before entry are included. Use the left and right arrow keys on the chart to step through quarters.`}
      table={
        <table className="tbl">
          <caption>Generic entry events</caption>
          <thead><tr><th>Brand</th><th>Molecule</th><th>Generic entry</th><th className="n">Brand run-rate before</th><th className="n">Brand index +4q</th><th className="n">+8q</th><th className="n">Generic share +4q</th><th className="n">+8q</th></tr></thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.ingredient}>
                <td className="nm">{e.brand ?? "n/a"}</td><td>{e.ingredient.toLowerCase()}</td><td>{dateLabel(e.entry)}</td>
                <td className="n">{e.runRateMusd == null ? "n/a" : usd(e.runRateMusd * 1e6, 0)}</td>
                <td className="n">{e.brandIndexQ4 ?? "n/a"}</td><td className="n">{e.brandIndexQ8 ?? "n/a"}</td>
                <td className="n">{e.genericShareQ4 == null ? "n/a" : `${e.genericShareQ4}%`}</td><td className="n">{e.genericShareQ8 == null ? "n/a" : `${e.genericShareQ8}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <div ref={host} style={{ position: "relative" }}>
        <div ref={box}>
          <svg
            className="svg" width={w} height={H} tabIndex={0} role="img"
            aria-label={`Brand spend index by quarter since generic entry. The median brand is at ${m4 ? Math.round(m4.median) : "n/a"} four quarters after entry and ${m8 ? Math.round(m8.median) : "n/a"} eight quarters after, where 100 is the year before.`}
            onPointerMove={(e) => move(e.clientX)} onPointerLeave={() => { setK(null); hide(); }}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") { e.preventDefault(); setK(Math.min(kMax, (k ?? 8) + 1)); }
              if (e.key === "ArrowLeft") { e.preventDefault(); setK(Math.max(kMin, (k ?? 8) - 1)); }
              if (e.key === "Escape") setK(null);
            }}
            onBlur={() => setK(null)}
          >
            <defs><clipPath id="erosion-plot"><rect x={-2} y={-2} width={iw + 4} height={ih + 4} /></clipPath></defs>
            <g transform={`translate(${m.l},${m.t})`}>
              <text x={-m.l + 2} y={-12} className="t-mute">Brand spend index (100 = the year before)</text>
              {[0, 50, 100, 150].map((t) => (
                <g key={t}>
                  <line className="grid" x1={0} x2={iw} y1={y(t)} y2={y(t)} style={t === 100 ? { stroke: "var(--rule-2)" } : undefined} />
                  <text x={-8} y={y(t)} dy="0.32em" textAnchor="end" className="t-mute">{t}</text>
                </g>
              ))}
              {[-8, -4, 0, 4, 8, 12, 16].map((t) => (
                <text key={t} x={x(t)} y={ih + 18} textAnchor="middle" className={t === 0 ? "t-strong" : "t-mute"}>{t > 0 ? `+${t}` : t}</text>
              ))}
              <text x={iw / 2} y={ih + 34} textAnchor="middle" className="t-mute">Quarters since generics entered</text>
              <line x1={x(0)} x2={x(0)} y1={0} y2={ih} style={{ stroke: "var(--ink-3)", strokeWidth: 1 }} />
              <text x={x(0) + 6} y={10} className="t-mute">Generics enter</text>
              <g clipPath="url(#erosion-plot)">
                {Object.entries(erosion.curves).map(([ing, c]) => (
                  <path key={ing} d={path(c.k, c.brandIndex)} fill="none" style={{ stroke: LINE, opacity: pick ? 0.45 : 0.7 }} strokeWidth={1.25} />
                ))}
              </g>
              {picked && <path d={path(picked.k, picked.brandIndex)} fill="none" style={{ stroke: PICK }} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />}
              <path d={path(curve.map((p) => p.k), curve.map((p) => p.median))} fill="none" style={{ stroke: MEDIAN }} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
              {m8 && (
                <g>
                  <circle cx={x(8)} cy={y(m8.median)} r={4.5} style={{ fill: MEDIAN, stroke: "var(--paper)", strokeWidth: 2 }} />
                  <text x={x(8) + (iw - x(8) < 170 ? -10 : 10)} y={y(m8.median) - 8} textAnchor={iw - x(8) < 170 ? "end" : "start"} className="t-strong">Median: {Math.round(m8.median)} after 2 years</text>
                </g>
              )}
              {k != null && (
                <g>
                  <line x1={x(k)} x2={x(k)} y1={0} y2={ih} style={{ stroke: "var(--ink-2)", strokeWidth: 1 }} />
                  {act && <circle cx={x(k)} cy={y(act.median)} r={4.5} style={{ fill: MEDIAN, stroke: "var(--paper)", strokeWidth: 2 }} />}
                </g>
              )}
              <line className="axis" x1={0} x2={iw} y1={ih} y2={ih} />
            </g>
          </svg>
          {k != null && <Tip tip={{ x: m.l + x(k), y: m.t + 40, title: tipTitle, rows: rowsTip }} width={w} />}
        </div>
      </div>
    </Frame>
  );
}

/** Spend that is protected, by the year core protection ends. Select a year to list the products. */
export function ProtectionChart({ bars, selected, onSelect, scope, asOf, groups }: { bars: ProtectionBar[]; selected: string | null; onSelect: (k: string | null) => void; scope: string; asOf: string; groups: Record<string, { families: number; spend: number }> }) {
  const host = useRef<HTMLDivElement>(null);
  const [box, w] = useWidth<HTMLDivElement>();
  const { tip, atPointer, atElement, hide } = useTip(host);
  const [view, setView] = useView();

  const H = 270;
  const m = { l: 48, r: 8, t: 26, b: 30 };
  const iw = w - m.l - m.r;
  const ih = H - m.t - m.b;
  const { top, ticks } = niceTicks(Math.max(...bars.map((b) => b.spend), 1));
  const y = scaleLinear().domain([0, top]).range([ih, 0]);
  const band = iw / bars.length;
  const bw = Math.min(band * 0.58, 30);

  return (
    <Frame
      title={`When protection ends, ${scope}`}
      sub={`2025 Medicaid spend on brands that still have a listed patent or exclusivity, grouped by the year their core protection ends. Select a year to list the brands.`}
      view={view}
      onView={setView}
      source={`FDA Orange Book as of ${asOf}. Core protection is the drug-substance patent or an exclusivity; later formulation patents are often challenged or settled, so a date here is where protection ends, not a forecast of generic launch.`}
      table={
        <table className="tbl">
          <caption>Protected brand spend by year core protection ends, {scope}</caption>
          <thead><tr><th>Year</th><th className="n">Brands</th><th className="n">2025 spend</th></tr></thead>
          <tbody>{bars.map((b) => (<tr key={b.key}><td>{b.label}</td><td className="n">{b.families}</td><td className="n">{usd(b.spend)}</td></tr>))}</tbody>
        </table>
      }
    >
      <div ref={host} style={{ position: "relative" }}>
        <div ref={box}>
          <svg className="svg" width={w} height={H} role="group" aria-label={`Protected spend by the year core protection ends, ${scope}`}>
            <g transform={`translate(${m.l},${m.t})`}>
              {ticks.map((t) => (
                <g key={t}>
                  <line className="grid" x1={0} x2={iw} y1={y(t)} y2={y(t)} />
                  <text x={-8} y={y(t)} dy="0.32em" textAnchor="end" className="t-mute">{t === 0 ? "$0" : usd(t, 0)}</text>
                </g>
              ))}
              {bars.map((b, i) => {
                const cx = band * i + band / 2;
                const h = ih - y(b.spend);
                const isSel = selected === b.key;
                const rows = [{ label: "2025 spend", value: usd(b.spend) }, { label: "Brands", value: String(b.families) }];
                return (
                  <g
                    key={b.key} tabIndex={0} role="button" aria-pressed={isSel}
                    aria-label={`${b.label}: ${usd(b.spend)} across ${b.families} brands. ${isSel ? "Selected." : "Press to list them."}`}
                    onClick={() => onSelect(isSel ? null : b.key)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(isSel ? null : b.key); } }}
                    onPointerMove={atPointer(b.label, rows)} onPointerLeave={hide}
                    onFocus={atElement(b.label, rows)} onBlur={hide}
                  >
                    <rect x={cx - band / 2} y={-m.t} width={band} height={ih + m.t + m.b} fill="transparent" />
                    <path d={roundedBar(cx - bw / 2, ih - h, bw, h, 4, "up")} style={{ fill: isSel ? "var(--ochre)" : "var(--teal)" }} />
                    {b.spend > 0 && <text x={cx} y={ih - h - 7} textAnchor="middle" className={isSel ? "t-strong" : "t-mute"}>{usd(b.spend, 1)}</text>}
                    <text x={cx} y={ih + 17} textAnchor="middle" className={isSel ? "t-strong" : "t-mute"}>{b.label}</text>
                  </g>
                );
              })}
              <line className="axis" x1={0} x2={iw} y1={ih} y2={ih} />
            </g>
          </svg>
          <Tip tip={tip} width={w} />
        </div>
      </div>
      <dl className="ledger" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", marginTop: 22 }}>
        {[
          ["Biologic (not in Orange Book)", "Biologics: protection is tracked elsewhere"],
          ["No patent or exclusivity listed", "No listed protection"],
          ["Listed protection has ended", "Listed protection has ended"],
        ].map(([key, label]) => (
          <div key={key}>
            <dt className="led-label">{label}</dt>
            <dd style={{ margin: 0 }}><p className="led-value" style={{ fontSize: 24 }}>{usd(groups[key]?.spend ?? 0)}</p><p className="led-delta">{groups[key]?.families ?? 0} brands · {pct((groups[key]?.spend ?? 0) / Math.max(1, bars.reduce((a, b) => a + b.spend, 0) + Object.values(groups).reduce((a, g) => a + g.spend, 0)), 0)} of brand spend</p></dd>
          </div>
        ))}
      </dl>
    </Frame>
  );
}

export function ProtectedList({ loe, area, year }: { loe: LoeT; area: string; year: string }) {
  const rows = loe.top
    .filter((r) => (area === "All areas" || r.area === area) && r.coreEnd && (year === "earlier" ? Number(r.coreEnd.slice(0, 4)) < 2026 : year === "later" ? Number(r.coreEnd.slice(0, 4)) > 2035 : r.coreEnd.slice(0, 4) === year))
    .slice(0, 12);
  return (
    <div className="tbl-wrap" style={{ marginTop: 18 }}>
      <table className="tbl">
        <caption>Brands whose core protection ends {year === "earlier" ? "before 2026" : year === "later" ? "after 2035" : `in ${year}`}, largest first</caption>
        <thead><tr><th>Brand</th><th>Company</th><th className="n">2025 spend</th><th>Core protection ends</th><th>Last listed protection</th></tr></thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan={5}>No brands in the largest 400 for this selection.</td></tr>}
          {rows.map((r) => (
            <tr key={r.family}><td className="nm">{r.family}</td><td>{r.owner}</td><td className="n">{usd(r.spend)}</td><td>{dateLabel(r.coreEnd)}</td><td>{dateLabel(r.lastEnd)}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
