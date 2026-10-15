"use client";

import { useRef } from "react";
import { scaleLinear } from "d3-scale";
import { Frame, niceTicks, roundedBar, Tip, useTip, useView, useWidth } from "../chart";
import { count, pct, usd } from "@/lib/format";
import type { MarketT } from "@/lib/schema";

const BRAND = "var(--teal)";
const GENERIC = "var(--ochre)";

type Series = MarketT["series"][string];

/** Spend by year, brand and generic stacked. Two series, so a legend and a few direct labels. */
export function SpendColumns({ years, s, scope }: { years: number[]; s: Series; scope: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [box, w] = useWidth<HTMLDivElement>();
  const { tip, atPointer, atElement, hide } = useTip(host);
  const [view, setView] = useView();

  const H = 270;
  const m = { l: 48, r: 8, t: 26, b: 26 };
  const iw = w - m.l - m.r;
  const ih = H - m.t - m.b;
  const totals = years.map((_, i) => s.brandSpend[i] + s.genericSpend[i] + s.otherSpend[i]);
  const { top, ticks } = niceTicks(Math.max(...totals));
  const y = scaleLinear().domain([0, top]).range([ih, 0]);
  const band = iw / years.length;
  const bw = Math.min(band * 0.56, 30);

  return (
    <Frame
      title="Spend by year"
      sub={`${scope}. Gross amount reimbursed, before manufacturer rebates.`}
      view={view}
      onView={setView}
      legend={
        <ul className="legend" aria-label="Legend">
          <li><i style={{ background: BRAND }} />Brand</li>
          <li><i style={{ background: GENERIC }} />Generic</li>
        </ul>
      }
      source="Source: CMS State Drug Utilization Data, national totals. Brand = single-source or innovator products; generic = non-innovator."
      table={
        <table className="tbl">
          <caption>Spend by year, {scope}</caption>
          <thead>
            <tr><th>Year</th><th className="n">Brand</th><th className="n">Generic</th><th className="n">Unmatched NDCs</th><th className="n">Total</th><th className="n">Brand share</th></tr>
          </thead>
          <tbody>
            {years.map((yr, i) => (
              <tr key={yr}>
                <td>{yr}</td>
                <td className="n">{usd(s.brandSpend[i])}</td>
                <td className="n">{usd(s.genericSpend[i])}</td>
                <td className="n">{usd(s.otherSpend[i])}</td>
                <td className="n">{usd(totals[i])}</td>
                <td className="n">{pct(s.brandSpend[i] / totals[i], 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <div ref={host} style={{ position: "relative" }}>
        <div ref={box}>
          <svg className="svg" width={w} height={H} role="img" aria-label={`Stacked columns of brand and generic spend, ${years[0]} to ${years[years.length - 1]}. ${scope}. Total ${usd(totals[0])} in ${years[0]} and ${usd(totals[totals.length - 1])} in ${years[years.length - 1]}.`}>
            <g transform={`translate(${m.l},${m.t})`}>
              {ticks.map((t) => (
                <g key={t}>
                  <line className="grid" x1={0} x2={iw} y1={y(t)} y2={y(t)} />
                  <text x={-8} y={y(t)} dy="0.32em" textAnchor="end" className="t-mute">{t === 0 ? "$0" : usd(t, 0)}</text>
                </g>
              ))}
              {years.map((yr, i) => {
                const cx = band * i + band / 2;
                const hb = ih - y(s.brandSpend[i]);
                const hg = ih - y(s.genericSpend[i] + s.otherSpend[i]);
                const gap = hg > 0 && hb > 0 ? 2 : 0;
                const rows = [
                  { label: "Brand", value: usd(s.brandSpend[i]), color: BRAND },
                  { label: "Generic", value: usd(s.genericSpend[i]), color: GENERIC },
                  { label: "Total", value: usd(totals[i]) },
                  { label: "Brand share", value: pct(s.brandSpend[i] / totals[i], 1) },
                ];
                return (
                  <g key={yr}>
                    <path d={roundedBar(cx - bw / 2, ih - hb, bw, hb, hg > 0 ? 0 : 4, "up")} fill={BRAND} />
                    <path d={roundedBar(cx - bw / 2, ih - hb - hg - gap, bw, hg, 4, "up")} fill={GENERIC} />
                    {(i === 0 || i === years.length - 1) && (
                      <text x={cx} y={ih - hb - hg - gap - 7} textAnchor="middle" className="t-strong">{usd(totals[i])}</text>
                    )}
                    <text x={cx} y={ih + 17} textAnchor="middle" className="t-mute">{yr}</text>
                    <rect
                      x={cx - band / 2} y={-m.t} width={band} height={ih + m.t} fill="transparent" tabIndex={0} role="img"
                      aria-label={`${yr}: brand ${usd(s.brandSpend[i])}, generic ${usd(s.genericSpend[i])}, total ${usd(totals[i])}`}
                      onPointerMove={atPointer(String(yr), rows)} onPointerLeave={hide}
                      onFocus={atElement(String(yr), rows)} onBlur={hide}
                    />
                  </g>
                );
              })}
              <line className="axis" x1={0} x2={iw} y1={ih} y2={ih} />
            </g>
          </svg>
          <Tip tip={tip} width={w} />
        </div>
      </div>
    </Frame>
  );
}

/** The same market measured two ways: share of prescriptions vs share of spend. */
export function ShareBars({ years, s, scope }: { years: number[]; s: Series; scope: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [box, w] = useWidth<HTMLDivElement>();
  const { tip, atPointer, atElement, hide } = useTip(host);
  const [view, setView] = useView();

  const picks = [years[years.length - 1], years[0]];
  const rows = picks.flatMap((yr) => {
    const i = years.indexOf(yr);
    const rx = s.brandRx[i] + s.genericRx[i] + s.otherRx[i];
    const sp = s.brandSpend[i] + s.genericSpend[i] + s.otherSpend[i];
    return [
      { key: `${yr}-rx`, year: yr, measure: "Prescriptions", brand: s.brandRx[i] / rx, total: rx, brandVal: s.brandRx[i], fmt: count },
      { key: `${yr}-sp`, year: yr, measure: "Spend", brand: s.brandSpend[i] / sp, total: sp, brandVal: s.brandSpend[i], fmt: usd },
    ];
  });

  const labelW = 124;
  const valueW = 92;
  const rowH = 34;
  const gapGroup = 18;
  const H = rows.length * rowH + gapGroup + 8;
  const bx = labelW;
  const bwid = Math.max(60, w - labelW - valueW);

  return (
    <Frame
      title="The same market, measured two ways"
      sub={`${scope}. Brand share of prescriptions against brand share of spend.`}
      view={view}
      onView={setView}
      legend={
        <ul className="legend" aria-label="Legend">
          <li><i style={{ background: BRAND }} />Brand</li>
          <li><i style={{ background: GENERIC }} />Generic</li>
        </ul>
      }
      source="Prescriptions are claims paid, not people treated."
      table={
        <table className="tbl">
          <caption>Brand and generic shares, {scope}</caption>
          <thead><tr><th>Year</th><th>Measure</th><th className="n">Brand</th><th className="n">Generic and unmatched</th><th className="n">Brand share</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}>
                <td>{r.year}</td><td>{r.measure}</td>
                <td className="n">{r.fmt(r.brandVal)}</td><td className="n">{r.fmt(r.total - r.brandVal)}</td><td className="n">{pct(r.brand, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <div ref={host} style={{ position: "relative" }}>
        <div ref={box}>
          <svg className="svg" width={w} height={H} role="img" aria-label={`Brand share: ${rows.map((r) => `${r.measure.toLowerCase()} ${r.year} ${pct(r.brand, 1)}`).join("; ")}.`}>
            {rows.map((r, i) => {
              const y0 = i * rowH + (i >= 2 ? gapGroup : 0) + 4;
              const bwBrand = bwid * r.brand;
              const tipRows = [
                { label: "Brand", value: `${pct(r.brand, 1)} · ${r.fmt(r.brandVal)}`, color: BRAND },
                { label: "Generic", value: `${pct(1 - r.brand, 1)} · ${r.fmt(r.total - r.brandVal)}`, color: GENERIC },
              ];
              return (
                <g key={r.key}>
                  <text x={0} y={y0 + 13} className="t-strong">{r.measure}</text>
                  <text x={0} y={y0 + 27} className="t-mute">{r.year}</text>
                  <path d={roundedBar(bx, y0 + 4, Math.max(0, bwBrand - 1), 18, 0, "right")} fill={BRAND} />
                  <path d={roundedBar(bx + bwBrand + 1, y0 + 4, Math.max(0, bwid - bwBrand - 1), 18, 4, "right")} fill={GENERIC} />
                  <text x={bx + bwid + 10} y={y0 + 17} className="t-strong">{pct(r.brand, 1)}</text>
                  <rect
                    x={0} y={y0} width={w} height={rowH - 2} fill="transparent" tabIndex={0} role="img"
                    aria-label={`${r.measure} ${r.year}: brand ${pct(r.brand, 1)}, generic ${pct(1 - r.brand, 1)}`}
                    onPointerMove={atPointer(`${r.measure}, ${r.year}`, tipRows)} onPointerLeave={hide}
                    onFocus={atElement(`${r.measure}, ${r.year}`, tipRows)} onBlur={hide}
                  />
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
