"use client";

import { useRef } from "react";
import { scaleLinear } from "d3-scale";
import { fit, Frame, niceTicks, roundedBar, Tip, useTip, useView, useWidth } from "../chart";
import { signedPct, signedUsd, usd } from "@/lib/format";
import type { AreaRow, Bridge } from "@/lib/derive";

const POS = "var(--teal)";
const NEG = "var(--rust)";
const NET = "var(--ink)";

/** What moved spend between two years: volume, mix, price, new and lost products. */
export function Waterfall({ bridge, scope, pairs, pair, onPair }: { bridge: Bridge; scope: string; pairs: string[]; pair: string; onPair: (p: string) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const [box, w] = useWidth<HTMLDivElement>();
  const { tip, atPointer, atElement, hide } = useTip(host);
  const [view, setView] = useView();

  const H = 300;
  const m = { l: 52, r: 8, t: 26, b: 62 };
  const iw = w - m.l - m.r;
  const ih = H - m.t - m.b;
  const levels = bridge.steps.flatMap((s) => [s.from, s.to]);
  const lo = Math.min(0, ...levels);
  const hi = Math.max(0, ...levels);
  const span = niceTicks(hi - lo > 0 ? hi - lo : 1, 4);
  const step = span.ticks.length > 1 ? span.ticks[1] - span.ticks[0] : 1;
  const yMin = Math.floor(lo / step) * step;
  const yMax = Math.ceil(hi / step) * step;
  const y = scaleLinear().domain([yMin, yMax]).range([ih, 0]);
  const ticks: number[] = [];
  for (let v = yMin; v <= yMax + step / 1000; v += step) ticks.push(Number(v.toFixed(0)));
  const band = iw / bridge.steps.length;
  const bw = Math.min(band * 0.58, 34);
  const net = bridge.steps[bridge.steps.length - 1];

  const narrow = band < 66;
  const SHORT: Record<string, string> = { volume: "Volume", mix: "Mix", price: "Price", newProducts: "New", lostProducts: "Lost", net: "Net" };
  const maxChars = Math.max(9, Math.floor(band / 6.8));
  const wrap = (label: string) => {
    const words = label.split(" ");
    const lines: string[] = [];
    let cur = "";
    for (const wd of words) {
      if ((cur + " " + wd).trim().length > maxChars) {
        lines.push(cur);
        cur = wd;
      } else cur = (cur + " " + wd).trim();
    }
    if (cur) lines.push(cur);
    return lines.slice(0, 3);
  };

  return (
    <Frame
      title={`Why spend changed, ${bridge.y0} to ${bridge.y1}`}
      sub={`${scope}. ${usd(bridge.start)} in ${bridge.y0} to ${usd(bridge.end)} in ${bridge.y1}: ${signedUsd(net.value)}.${narrow ? " Bars: prescription volume, mix of products, spend per prescription, new and lost products." : ""}`}
      view={view}
      onView={setView}
      controls={
        <div className="chips" role="group" aria-label="Years to compare">
          {pairs.map((p) => (
            <button key={p} type="button" aria-pressed={p === pair} onClick={() => onPair(p)}>{p.replace("-", " to ")}</button>
          ))}
        </div>
      }
      source="Price per prescription is spend divided by prescriptions, so it also moves with strength, pack size and days' supply; it is not a list price. Products are compared by brand name (or molecule for generics)."
      table={
        <table className="tbl">
          <caption>Bridge from {bridge.y0} to {bridge.y1}, {scope}</caption>
          <thead><tr><th>Step</th><th className="n">Change in spend</th></tr></thead>
          <tbody>
            <tr><td>{bridge.y0} spend</td><td className="n">{usd(bridge.start)}</td></tr>
            {bridge.steps.slice(0, -1).map((s) => (<tr key={s.key}><td>{s.label}</td><td className="n">{signedUsd(s.value)}</td></tr>))}
            <tr className="hl"><td className="nm">{bridge.y1} spend</td><td className="n">{usd(bridge.end)}</td></tr>
          </tbody>
        </table>
      }
    >
      <div ref={host} style={{ position: "relative" }}>
        <div ref={box}>
          <svg className="svg" width={w} height={H} role="img" aria-label={`Bridge of spend from ${bridge.y0} to ${bridge.y1}. ${bridge.steps.map((s) => `${s.label} ${signedUsd(s.value)}`).join("; ")}.`}>
            <g transform={`translate(${m.l},${m.t})`}>
              {ticks.map((t) => (
                <g key={t}>
                  <line className="grid" x1={0} x2={iw} y1={y(t)} y2={y(t)} />
                  <text x={-8} y={y(t)} dy="0.32em" textAnchor="end" className="t-mute">{t === 0 ? "$0" : signedUsd(t, 0)}</text>
                </g>
              ))}
              <line className="axis" x1={0} x2={iw} y1={y(0)} y2={y(0)} />
              {bridge.steps.map((s, i) => {
                const cx = band * i + band / 2;
                const top = y(Math.max(s.from, s.to));
                const h = Math.max(1.5, Math.abs(y(s.from) - y(s.to)));
                const fill = s.type === "net" ? NET : s.value >= 0 ? POS : NEG;
                const up = s.value >= 0;
                const rows = [{ label: s.type === "net" ? "Net change" : "Change", value: signedUsd(s.value) }];
                const lines = narrow ? [SHORT[s.key] ?? s.label] : wrap(s.label);
                return (
                  <g key={s.key}>
                    {i > 0 && i < bridge.steps.length - 1 && (
                      <line className="grid" x1={band * (i - 1) + band / 2 + bw / 2} x2={cx - bw / 2} y1={y(s.from)} y2={y(s.from)} style={{ stroke: "var(--rule-2)" }} />
                    )}
                    <path d={roundedBar(cx - bw / 2, top, bw, h, 3, "up")} fill={fill} />
                    <text x={cx} y={up ? top - 6 : top + h + 14} textAnchor="middle" className="t-strong">{signedUsd(s.value)}</text>
                    {lines.map((ln, j) => (
                      <text key={j} x={cx} y={ih + 18 + j * 14 + (yMin < 0 ? Math.max(0, y(yMin) - ih) : 0)} textAnchor="middle" className={s.type === "net" ? "t-strong" : "t-mute"}>{ln}</text>
                    ))}
                    <rect
                      x={cx - band / 2} y={-m.t} width={band} height={ih + m.t + m.b} fill="transparent" tabIndex={0} role="img"
                      aria-label={`${s.label}: ${signedUsd(s.value)}`}
                      onPointerMove={atPointer(s.label, rows)} onPointerLeave={hide}
                      onFocus={atElement(s.label, rows)} onBlur={hide}
                    />
                  </g>
                );
              })}
            </g>
          </svg>
          <Tip tip={tip} width={w} />
        </div>
      </div>
    </Frame>
  );
}

/** Extra spend since the first year, by therapeutic area: where the growth came from. Click a row to scope the page. */
export function AreaIncrease({ rows, selected, onSelect, years }: { rows: AreaRow[]; selected: string; onSelect: (a: string) => void; years: [number, number] }) {
  const host = useRef<HTMLDivElement>(null);
  const [box, w] = useWidth<HTMLDivElement>();
  const { tip, atPointer, atElement, hide } = useTip(host);
  const [view, setView] = useView();

  const data = rows.map((r) => ({ ...r, delta: r.spend1 - r.spend0 })).sort((a, b) => b.delta - a.delta);
  const rowH = 26;
  const labelW = Math.min(205, Math.max(136, w * 0.34));
  const rightW = w < 520 ? 0 : 112;
  const valueRoom = 66;
  const negPad = minDelta(rows) < 0 ? 62 : 8;
  const H = data.length * rowH + 30;
  const maxD = Math.max(...data.map((d) => d.delta), 1);
  const minD = Math.min(...data.map((d) => d.delta), 0);
  const plotW = Math.max(80, w - labelW - rightW - valueRoom);
  const x = scaleLinear().domain([minD, maxD]).range([negPad, plotW]);
  const total = data.reduce((a, d) => a + d.delta, 0);

  return (
    <Frame
      title={`Where the extra spend came from, ${years[0]} to ${years[1]}`}
      sub={`Increase in annual spend by therapeutic area. Together: ${signedUsd(total)}. Select a row to scope the page to that area.`}
      view={view}
      onView={setView}
      source="Therapeutic area is assigned from the FDA pharmacologic class, then the same ingredient, then a curated name list (97.8% of spend classified; the rest is shown as 'Unclassified')."
      table={
        <table className="tbl">
          <caption>Spend by therapeutic area</caption>
          <thead><tr><th>Area</th><th className="n">{years[0]}</th><th className="n">{years[1]}</th><th className="n">Increase</th><th className="n">Per year</th></tr></thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.area} className={d.area === selected ? "hl" : undefined}>
                <td>{d.area}</td><td className="n">{usd(d.spend0)}</td><td className="n">{usd(d.spend1)}</td>
                <td className="n">{signedUsd(d.delta)}</td><td className="n">{d.cagr == null ? "n/a" : signedPct(d.cagr, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <div ref={host} style={{ position: "relative" }}>
        <div ref={box}>
          <svg className="svg" width={w} height={H} role="group" aria-label="Increase in spend by therapeutic area">
            <g transform="translate(0,6)">
              {data.map((d, i) => {
                const y0 = i * rowH;
                const isSel = d.area === selected;
                const barH = 14;
                const x0 = labelW + x(0);
                const xe = labelW + x(d.delta);
                const neg = d.delta < 0;
                const rows = [
                  { label: `${years[0]}`, value: usd(d.spend0) },
                  { label: `${years[1]}`, value: usd(d.spend1) },
                  { label: "Increase", value: signedUsd(d.delta) },
                  { label: "Per year", value: d.cagr == null ? "n/a" : signedPct(d.cagr, 1) },
                ];
                return (
                  <g
                    key={d.area} tabIndex={0} role="button" aria-pressed={isSel}
                    aria-label={`${d.area}: ${signedUsd(d.delta)} since ${years[0]}${d.cagr == null ? "" : `, ${signedPct(d.cagr, 1)} a year`}. ${isSel ? "Selected." : "Press to select."}`}
                    onClick={() => onSelect(isSel ? "All areas" : d.area)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(isSel ? "All areas" : d.area); } }}
                    onPointerMove={atPointer(d.area, rows)} onPointerLeave={hide}
                    onFocus={atElement(d.area, rows)} onBlur={hide}
                  >
                    {isSel && <rect x={0} y={y0 - 2} width={w} height={rowH - 2} style={{ fill: "var(--teal-wash)" }} />}
                    <text x={labelW - 12} y={y0 + 12} dy="0.1em" textAnchor="end" className={isSel ? "t-strong" : undefined}>{fit(d.area, labelW - 16)}</text>
                    {neg ? (
                      <rect x={xe} y={y0 + 3} width={Math.max(1, x0 - xe)} height={barH} rx={3} style={{ fill: NEG }} />
                    ) : (
                      <path d={roundedBar(x0, y0 + 3, Math.max(1.5, xe - x0), barH, 4, "right")} style={{ fill: POS }} />
                    )}
                    <text x={neg ? xe - 6 : xe + 7} y={y0 + 14} textAnchor={neg ? "end" : "start"} className="t-strong">{signedUsd(d.delta)}</text>
                    {rightW > 0 && <text x={w} y={y0 + 14} textAnchor="end" className="t-mute">{d.cagr == null ? "" : `${signedPct(d.cagr, 1)} a year`}</text>}
                  </g>
                );
              })}
              <line className="axis" x1={labelW + x(0)} x2={labelW + x(0)} y1={-4} y2={data.length * rowH} />
            </g>
          </svg>
          <Tip tip={tip} width={w} />
        </div>
      </div>
    </Frame>
  );
}

function minDelta(rows: AreaRow[]): number {
  return Math.min(0, ...rows.map((r) => r.spend1 - r.spend0));
}
