import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { areaGrowth, bridgeResidual, cagr, kpis, medianAt, medianCurve, protectionBars, stateRows, TILE_GRID, topOwners, waterfall } from "./derive";
import { ALL, Erosion, Loe, Market, Meta, Owners, Pvm, States } from "./schema";

// These read the real exported files, so they also prove the exports match the schemas.
const read = (f: string) => JSON.parse(fs.readFileSync(path.join(process.cwd(), "public", "data", f), "utf-8"));
const meta = Meta.parse(read("meta.json"));
const market = Market.parse(read("market.json"));
const pvm = Pvm.parse(read("pvm.json"));
const owners = Owners.parse(read("owners.json"));
const erosion = Erosion.parse(read("erosion.json"));
const loe = Loe.parse(read("loe.json"));
const states = States.parse(read("states.json"));

describe("kpis", () => {
  const k = kpis(market, ALL);
  it("covers 2019 to 2025", () => {
    expect([k.y0, k.y1]).toEqual([2019, 2025]);
  });
  it("matches the published national figures", () => {
    expect(k.spend1 / 1e9).toBeCloseTo(116.89, 1);
    expect(k.spend0 / 1e9).toBeCloseTo(73.05, 1);
  });
  it("shows brands as a small share of prescriptions and a large share of spend", () => {
    expect(k.brandRxShare1).toBeLessThan(0.2);
    expect(k.brandSpendShare1).toBeGreaterThan(0.8);
  });
  it("area series add to the all-areas series", () => {
    const sum = meta.areas.reduce((acc, a) => acc + kpis(market, a).spend1, 0);
    expect(sum).toBeCloseTo(k.spend1, -3);
  });
});

describe("cagr", () => {
  it("compounds", () => expect(cagr(100, 121, 2)).toBeCloseTo(0.1, 10));
  it("refuses a zero or negative base", () => {
    expect(cagr(0, 5, 3)).toBeNull();
    expect(cagr(5, 0, 3)).toBeNull();
  });
});

describe("areaGrowth", () => {
  const rows = areaGrowth(market, meta.areas);
  it("is sorted by 2025 spend", () => {
    for (let i = 1; i < rows.length; i++) expect(rows[i - 1].spend1).toBeGreaterThanOrEqual(rows[i].spend1);
  });
  it("finds immunology and diabetes among the fastest growers", () => {
    const fast = [...rows].filter((r) => r.cagr != null).sort((a, b) => (b.cagr ?? 0) - (a.cagr ?? 0)).slice(0, 4).map((r) => r.area);
    expect(fast).toContain("Immunology & inflammation");
    expect(fast).toContain("Diabetes & obesity");
  });
});

describe("waterfall", () => {
  it("closes for every segment and pair", () => {
    for (const seg of Object.keys(pvm.segments))
      for (const pair of pvm.pairs) {
        const r = bridgeResidual(pvm, seg, pair);
        if (!Number.isNaN(r)) expect(Math.abs(r)).toBeLessThan(1);
      }
  });
  it("ends on a net change equal to end minus start", () => {
    const br = waterfall(pvm, ALL, "2022-2025")!;
    const net = br.steps[br.steps.length - 1];
    expect(net.type).toBe("net");
    expect(net.value).toBeCloseTo(br.end - br.start, -1);
    expect(br.steps[br.steps.length - 2].to).toBeCloseTo(net.value, -1);
  });
  it("returns null for a pair that does not exist", () => expect(waterfall(pvm, ALL, "1999-2000")).toBeNull());
  it("shows prescription volume falling while the mix shift adds the most", () => {
    const by = Object.fromEntries(waterfall(pvm, ALL, "2022-2025")!.steps.map((s) => [s.key, s.value]));
    expect(by.volume).toBeLessThan(0);
    expect(by.mix).toBeGreaterThan(by.price);
  });
});

describe("topOwners", () => {
  it("keeps the pinned company in the list even when it is outside the top", () => {
    const rows = topOwners(owners, ALL, 8);
    expect(rows.some((r) => r.owner === owners.pinned)).toBe(true);
    expect(rows[0].spend1).toBeGreaterThanOrEqual(rows[1].spend1);
  });
});

describe("medianCurve", () => {
  const curve = medianCurve(erosion);
  it("is about 100 the quarter before generics arrive", () => {
    const at = medianAt(curve, -1)!;
    expect(at.median).toBeGreaterThan(85);
    expect(at.median).toBeLessThan(115);
  });
  it("falls well below 100 two years after entry", () => {
    const at = medianAt(curve, 8)!;
    expect(at.median).toBeLessThan(70);
    expect(at.n).toBeGreaterThanOrEqual(6);
  });
});

describe("protectionBars", () => {
  const bars = protectionBars(loe, ALL);
  it("has one bar per year 2026 to 2035, in order", () => {
    const years = bars.filter((b) => /^\d{4}$/.test(b.key)).map((b) => Number(b.key));
    expect(years).toEqual([2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033, 2034, 2035]);
  });
  it("accounts for all protected spend", () => {
    const protectedTotal = Object.values(loe.segments[ALL].byYear).reduce((a, v) => a + v.spend, 0);
    expect(bars.reduce((a, b) => a + b.spend, 0)).toBeCloseTo(protectedTotal, -3);
  });
});

describe("stateRows", () => {
  const rows = stateRows(states, ALL, 2025, 3);
  it("covers 51 states", () => expect(rows).toHaveLength(51));
  it("flags the states that changed how they report", () => {
    const flagged = rows.filter((r) => r.flagged).map((r) => r.code);
    for (const code of ["NY", "NC", "VA"]) expect(flagged).toContain(code);
    expect(flagged).not.toContain("TX");
  });
  it("computes spend per enrollee from spend and enrollment", () => {
    const ca = rows.find((r) => r.code === "CA")!;
    expect(ca.perEnrollee).toBeCloseTo(ca.spend / ca.enrollment!, 6);
  });
});

describe("tile grid", () => {
  it("gives every state its own square", () => {
    const codes = states.states.map((s) => s.code).sort();
    expect(Object.keys(TILE_GRID).sort()).toEqual(codes);
    const cells = new Set(Object.values(TILE_GRID).map(([c, r]) => `${c},${r}`));
    expect(cells.size).toBe(51);
  });
});
