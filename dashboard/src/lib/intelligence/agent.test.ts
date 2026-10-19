import { describe, expect, it, vi } from "vitest";
vi.mock("server-only", () => ({}));
import { loadDataset } from "../load";
import { loadPipeline } from "./load";
import { answer, finalFacts } from "./agent";
import { runTool } from "./tools";
import golden from "./territory-golden.json";

const data = loadDataset(),
  pipeline = loadPipeline();

describe("commercial evidence", () => {
  it("keeps the growth bridge reconciled to the actual spend change", () => {
    const result = runTool(
      {
        tool: "growth_bridge",
        args: { area: "Diabetes & obesity", from: 2022, to: 2025 },
      },
      data,
      pipeline,
      "r1",
    );
    expect(
      result.metrics.slice(1).reduce((s, m) => s + Number(m.value), 0),
    ).toBeCloseTo(Number(result.metrics[0].value), 0);
  });
  it.each(golden)(
    "matches independent Python territory scores: $area / $preset",
    (g) => {
      const result = runTool(
        {
          tool: "rank_territories",
          args: { area: g.area, year: 2025, preset: g.preset, limit: 10 },
        },
        data,
        pipeline,
        "r1",
      );
      const expected = Object.entries(g.rows)
        .sort((a, b) => a[1].P - b[1].P)
        .slice(0, 10);
      result.rows.forEach((row, i) => {
        expect(row.state).toBe(expected[i][0]);
        expect(row.score).toBeCloseTo(expected[i][1].O, 5);
      });
    },
  );
  it("does not silently substitute an unknown therapeutic area or period", () => {
    expect(() =>
      runTool(
        { tool: "market_summary", args: { area: "Made up" } },
        data,
        pipeline,
        "r1",
      ),
    ).toThrow("Unknown area");
    expect(() =>
      runTool(
        { tool: "growth_bridge", args: { from: 2025, to: 2022 } },
        data,
        pipeline,
        "r1",
      ),
    ).toThrow();
    expect(() =>
      runTool(
        { tool: "market_summary", args: { year: 2028 } },
        data,
        pipeline,
        "r1",
      ),
    ).toThrow();
  });
  it("connects an MSD product to pinned trial counts without inventing protection for a biologic", () => {
    const j = runTool(
      { tool: "product_pipeline", args: { family: "JANUVIA" } },
      data,
      pipeline,
      "r1",
    );
    expect(j.metrics.find((m) => m.id === "r1.JANUVIA_late")?.value).toBe(0);
    expect(j.sources[1].url).toContain(pipeline.provenance.commit);
    const k = runTool(
      { tool: "product_pipeline", args: { family: "KEYTRUDA" } },
      data,
      pipeline,
      "r1",
    );
    expect(
      k.metrics.find((m) => m.id === "r1.KEYTRUDA_protection")?.value,
    ).toContain("Biologic");
    expect(
      k.rows.every((r) =>
        String(r.url).startsWith("https://clinicaltrials.gov/study/NCT"),
      ),
    ).toBe(true);
  });
  it("discloses a forecast that lost to its baseline", () => {
    const f = runTool(
      { tool: "forecast_outlook", args: {} },
      data,
      pipeline,
      "r1",
    );
    expect(f.notes.join(" ")).toContain("worse than the baseline");
    expect(f.rows).toHaveLength(8);
  });
  it("rejects facts never observed in tool output", () => {
    expect(() => finalFacts(["invented"], [])).toThrow("not returned");
  });
});

describe("bounded planning", () => {
  it("runs a genuine multi-tool loop and returns only selected observed values", async () => {
    const calls = [
      { action: "tool", tool: "market_summary", args: {} },
      { action: "tool", tool: "product_pipeline", args: { family: "JANUVIA" } },
      { action: "finish", metricIds: ["r1.spend", "r2.JANUVIA_late"] },
    ];
    const complete = vi.fn(async () => ({
      text: JSON.stringify(calls.shift()),
      model: "test",
    }));
    const result = await answer(
      "Compare market spending with Januvia trials",
      data,
      pipeline,
      complete,
    );
    expect(result.refused).toBe(false);
    expect(result.evidence).toHaveLength(2);
    expect(result.facts.map((f) => f.id)).toEqual([
      "r1.spend",
      "r2.JANUVIA_late",
    ]);
  });
  it("stops repeated invalid or unsupported model output at the turn limit", async () => {
    const complete = vi.fn(async () => ({
      text: '{"action":"finish","metricIds":["fake.number"]}',
      model: "test",
    }));
    const result = await answer(
      "What was market spend?",
      data,
      pipeline,
      complete,
    );
    expect(result.refused).toBe(true);
    expect(result.facts).toEqual([]);
    expect(complete).toHaveBeenCalledTimes(6);
  });
  it("does not call a provider for unsupported patient or UAE sales data", async () => {
    const complete = vi.fn();
    const result = await answer("Show UAE sales", data, pipeline, complete);
    expect(result.refused).toBe(true);
    expect(complete).not.toHaveBeenCalled();
  });
  it("labels guided results and refuses unsupported requests instead of pretending to use a model", async () => {
    const result = await answer(
      "What drove diabetes spending growth from 2022 to 2025?",
      data,
      pipeline,
    );
    expect(result.mode).toBe("guided");
    expect(result.refused).toBe(false);
    expect(result.facts.some((f) => f.id === "r1.change")).toBe(true);
    expect((await answer("Tell me a joke", data, pipeline)).refused).toBe(true);
  });
});
