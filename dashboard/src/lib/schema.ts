import { z } from "zod";

// One schema per JSON file the Python export writes (src/rx/export_json.py). The page is built from these
// files, so a renamed or missing column fails the build instead of quietly drawing a wrong chart.

const nums = z.array(z.number());
const nullableNums = z.array(z.number().nullable());

export const Meta = z.object({
  built: z.string(),
  years: nums,
  areas: z.array(z.string()),
  orangeBookAsOf: z.string(),
  pinnedOwner: z.string(),
  rowsLoaded: z.number(),
  sources: z.array(z.object({ name: z.string(), by: z.string(), use: z.string() })),
});

const SeriesBlock = z.object({
  brandSpend: nums,
  genericSpend: nums,
  otherSpend: nums,
  brandRx: nums,
  genericRx: nums,
  otherRx: nums,
});
export const Market = z.object({ years: nums, series: z.record(z.string(), SeriesBlock) });

const Bridge = z.object({
  start: z.number(),
  volume: z.number(),
  mix: z.number(),
  price: z.number(),
  newProducts: z.number(),
  lostProducts: z.number(),
  end: z.number(),
});
export const Pvm = z.object({ pairs: z.array(z.string()), segments: z.record(z.string(), z.record(z.string(), Bridge)) });

export const Owners = z.object({
  pinned: z.string(),
  segments: z.record(z.string(), z.array(z.object({ owner: z.string(), spend: nums, brandSpend: nums }))),
});

export const Products = z.object({
  owners: z.record(
    z.string(),
    z.array(
      z.object({
        family: z.string(),
        area: z.string(),
        spend: nums,
        status: z.string(),
        coreEnd: z.string().nullable(),
        substanceEnd: z.string().nullable(),
        lastEnd: z.string().nullable(),
      }),
    ),
  ),
});

export const Erosion = z.object({
  events: z.array(
    z.object({
      ingredient: z.string(),
      brand: z.string().nullable(),
      entry: z.string().nullable(),
      runRateMusd: z.number().nullable(),
      brandIndexQ4: z.number().nullable(),
      brandIndexQ8: z.number().nullable(),
      genericShareQ4: z.number().nullable(),
      genericShareQ8: z.number().nullable(),
      moleculeIndexQ8: z.number().nullable(),
    }),
  ),
  curves: z.record(
    z.string(),
    z.object({ k: nums, brandIndex: nullableNums, genericShare: nullableNums, moleculeIndex: nullableNums }),
  ),
});

export const Loe = z.object({
  asOf: z.string(),
  segments: z.record(
    z.string(),
    z.object({
      byYear: z.record(z.string(), z.object({ families: z.number(), spend: z.number() })),
      groups: z.record(z.string(), z.object({ families: z.number(), spend: z.number() })),
    }),
  ),
  top: z.array(
    z.object({
      family: z.string(),
      owner: z.string(),
      area: z.string(),
      spend: z.number(),
      coreEnd: z.string().nullable(),
      substanceEnd: z.string().nullable(),
      lastEnd: z.string().nullable(),
    }),
  ),
});

export const States = z.object({
  states: z.array(z.object({ code: z.string(), name: z.string(), region: z.string(), expanded: z.boolean().nullable() })),
  data: z.record(z.string(), z.record(z.string(), z.record(z.string(), z.tuple([z.number(), z.number(), z.number()])))),
  enrollment: z.record(z.string(), z.record(z.string(), z.number())),
  flags: z.record(z.string(), z.record(z.string(), z.tuple([z.number(), z.number().nullable()]))),
  reconciliation: z.array(z.object({ year: z.number(), national: z.number(), states: z.number(), gapPct: z.number() })),
});

export const Forecast = z.record(
  z.string(),
  z.object({
    actual: nums,
    forecast: z.array(z.object({ year: z.number(), spend: z.number(), low: z.number(), high: z.number(), method: z.string() })),
    backtest: z.array(z.object({ method: z.string(), mape: z.number(), beatsNaive: z.boolean(), chosen: z.boolean() })),
  }),
);

export const Quality = z.object({
  checks: z.array(
    z.object({
      id: z.string(),
      dimension: z.string(),
      name: z.string(),
      result: z.string(),
      rule: z.string(),
      status: z.enum(["pass", "warn", "fail", "info"]),
      dollars: z.number().nullable(),
      note: z.string(),
    }),
  ),
  waterfall: z.array(z.object({ stage: z.string(), dollars: z.number(), sharePct: z.number() })),
});

export type MetaT = z.infer<typeof Meta>;
export type MarketT = z.infer<typeof Market>;
export type PvmT = z.infer<typeof Pvm>;
export type OwnersT = z.infer<typeof Owners>;
export type ProductsT = z.infer<typeof Products>;
export type ErosionT = z.infer<typeof Erosion>;
export type LoeT = z.infer<typeof Loe>;
export type StatesT = z.infer<typeof States>;
export type ForecastT = z.infer<typeof Forecast>;
export type QualityT = z.infer<typeof Quality>;

export type Dataset = {
  meta: MetaT;
  market: MarketT;
  pvm: PvmT;
  owners: OwnersT;
  products: ProductsT;
  erosion: ErosionT;
  loe: LoeT;
  states: StatesT;
  forecast: ForecastT;
  quality: QualityT;
};

export const ALL = "All areas";
