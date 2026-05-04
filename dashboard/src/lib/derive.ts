import { median } from "d3-array";
import type { ErosionT, ForecastT, LoeT, MarketT, OwnersT, PvmT, StatesT } from "./schema";

// Pure functions: JSON in, numbers out. The charts only draw what these return, and the tests pin each one.

type Block = MarketT["series"][string];

export function totalsAt(s: Block, i: number) {
  const spend = s.brandSpend[i] + s.genericSpend[i] + s.otherSpend[i];
  const rx = s.brandRx[i] + s.genericRx[i] + s.otherRx[i];
  return { spend, rx, brandSpend: s.brandSpend[i], brandRx: s.brandRx[i], perRx: rx > 0 ? spend / rx : 0 };
}

export type Kpis = {
  y0: number;
  y1: number;
  spend0: number;
  spend1: number;
  rx0: number;
  rx1: number;
  perRx0: number;
  perRx1: number;
  brandSpendShare0: number;
  brandSpendShare1: number;
  brandRxShare0: number;
  brandRxShare1: number;
};

export function kpis(market: MarketT, area: string): Kpis {
  const s = market.series[area];
  const last = market.years.length - 1;
  const a = totalsAt(s, 0);
  const b = totalsAt(s, last);
  return {
    y0: market.years[0],
    y1: market.years[last],
    spend0: a.spend,
    spend1: b.spend,
    rx0: a.rx,
    rx1: b.rx,
    perRx0: a.perRx,
    perRx1: b.perRx,
    brandSpendShare0: a.spend ? a.brandSpend / a.spend : 0,
    brandSpendShare1: b.spend ? b.brandSpend / b.spend : 0,
    brandRxShare0: a.rx ? a.brandRx / a.rx : 0,
    brandRxShare1: b.rx ? b.brandRx / b.rx : 0,
  };
}

export function cagr(from: number, to: number, years: number): number | null {
  if (!(from > 0) || !(to > 0) || years <= 0) return null;
  return (to / from) ** (1 / years) - 1;
}

export type AreaRow = { area: string; spend0: number; spend1: number; cagr: number | null };

export function areaGrowth(market: MarketT, areas: string[]): AreaRow[] {
  const last = market.years.length - 1;
  return areas
    .map((area) => {
      const s = market.series[area];
      const a = totalsAt(s, 0).spend;
      const b = totalsAt(s, last).spend;
      return { area, spend0: a, spend1: b, cagr: cagr(a, b, last) };
    })
    .sort((x, y) => y.spend1 - x.spend1);
}

export type WaterfallStep = {
  key: string;
  label: string;
  value: number; // the signed change this step adds; for the last step, the net change
  type: "delta" | "net";
  from: number; // running change before this step (0 for the net bar)
  to: number;
};

export type Bridge = { start: number; end: number; y0: string; y1: string; steps: WaterfallStep[] };

const STEP_LABELS: Record<string, string> = {
  volume: "More or fewer prescriptions",
  mix: "Shift to costlier products",
  price: "Spend per prescription, same product",
  newProducts: "New products",
  lostProducts: "Discontinued products",
};

/** The change in spend between two years, split into its causes. Bars float on the running change since the start year. */
export function waterfall(pvm: PvmT, area: string, pair: string): Bridge | null {
  const b = pvm.segments[area]?.[pair];
  if (!b) return null;
  const [y0, y1] = pair.split("-");
  const steps: WaterfallStep[] = [];
  let level = 0;
  for (const key of ["volume", "mix", "price", "newProducts", "lostProducts"] as const) {
    const v = b[key];
    steps.push({ key, label: STEP_LABELS[key], value: v, type: "delta", from: level, to: level + v });
    level += v;
  }
  steps.push({ key: "net", label: "Net change in spend", value: level, type: "net", from: 0, to: level });
  return { start: b.start, end: b.end, y0, y1, steps };
}

/** The bridge must close: start plus the five effects is the end. Used by tests and a dev-time assertion. */
export function bridgeResidual(pvm: PvmT, area: string, pair: string): number {
  const b = pvm.segments[area]?.[pair];
  if (!b) return NaN;
  return b.start + b.volume + b.mix + b.price + b.newProducts + b.lostProducts - b.end;
}

export type OwnerRow = { owner: string; spend0: number; spend1: number; brandSpend1: number; rank: number };

export function topOwners(owners: OwnersT, area: string, n = 12): OwnerRow[] {
  const rows = (owners.segments[area] ?? []).map((o) => ({
    owner: o.owner,
    spend0: o.spend[0],
    spend1: o.spend[o.spend.length - 1],
    brandSpend1: o.brandSpend[o.brandSpend.length - 1],
    rank: 0,
  }));
  rows.sort((a, b) => b.spend1 - a.spend1);
  rows.forEach((r, i) => (r.rank = i + 1));
  const head = rows.slice(0, n);
  const pinned = rows.find((r) => r.owner === owners.pinned);
  if (pinned && !head.includes(pinned) && pinned.spend1 > 0) head.push(pinned);
  return head;
}

export type CurvePoint = { k: number; median: number; n: number };

