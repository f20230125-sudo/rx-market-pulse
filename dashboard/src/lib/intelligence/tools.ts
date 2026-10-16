import { z } from "zod";
import { stateRows } from "../derive";
import { ALL, type Dataset } from "../schema";

export type Metric = {
  id: string;
  label: string;
  value: number | string;
  unit: string;
};
export type Evidence = {
  tool: string;
  filters: Record<string, unknown>;
  period: string;
  metrics: Metric[];
  rows: Record<string, unknown>[];
  notes: string[];
  sources: { title: string; url: string; asOf: string }[];
};
export type Pipeline = {
  meta: { asOf: string };
  provenance: { commit: string; source: string };
  revenue: {
    franchise: {
      family: string;
      area: string;
      spend_2025: number;
      core_end: string | null;
      active_pipeline: number;
      active_late: number;
      status: string;
    }[];
  };
  active: {
    nct_id: string;
    title: string;
    phase: string;
    area: string;
    pc_date: string | null;
    merck_products: string | null;
    is_late: boolean;
  }[];
};

const area = z.string().max(100).default(ALL);
const year = z.number().int().min(2019).max(2025).default(2025);
export const Calls = z.discriminatedUnion("tool", [
  z.object({
    tool: z.literal("market_summary"),
    args: z.object({ area, year }).strict(),
  }),
  z.object({
    tool: z.literal("growth_bridge"),
    args: z
      .object({
        area,
        from: z.number().int().min(2019).max(2024).default(2022),
        to: year,
      })
      .strict(),
  }),
  z.object({
    tool: z.literal("rank_territories"),
    args: z
      .object({
        area,
        year: z.number().int().min(2022).max(2025).default(2025),
        preset: z
          .enum(["Balanced", "Growth-led", "Size-led"])
          .default("Balanced"),
        limit: z.number().int().min(1).max(10).default(5),
      })
      .strict(),
  }),
  z.object({
    tool: z.literal("product_pipeline"),
    args: z
      .object({
        family: z.string().max(50).optional(),
        throughYear: z.number().int().min(2026).max(2040).default(2028),
      })
      .strict(),
  }),
  z.object({
    tool: z.literal("forecast_outlook"),
    args: z.object({ area }).strict(),
  }),
]);
export type Call = z.infer<typeof Calls>;
export const TOOL_HELP = `market_summary({area?,year?}): national spend, prescriptions, brand share; 2019–2025.
growth_bridge({area?,from?,to?}): exact volume/mix/spend-per-prescription/new/lost contributions; from < to.
rank_territories({area?,year?,preset?,limit?}): weighted territory score, reporting breaks neutralized; year 2022–2025; presets Balanced, Growth-led, Size-led.
product_pipeline({family?,throughYear?}): MSD products with protection ending by throughYear (default 2028), or one named family regardless of date; registered late-stage study links.
forecast_outlook({area?}): quarterly forecast and independent test against seasonal baseline.
Default area is All areas. All currency is gross US Medicaid reimbursement in USD, never MSD net revenue.`;

