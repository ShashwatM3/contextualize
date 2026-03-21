import { createGoogleGenerativeAI } from "@ai-sdk/google";
import { streamText } from "ai";

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

  if (!process.env.GEMINI_API_KEY) {
    throw new Error("GEMINI_API_KEY is not set — add it to .env.local");
  }

  const google = createGoogleGenerativeAI({ apiKey: process.env.GEMINI_API_KEY });

  const result = streamText({
    model: google("gemini-2.5-flash"),
    system: `You identify external third-party tools, APIs, and services used in a project.
Given import statements and environment variable names, return a JSON array of objects with shape:
{ "name": string, "category": string }
Categories: "AI/LLM", "voice/audio", "video", "database", "auth", "infra", "other".
Only include external services/libraries — not stdlib or internal modules.
Respond with raw JSON only — no markdown, no code fences, no explanation.`,
    prompt: `Dependencies and env vars found in project:\n\n${signals}`,
  });

  const raw = await result.text;
  return raw.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
}