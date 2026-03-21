import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createOpenAI } from "@ai-sdk/openai";
import { streamText } from "ai";
import dotenv from "dotenv";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const envInBin = resolve(__dirname, ".env.local");
const envInRoot = resolve(__dirname, "..", ".env.local");
dotenv.config({ path: existsSync(envInBin) ? envInBin : envInRoot, quiet: true });

export function extractDependencySignals(concatText) {
  const lines = concatText.split('\n');
  const signals = [];

  const patterns = [
    /^import\s+.+\s+from\s+['"][^'"]+['"]/,        // ES import
    /require\(['"][^'"]+['"]\)/,                     // CommonJS require
    /^from\s+\S+\s+import/,                         // Python from X import
    /^import\s+\S+/,                                 // Python import X
    /[A-Z_]+=sk-|[A-Z_]+=pk-|[A-Z_]+_API_KEY/,     // API key env vars
    /[A-Z_]+_URL\s*=/,                              // Service URL env vars
  ];

  for (const line of lines) {
    const trimmed = line.trim();
    if (patterns.some(p => p.test(trimmed))) {
      signals.push(trimmed);
    }
  }

  // Also grab package.json / requirements.txt verbatim if present
  // (already small, include in full)
  
  return [...new Set(signals)].join('\n'); // deduplicate
}

export async function analyzeDependencies(concatText) {
  const signals = extractDependencySignals(concatText);
  if (!signals.trim()) return "[]";

  const openai = createOpenAI({ apiKey: process.env.OPENAI_API_KEY });

  const result = streamText({
    model: openai("gpt-4o-mini"),
    system: `You identify external third-party tools, APIs, and services used in a project.
Given import statements and environment variable names, return a JSON array of objects with shape:
{ "name": string, "category": string }
Categories: "AI/LLM", "voice/audio", "video", "database", "auth", "infra", "other".
Only include external services/libraries — not stdlib or internal modules.
Respond with raw JSON only — no markdown, no code fences, no explanation.`,
    prompt: `Dependencies and env vars found in project:\n\n${signals}`,
  });

  const raw = await result.text;
  // Strip markdown code fences if the model wraps the response
  return raw.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
}