export function runTool(
  input: unknown,
  data: Dataset,
  pipeline: Pipeline,
  prefix: string,
): Evidence {
  const c = Calls.parse(input);
  const args = c.args;
  if ("area" in args && !data.market.series[args.area])
    throw new Error(`Unknown area: ${args.area}`);
  const metrics: Metric[] = [];
  const add = (
    id: string,
    label: string,
    value: number | string,
    unit: string,
  ) => {
    if (typeof value === "number" && !Number.isFinite(value))
      throw new Error("Nonfinite metric");
    metrics.push({ id: `${prefix}.${id}`, label, value, unit });
  };
  const evidence: Evidence = {
    tool: c.tool,
    filters: args,
    period: "",
    metrics,
    rows: [],
    notes: [
      "US Medicaid reimbursement before rebates; this is not company revenue or UAE sales.",
    ],
    sources: [
      {
        title: "Rx Market Pulse snapshot",
        url: "https://github.com/f20230125-sudo/rx-market-pulse/tree/main/dashboard/public/data",
        asOf: data.meta.built,
      },
    ],
  };
  if (c.tool === "market_summary") {
    const { area, year } = c.args;
    const i = data.market.years.indexOf(year),
      s = data.market.series[area];
    const spend = s.brandSpend[i] + s.genericSpend[i] + s.otherSpend[i];
    const rx = s.brandRx[i] + s.genericRx[i] + s.otherRx[i];
    evidence.period = String(year);
    add("spend", `${area}: gross reimbursement in ${year}`, spend, "USD");
    add("rx", `${area}: prescriptions in ${year}`, rx, "prescriptions");
    add(
      "brand_share",
      `${area}: brand share of spend in ${year}`,
      spend ? (100 * s.brandSpend[i]) / spend : 0,
      "%",
    );
  } else if (c.tool === "growth_bridge") {
    const { area, from, to } = c.args;
    if (from >= to) throw new Error("Growth period must increase");
    const bridge = data.pvm.segments[area]?.[`${from}-${to}`];
    if (!bridge) throw new Error("No bridge for that period");
    evidence.period = `${from}–${to}`;
    add(
      "change",
      `${area}: spend change, ${from}–${to}`,
      bridge.end - bridge.start,
      "USD",
    );
    for (const [key, label] of Object.entries({
      volume: "Prescription volume",
      mix: "Product mix",
      price: "Spend per prescription",
      newProducts: "New products",
      lostProducts: "Products leaving",
    })) {
      add(
        key,
        `${label} contribution, ${area}, ${from}–${to}`,
        bridge[key as keyof typeof bridge],
        "USD",
      );
    }
    evidence.notes.push(
      "An accounting decomposition, not causal attribution. Spend per prescription also changes with strength, pack size and days supplied.",
    );
  } else if (c.tool === "rank_territories") {
    const { area, year, preset, limit } = c.args;
    const rows = stateRows(data.states, area, year, 3).sort((a, b) =>
      a.name.localeCompare(b.name),
    );
    const growth = rows
      .map((r) => r.growth)
      .filter((v): v is number => v !== null)
      .sort((a, b) => a - b);
    const mid = growth.length >> 1;
    const median = growth.length
      ? growth.length % 2
        ? growth[mid]
        : (growth[mid - 1] + growth[mid]) / 2
      : 0;
    const factors = rows.map((r) => {
      const prior =
        data.states.data[area]?.[String(year - 3)]?.[r.code]?.[0] ?? 0;
      return [
        r.spend,
        prior >= 1e6 && !r.flagged && r.growth !== null ? r.growth : median,
        r.perEnrollee ?? 0,
        r.spend ? r.brandSpend / r.spend : 0,
      ];
    });
    const weights = {
      Balanced: [0.35, 0.25, 0.2, 0.2],
      "Growth-led": [0.2, 0.45, 0.2, 0.15],
      "Size-led": [0.55, 0.1, 0.2, 0.15],
    }[preset];
    const ranked = rows
      .map((r, i) => ({
        ...r,
        score:
          100 *
            factors[i].reduce(
              (sum, v, j) =>
                sum +
                (weights[j] * factors.filter((f) => f[j] < v).length) /
                  (rows.length - 1),
              0,
            ) +
          (7 + i) / 1e6,
      }))
      .sort((a, b) => b.score - a.score);
    evidence.period = `${year - 3}–${year}`;
    evidence.rows = ranked
      .slice(0, limit)
      .map((r, i) => ({
        rank: i + 1,
        state: r.code,
        name: r.name,
        score: r.score,
        spend: r.spend,
        reportingBreak: r.reason,
      }));
    evidence.rows.forEach((r, i) =>
      add(
        `rank_${i + 1}`,
        `${preset} rank ${i + 1}, ${area}, ${year}: ${r.name}`,
        r.score as number,
        "score / 100",
      ),
    );
    evidence.notes.push(
      "Weights apply to size, growth, spend per enrollee and brand share percentiles. Reporting breaks and prior spend below $1M get median growth. State cells are suppressed: ranks reflect reported spend.",
    );
  } else if (c.tool === "product_pipeline") {
    const { family, throughYear } = c.args;
    const items = pipeline.revenue.franchise.filter((r) =>
      family
        ? r.family === family.toUpperCase()
        : r.core_end &&
          Number(r.core_end.slice(0, 4)) <= throughYear &&
          Number(r.core_end.slice(0, 4)) >= 2026,
    );
    if (!items.length) throw new Error("No matching product in this snapshot");
    evidence.period = `2025 spend; trials as of ${pipeline.meta.asOf}`;
    evidence.sources.push({
      title: "Trial Pipeline Benchmark pinned snapshot",
      url: pipeline.provenance.source,
      asOf: pipeline.meta.asOf,
    });
    for (const r of items) {
      add(
        `${r.family}_spend`,
        `${r.family}: 2025 gross Medicaid reimbursement`,
        r.spend_2025,
        "USD",
      );
      add(
        `${r.family}_late`,
        `${r.family}: active late-stage registered studies`,
        r.active_late,
        "studies",
      );
      add(
        `${r.family}_protection`,
        `${r.family}: core protection date`,
        r.core_end ?? r.status,
        "date / status",
      );
    }
    const names = new Set(items.map((r) => r.family));
    evidence.rows = pipeline.active
      .filter(
        (r) =>
          r.is_late &&
          [...names].some((n) => (r.merck_products ?? "").includes(n)),
      )
      .map((r) => ({
        study: r.nct_id,
        title: r.title,
        phase: r.phase,
        primaryCompletion: r.pc_date,
        url: `https://clinicaltrials.gov/study/${r.nct_id}`,
      }));
    evidence.notes.push(
      "Study counts are not launch probabilities or a measure of pipeline value. Primary completion is not a results announcement. Biologics are outside Orange Book protection coverage.",
    );
  } else {
    const q = data.forecast[c.args.area].quarterly;
    evidence.period = "2026Q1–2027Q4; independent test 2024Q1–2025Q4";
    const chosen = q.methods.find((m) => m.chosen)!,
      naive = q.methods.find((m) => m.method === "seasonal-naive")!;
    if (chosen.test.wape !== null)
      add(
        "test_wape",
        "Selected method: independent test WAPE",
        chosen.test.wape,
        "%",
      );
    if (naive.test.wape !== null)
      add(
        "baseline_wape",
        "Seasonal baseline: independent test WAPE",
        naive.test.wape,
        "%",
      );
    add("method", "Method selected before the test", q.chosen, "method");
    const last = data.forecast[c.args.area].forecast.at(-1)!;
    add(
      "2027_spend",
      `${c.args.area}: 2027 forecast reimbursement`,
      last.spend,
      "USD",
    );
    add("2027_low", `${c.args.area}: 2027 empirical low`, last.low, "USD");
    add("2027_high", `${c.args.area}: 2027 empirical high`, last.high, "USD");
    evidence.rows = q.forecast;
    evidence.notes.push(q.bandDescription);
    if ((chosen.test.wape ?? Infinity) > (naive.test.wape ?? Infinity))
      evidence.notes.push(
        "The selected method performed worse than the baseline in the independent test.",
      );
  }
  return evidence;
}
