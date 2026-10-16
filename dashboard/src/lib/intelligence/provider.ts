import { spawn } from "node:child_process";
import type { Complete, Completion } from "./agent";

export const claudeCLI: Complete = (system, prompt) =>
  new Promise((resolve, reject) => {
    const child = spawn(
      /* turbopackIgnore: true */ process.env.CLAUDE_CLI_PATH ?? "claude",
      [
        "--print",
        "--output-format",
        "json",
        "--model",
        process.env.RX_AGENT_MODEL ?? "sonnet",
        "--tools",
        "",
        "--safe-mode",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--system-prompt",
        system,
      ],
      { windowsHide: true, stdio: ["pipe", "pipe", "ignore"] },
    );
    let output = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error("Model timed out"));
    }, 120_000);
    child.stdout.on("data", (chunk) => {
      output += chunk.toString("utf8");
      if (output.length > 1_000_000) {
        child.kill();
        reject(new Error("Oversized model reply"));
      }
    });
    child.on("error", () => {
      clearTimeout(timer);
      reject(new Error("Claude Code is unavailable"));
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      try {
        const result = JSON.parse(output);
        if (code || result.is_error) throw new Error("Model inference failed");
        const u = result.usage ?? {};
        resolve({
          text: result.result,
          model: Object.keys(result.modelUsage ?? {})[0] ?? "claude",
          inputTokens:
            (u.input_tokens ?? 0) +
            (u.cache_read_input_tokens ?? 0) +
            (u.cache_creation_input_tokens ?? 0),
          outputTokens: u.output_tokens ?? 0,
          costUsd: result.total_cost_usd,
        });
      } catch {
        reject(new Error("Model inference failed"));
      }
    });
    child.stdin.end(prompt, "utf8");
  });

export function provider(): Complete | undefined {
  const mode = process.env.RX_AGENT_PROVIDER ?? "guided";
  if (mode === "guided") return undefined;
  if (mode === "claude-cli") return claudeCLI;
  if (mode !== "groq" && mode !== "gemini")
    throw new Error("Unknown model provider");
  const model = process.env.RX_AGENT_MODEL;
  const key = process.env[mode === "groq" ? "GROQ_API_KEY" : "GEMINI_API_KEY"];
  if (!key || !model) throw new Error("Set the server model and provider key");
  return async (system, prompt): Promise<Completion> => {
    const gemini = mode === "gemini";
    const url = gemini
      ? `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`
      : "https://api.groq.com/openai/v1/chat/completions";
    const response = await fetch(url, {
      method: "POST",
      signal: AbortSignal.timeout(60_000),
      headers: {
        "Content-Type": "application/json",
        ...(gemini
          ? { "x-goog-api-key": key }
          : { Authorization: `Bearer ${key}` }),
      },
      body: JSON.stringify(
        gemini
          ? {
              systemInstruction: { parts: [{ text: system }] },
              contents: [{ role: "user", parts: [{ text: prompt }] }],
              generationConfig: {
                temperature: 0,
                maxOutputTokens: 1000,
                responseMimeType: "application/json",
              },
            }
          : {
              model,
              messages: [
                { role: "system", content: system },
                { role: "user", content: prompt },
              ],
              temperature: 0,
              max_tokens: 1000,
              response_format: { type: "json_object" },
            },
      ),
    });
    if (!response.ok)
      throw new Error(`Model service returned HTTP ${response.status}`);
    const value = await response.json();
    return gemini
      ? {
          text:
            value.candidates?.[0]?.content?.parts
              ?.map((p: { text?: string }) => p.text ?? "")
              .join("") ?? "",
          model,
          inputTokens: value.usageMetadata?.promptTokenCount,
          outputTokens: value.usageMetadata?.candidatesTokenCount,
        }
      : {
          text: value.choices?.[0]?.message?.content ?? "",
          model: value.model ?? model,
          inputTokens: value.usage?.prompt_tokens,
          outputTokens: value.usage?.completion_tokens,
        };
  };
}
