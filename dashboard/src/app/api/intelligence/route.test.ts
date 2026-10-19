import { beforeEach, expect, test, vi } from "vitest";

const mocks = vi.hoisted(() => ({ answer: vi.fn(), provider: vi.fn() }));
vi.mock("@/lib/intelligence/agent", () => ({ answer: mocks.answer }));
vi.mock("@/lib/intelligence/provider", () => ({ provider: mocks.provider }));
vi.mock("@/lib/intelligence/load", () => ({ loadPipeline: () => ({}) }));
vi.mock("@/lib/load", () => ({ loadDataset: () => ({}) }));
import { POST } from "./route";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.answer.mockResolvedValue({ mode: "guided", facts: [] });
});
test("chunked oversize requests are rejected before invoking the analyst", async () => {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("x".repeat(4097)));
      controller.close();
    },
  });
  const request = new Request("https://rx.example/api/intelligence", {
    method: "POST", body, duplex: "half",
  } as RequestInit);
  expect((await POST(request)).status).toBe(413);
  expect(mocks.answer).not.toHaveBeenCalled();
  expect(mocks.provider).not.toHaveBeenCalled();
});
test("valid JSON still reaches the guided analyst and returns an uncached response", async () => {
  const request = new Request("https://rx.example/api/intelligence", {
    method: "POST", body: JSON.stringify({ question: "  Explain growth  " }),
  });
  const response = await POST(request);
  expect(response.status).toBe(200);
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect(mocks.answer.mock.calls[0][0]).toBe("Explain growth");
});
test("cross-origin requests and malformed JSON never invoke the analyst", async () => {
  const foreign = new Request("https://rx.example/api/intelligence", {
    method: "POST", headers: { origin: "https://other.example" }, body: "{}",
  });
  expect((await POST(foreign)).status).toBe(403);
  expect((await POST(new Request("https://rx.example/api/intelligence", { method: "POST", body: "{" }))).status).toBe(400);
  expect(mocks.answer).not.toHaveBeenCalled();
});
