import { z } from "zod";
import { answer } from "@/lib/intelligence/agent";
import { loadPipeline } from "@/lib/intelligence/load";
import { provider } from "@/lib/intelligence/provider";
import { loadDataset } from "@/lib/load";

export const runtime = "nodejs";
export const maxDuration = 300;
const Input = z
  .object({ question: z.string().trim().min(5).max(1000) })
  .strict();
let requests: number[] = [];
let active = 0;

export async function POST(request: Request) {
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(request.url).origin)
    return Response.json({ error: "Origin not allowed" }, { status: 403 });
  if (Number(request.headers.get("content-length") ?? 0) > 4096)
    return Response.json({ error: "Question too large" }, { status: 413 });
  const now = Date.now();
  requests = requests.filter((t) => now - t < 60_000);
  if (requests.length >= 8 || active >= 2)
    return Response.json(
      { error: "Please wait before asking another question." },
      { status: 429, headers: { "Retry-After": "60" } },
    );
  let input;
  try {
    input = Input.parse(await request.json());
  } catch {
    return Response.json(
      { error: "Enter a question of 5–1000 characters." },
      { status: 400 },
    );
  }
  requests.push(now);
  active++;
  try {
    return Response.json(
      await answer(input.question, loadDataset(), loadPipeline(), provider()),
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return Response.json(
      {
        error:
          "The model service is unavailable. Check the server provider configuration or try again later.",
      },
      { status: 503 },
    );
  } finally {
    active--;
  }
}
