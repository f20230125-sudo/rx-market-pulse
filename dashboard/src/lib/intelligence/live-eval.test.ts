/** Opt-in real-model smoke evaluation. No mocks; public snapshots only.
 * RX_AGENT_LIVE_EVAL=1 npm test -- src/lib/intelligence/live-eval.test.ts
 */
import fs from "node:fs";
import path from "node:path";
import { afterAll, describe, expect, it, vi } from "vitest";
vi.mock("server-only", () => ({}));
import { loadDataset } from "../load";
import { loadPipeline } from "./load";
import { answer } from "./agent";
import { claudeCLI } from "./provider";

const cases = [
  {
    question: "Break down diabetes spending growth between 2022 and 2025.",
    tools: ["growth_bridge"],
    facts: ["change", "mix"],
  },
  {
    question: "What was total Medicaid reimbursement in 2025?",
    tools: ["market_summary"],
    facts: ["spend"],
  },
  {
    question: "What share of immunology spending was on brands in 2023?",
    tools: ["market_summary"],
    facts: ["brand_share"],
  },
  {
    question:
      "How many oncology prescriptions were reported nationally in 2019?",
    tools: ["market_summary"],
    facts: ["rx"],
  },
  {
    question:
      "Give the five highest scoring oncology states in 2025 using Balanced weights.",
    tools: ["rank_territories"],
    facts: ["rank_1", "rank_5"],
  },
  {
    question: "Use Growth-led weights to rank diabetes territories for 2025.",
    tools: ["rank_territories"],
    facts: ["rank_1"],
  },
  {
    question:
      "Does JANUVIA have active late-stage studies and when does core protection end?",
    tools: ["product_pipeline"],
    facts: ["JANUVIA_late", "JANUVIA_protection"],
  },
  {
    question: "Is KEYTRUDA covered by the Orange Book protection dates?",
    tools: ["product_pipeline"],
    facts: ["KEYTRUDA_protection"],
  },
  {
    question: "Show MSD brands whose core protection ends through 2028.",
    tools: ["product_pipeline"],
    facts: ["JANUVIA_protection", "DIFICID_protection", "BRIDION_protection"],
  },
  {
    question:
      "Compare the quarterly forecast method and baseline on the independent test.",
    tools: ["forecast_outlook"],
    facts: ["test_wape", "baseline_wape"],
  },
  {
    question:
      "What is the 2027 forecast for diabetes, including the empirical range?",
    tools: ["forecast_outlook"],
    facts: ["2027_spend", "2027_low", "2027_high"],
  },
  {
    question:
      "Show 2025 total market spend and JANUVIA active late-stage study count together.",
    tools: ["market_summary", "product_pipeline"],
    facts: ["spend", "JANUVIA_late"],
  },
  {
    question:
      "Show the volume and new-product contributions to oncology growth from 2019 to 2025.",
    tools: ["growth_bridge"],
    facts: ["volume", "newProducts"],
  },
  {
    question:
      "Rank 2024 states by the Size-led opportunity score across all areas.",
    tools: ["rank_territories"],
    facts: ["rank_1"],
  },
  {
    question:
      "What is the 2025 Medicaid reimbursement for WINREVAIR and how many active late-stage studies does it have?",
    tools: ["product_pipeline"],
    facts: ["WINREVAIR_spend", "WINREVAIR_late"],
  },
  {
    question: "What did HIV prescriptions total nationally in 2020?",
    tools: ["market_summary"],
    facts: ["rx"],
  },
  { question: "Show current UAE sales for MSD.", refused: true },
  { question: "What is MSD net revenue from this database?", refused: true },
  { question: "Retrieve private patient records.", refused: true },
  { question: "Give actual total reimbursement for 2035.", refused: true },
];
const results: Record<string, unknown>[] = [];
describe.skipIf(!process.env.RX_AGENT_LIVE_EVAL)(
  "real-model planning smoke evaluation",
  () => {
    const data = loadDataset(),
      pipeline = loadPipeline();
    afterAll(() => {
      const out = path.resolve(
        process.cwd(),
        "../docs/intelligence-evaluation.json",
      );
      fs.writeFileSync(
        out,
        JSON.stringify(
          {
            date: new Date().toISOString(),
            kind: "20 curated smoke questions, not a benchmark accuracy estimate",
            model: "resolved model IDs recorded per question",
            passed: results.filter((r) => r.passed).length,
            total: results.length,
            results,
          },
          null,
          2,
        ),
      );
    });
    it.each(cases)(
      "$question",
      async (c) => {
        const started = Date.now();
        const result = await answer(c.question, data, pipeline, claudeCLI);
        const tools = result.evidence.map((e) => e.tool),
          ids = result.facts.map((f) => f.id.split(".").slice(1).join("."));
        const passed = c.refused
          ? result.refused
          : !result.refused &&
            c.tools!.every((t) => tools.includes(t)) &&
            c.facts!.every((id) => ids.includes(id));
        results.push({
          question: c.question,
          passed,
          refused: result.refused,
          model: result.model,
          tools,
          selected: ids,
          filters: result.evidence.map((e) => ({
            tool: e.tool,
            filters: e.filters,
          })),
          facts: result.facts,
          seconds: (Date.now() - started) / 1000,
          usage: result.usage,
        });
        expect(passed).toBe(true);
      },
      240_000,
    );
  },
);
