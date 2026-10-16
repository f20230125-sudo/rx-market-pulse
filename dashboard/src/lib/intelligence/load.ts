import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import type { Pipeline } from "./tools";

export function loadPipeline(): Pipeline {
  const base = path.join(process.cwd(), "public/data/pipeline");
  const provenance = JSON.parse(
    fs.readFileSync(path.join(base, "provenance.json"), "utf8"),
  );
  for (const [name, expected] of Object.entries(
    provenance.files as Record<string, string>,
  )) {
    if (!["meta.json", "revenue.json", "msd_active.json"].includes(name))
      throw new Error("Unknown snapshot file");
    const actual = createHash("sha256")
      .update(fs.readFileSync(path.join(base, name)))
      .digest("hex");
    if (actual !== expected)
      throw new Error("Pinned pipeline snapshot hash mismatch");
  }
  const read = (name: string) =>
    JSON.parse(
      fs.readFileSync(
        path.join(process.cwd(), "public/data/pipeline", name),
        "utf8",
      ),
    );
  return {
    meta: read("meta.json"),
    revenue: read("revenue.json"),
    active: read("msd_active.json"),
    provenance: read("provenance.json"),
  };
}
