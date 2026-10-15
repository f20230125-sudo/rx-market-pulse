import "server-only";
import fs from "node:fs";
import path from "node:path";
import { Erosion, Forecast, Loe, Market, Meta, Owners, Products, Pvm, Quality, States, type Dataset } from "./schema";

const DIR = path.join(process.cwd(), "public", "data");

function read<T>(file: string, schema: { parse: (v: unknown) => T }): T {
  const raw = JSON.parse(fs.readFileSync(path.join(DIR, file), "utf-8"));
  return schema.parse(raw);
}

/** Reads and validates every data file. Runs at build time on the server; the page ships the result. */
export function loadDataset(): Dataset {
  return {
    meta: read("meta.json", Meta),
    market: read("market.json", Market),
    pvm: read("pvm.json", Pvm),
    owners: read("owners.json", Owners),
    products: read("products.json", Products),
    erosion: read("erosion.json", Erosion),
    loe: read("loe.json", Loe),
    states: read("states.json", States),
    forecast: read("forecast.json", Forecast),
    quality: read("quality.json", Quality),
  };
}
