import { test } from "vitest";
import assert from "node:assert/strict";
import { readBoundedJson, RequestBodyError } from "./request-body";

function streamed(chunks: Uint8Array[], headers: Record<string,string> = {}) {
  let cancelled = false;
  const body = new ReadableStream<Uint8Array>({
    pull(controller) { const next = chunks.shift(); if (next) controller.enqueue(next); else controller.close(); },
    cancel() { cancelled = true; },
  }, { highWaterMark: 0 });
  const request = new Request("https://example.test/api", { method: "POST", body, headers, duplex: "half" } as RequestInit);
  return { request, cancelled: () => cancelled };
}
const bytes = (s: string) => new TextEncoder().encode(s);
test("streamed bodies stop at the byte limit even without a trustworthy length header", async () => {
  for (const headers of [{}, { "content-length": "1" }] as Record<string,string>[]) {
    const input = streamed([bytes("x".repeat(9)), bytes("unread")], headers);
    await assert.rejects(readBoundedJson(input.request, 8), e => e instanceof RequestBodyError && e.status === 413);
    assert(input.cancelled());
  }
});
test("UTF-8 byte limits and split multibyte sequences are handled correctly", async () => {
  const value = bytes('{"text":"é"}');
  assert.deepEqual(await readBoundedJson(streamed([value.slice(0,10),value.slice(10)]).request,value.length),{text:"é"});
  await assert.rejects(readBoundedJson(streamed([value]).request,value.length-1),e => e instanceof RequestBodyError && e.status === 413);
});
test("invalid JSON and invalid UTF-8 return a client error", async () => {
  for (const value of [bytes("{"), new Uint8Array([34,255,34])]) {
    await assert.rejects(readBoundedJson(streamed([value]).request,100),e => e instanceof RequestBodyError && e.status === 400);
  }
});