/** Median brand-spend index (100 = the year before generics) at each quarter since entry, across the events. */
export function medianCurve(erosion: ErosionT, minEvents = 10): CurvePoint[] {
  const byK = new Map<number, number[]>();
  for (const c of Object.values(erosion.curves)) {
    c.k.forEach((k, i) => {
      const v = c.brandIndex[i];
      if (v != null) byK.set(k, [...(byK.get(k) ?? []), v]);
    });
  }
  return [...byK.entries()]
    .filter(([, vs]) => vs.length >= minEvents)
    .map(([k, vs]) => ({ k, median: median(vs) ?? 0, n: vs.length }))
    .sort((a, b) => a.k - b.k);
}

export function medianAt(curve: CurvePoint[], k: number): CurvePoint | undefined {
  return curve.find((p) => p.k === k);
}

export type ProtectionBar = { key: string; label: string; spend: number; families: number };

export function protectionBars(loe: LoeT, area: string, fromYear = 2026, toYear = 2035): ProtectionBar[] {
  const seg = loe.segments[area];
  if (!seg) return [];
  const bars: ProtectionBar[] = [];
  let earlier = { spend: 0, families: 0 };
  let later = { spend: 0, families: 0 };
  for (const [yr, v] of Object.entries(seg.byYear)) {
    const y = Number(yr);
    if (y < fromYear) earlier = { spend: earlier.spend + v.spend, families: earlier.families + v.families };
    else if (y > toYear) later = { spend: later.spend + v.spend, families: later.families + v.families };
    else bars.push({ key: yr, label: yr, spend: v.spend, families: v.families });
  }
  for (let y = fromYear; y <= toYear; y++) {
    if (!bars.find((b) => b.key === String(y))) bars.push({ key: String(y), label: String(y), spend: 0, families: 0 });
  }
  bars.sort((a, b) => Number(a.key) - Number(b.key));
  if (earlier.families) bars.unshift({ key: "earlier", label: `Before ${fromYear}`, ...earlier });
  if (later.families) bars.push({ key: "later", label: `${toYear + 1}+`, ...later });
  return bars;
}

export type StateRow = {
  code: string;
  name: string;
  region: string;
  spend: number;
  rx: number;
  brandSpend: number;
  enrollment: number | null;
  perEnrollee: number | null;
  growth: number | null;
  flagged: boolean;
  reason: string | null;
};

export const FFS_SHIFT = 0.25;
export const SWING = 0.4;

export function stateRows(states: StatesT, area: string, year: number, lookback = 3): StateRow[] {
  const cur = states.data[area]?.[String(year)] ?? {};
  const prev = states.data[area]?.[String(year - lookback)] ?? {};
  return states.states.map((s) => {
    const [spend, rx, brandSpend] = cur[s.code] ?? [0, 0, 0];
    const enrollment = states.enrollment[String(year)]?.[s.code] ?? null;
    const prevSpend = prev[s.code]?.[0] ?? 0;
    const f1 = states.flags[String(year)]?.[s.code];
    const f0 = states.flags[String(year - lookback)]?.[s.code];
    let swing = 0;
    for (let y = year - lookback + 1; y <= year; y++) {
      const v = states.flags[String(y)]?.[s.code]?.[1];
      if (v != null) swing = Math.max(swing, Math.abs(v));
    }
    const ffsMove = f1 && f0 ? Math.abs(f1[0] - f0[0]) : 0;
    const reason =
      ffsMove >= FFS_SHIFT
        ? `fee-for-service share moved ${Math.round(ffsMove * 100)} points`
        : swing >= SWING
          ? `a year-on-year swing of ${Math.round(swing * 100)}%`
          : null;
    return {
      code: s.code,
      name: s.name,
      region: s.region,
      spend,
      rx,
      brandSpend,
      enrollment,
      perEnrollee: enrollment && enrollment > 0 ? spend / enrollment : null,
      growth: cagr(prevSpend, spend, lookback),
      flagged: reason !== null,
      reason,
    };
  });
}

export type ForecastView = {
  actual: number[];
  forecast: ForecastT[string]["forecast"];
  backtest: ForecastT[string]["backtest"];
};

export function forecastFor(f: ForecastT, area: string): ForecastView | null {
  return f[area] ?? null;
}

// A tile-grid map: one square per state, laid out roughly where the state sits. No geometry file to ship.
export const TILE_GRID: Record<string, [col: number, row: number]> = {
  AK: [0, 0], ME: [10, 0],
  WI: [5, 1], VT: [9, 1], NH: [10, 1],
  WA: [0, 2], ID: [1, 2], MT: [2, 2], ND: [3, 2], MN: [4, 2], IL: [5, 2], MI: [6, 2], NY: [8, 2], MA: [9, 2],
  OR: [0, 3], NV: [1, 3], WY: [2, 3], SD: [3, 3], IA: [4, 3], IN: [5, 3], OH: [6, 3], PA: [7, 3], NJ: [8, 3], CT: [9, 3], RI: [10, 3],
  CA: [0, 4], UT: [1, 4], CO: [2, 4], NE: [3, 4], MO: [4, 4], KY: [5, 4], WV: [6, 4], VA: [7, 4], MD: [8, 4], DE: [9, 4],
  AZ: [1, 5], NM: [2, 5], KS: [3, 5], AR: [4, 5], TN: [5, 5], NC: [6, 5], SC: [7, 5], DC: [8, 5],
  OK: [3, 6], LA: [4, 6], MS: [5, 6], AL: [6, 6], GA: [7, 6],
  HI: [0, 7], TX: [3, 7], FL: [7, 7],
};
