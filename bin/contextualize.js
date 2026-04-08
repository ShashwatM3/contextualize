#!/usr/bin/env node

import { execSync, spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { createInterface } from "node:readline/promises";
import { homedir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createOpenAI } from "@ai-sdk/openai";
import { streamText } from "ai";
import dotenv from "dotenv";
import { printBanner } from "./banner.js";
import { appendHistory, printHistory } from "./cli-history.js";
import { printInitManual } from "./init-manual.js";
import { analyzeDependencies } from "./analyze_codebase.js";
import { startWebServer } from "./web.js";
import {
  COLOR_BLUE,
  COLOR_ORANGE,
  confirmation,
  confirmationBullet,
  printBlue,
  printBlueBullet,
  printBoxBlue,
  printBoxBlueBullet,
  printBoxOrange,
  printBoxOrangeBullet,
  printBoxWhite,
  printBoxWhiteBullet,
  printOrange,
  printOrangeBullet,
  printWhite,
  printWhiteBullet,
} from "./print.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const envInBin = resolve(__dirname, ".env.local");
const envInRoot = resolve(__dirname, "..", ".env.local");
dotenv.config({ path: existsSync(envInBin) ? envInBin : envInRoot, quiet: true });







/**
 * Runs a shell command and returns stdout as a string.
 * @param {string} cmd
 * @param {import("node:child_process").ExecSyncOptionsWithStringEncoding} [opts]
 */
function terminalCall(cmd, opts) {
  return execSync(cmd, { encoding: "utf8", maxBuffer: 100 * 1024 * 1024, ...opts });
}

function terminalPlaceholder() {
  return execSync("ls", { encoding: "utf8" });
}

const CONTEXTUALIZE_ROOT = ".contextualize";
const LAST_ERROR_FILE = join(CONTEXTUALIZE_ROOT, "last_error.log");
const DEBUG_DIR = join(CONTEXTUALIZE_ROOT, "debug");
const VERTEX_CONFIG_FILE = join(CONTEXTUALIZE_ROOT, "vertex_config.json");
const ISSUES_STORE_FILE = join(CONTEXTUALIZE_ROOT, "issues_store.json");
const SUGGESTED_LABELS = [
  "bug",
  "dependency",
  "config",
  "api",
  "llm",
  "performance",
  "enhancement",
  "infra",
];

function ensureContextualizeLayout() {
  mkdirSync(CONTEXTUALIZE_ROOT, { recursive: true });
  mkdirSync(join(CONTEXTUALIZE_ROOT, "scan"), { recursive: true });
  mkdirSync(join(CONTEXTUALIZE_ROOT, "docs"), { recursive: true });
  mkdirSync(join(CONTEXTUALIZE_ROOT, "cat"), { recursive: true });
  mkdirSync(DEBUG_DIR, { recursive: true });
  if (!existsSync(LAST_ERROR_FILE)) {
    writeFileSync(LAST_ERROR_FILE, "", "utf8");
  }
  if (!existsSync(ISSUES_STORE_FILE)) {
    writeFileSync(ISSUES_STORE_FILE, "[]\n", "utf8");
  }
}

async function promptUser(question) {
  const rl = createInterface({
    input: process.stdin,
    output: process.stdout,
  });
  try {
    const answer = await rl.question(question);
    return answer.trim();
  } finally {
    rl.close();
  }
}

async function askYesNo(question, defaultYes = true) {
  const suffix = defaultYes ? " [Y/n]: " : " [y/N]: ";
  const raw = (await promptUser(question + suffix)).toLowerCase();
  if (!raw) return defaultYes;
  return raw === "y" || raw === "yes";
}

function readJsonOrDefault(path, fallback) {
  if (!existsSync(path)) return fallback;
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return fallback;
  }
}

function deriveDependencySignal(trace) {
  const stack = String(trace || "");
  let dependencyIssueLikely = false;
  let reason = "No obvious dependency signal found.";
  let detectedPackage = null;

  const moduleMissing = stack.match(/No module named ['"]([^'"]+)['"]/i);
  const npmMissing = stack.match(/Cannot find module ['"]([^'"]+)['"]/i);

  if (moduleMissing?.[1] || npmMissing?.[1]) {
    dependencyIssueLikely = true;
    detectedPackage = moduleMissing?.[1] ?? npmMissing?.[1] ?? null;
    reason = `Stack trace indicates a missing module (${detectedPackage}).`;
  } else if (
    /ImportError|ModuleNotFoundError|Cannot find module|package .* not found/i.test(stack)
  ) {
    dependencyIssueLikely = true;
    reason = "Stack trace contains import or package resolution failure patterns.";
  }

  const deps = readJsonOrDefault(join(CONTEXTUALIZE_ROOT, "scan/dependencies.json"), []);
  if (!detectedPackage && Array.isArray(deps)) {
    const traceLower = stack.toLowerCase();
    const hit = deps.find((d) => {
      const name = String(d?.name || "").toLowerCase();
      return name && traceLower.includes(name);
    });
    if (hit?.name) {
      dependencyIssueLikely = true;
      detectedPackage = hit.name;
      reason = `Stack trace references dependency name "${hit.name}".`;
    }
  }

  return { dependencyIssueLikely, reason, detectedPackage };
}

function selectBestDocChunks(trace, maxChars = 9000) {
  const docsDir = join(CONTEXTUALIZE_ROOT, "docs");
  if (!existsSync(docsDir)) return [];
  const files = readdirSync(docsDir).filter((f) => f.endsWith(".md"));
  if (!files.length) return [];

  const tokens = Array.from(
    new Set(
      String(trace || "")
        .toLowerCase()
        .split(/[^a-z0-9._-]+/g)
        .filter((x) => x.length > 2)
        .slice(0, 200),
    ),
  );

  const scored = [];
  for (const file of files) {
    try {
      const raw = readFileSync(join(docsDir, file), "utf8");
      const text = raw.slice(0, 20000);
      const lower = text.toLowerCase();
      let score = 0;
      for (const t of tokens) {
        if (lower.includes(t)) score += 1;
      }
      if (score > 0) {
        scored.push({ file, score, text });
      }
    } catch {
      // skip unreadable files
    }
  }

  scored.sort((a, b) => b.score - a.score);
  const chunks = [];
  let used = 0;
  for (const item of scored.slice(0, 4)) {
    const budget = Math.max(500, maxChars - used);
    const snippet = item.text.slice(0, budget);
    chunks.push(`### ${item.file}\n${snippet}`);
    used += snippet.length;
    if (used >= maxChars) break;
  }
  return chunks;
}

function fetchSimilarIssuesFromStore(trace, k = 5) {
  const issues = readJsonOrDefault(ISSUES_STORE_FILE, []);
  if (!Array.isArray(issues) || !issues.length) return [];
  const traceLower = String(trace || "").toLowerCase();
  const tokens = traceLower.split(/[^a-z0-9._-]+/g).filter(Boolean);
  const unique = Array.from(new Set(tokens));

  const scored = issues
    .map((issue) => {
      const hay = `${issue.title || ""}\n${issue.body || ""}`.toLowerCase();
      let score = 0;
      for (const t of unique) {
        if (t.length < 3) continue;
        if (hay.includes(t)) score += 1;
      }
      return { issue, score };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map((x) => x.issue);

  return scored;
}

function runPythonInline(script) {
  const packageRoot = resolve(__dirname, "..");
  const pythonVenv = join(packageRoot, ".venv", "bin", "python3");
  const python = existsSync(pythonVenv) ? pythonVenv : "python3";
  const pythonPath = process.env.PYTHONPATH
    ? `${packageRoot}:${process.env.PYTHONPATH}`
    : packageRoot;

  return spawnSync(
    python,
    ["-c", script],
    {
      encoding: "utf8",
      cwd: process.cwd(),
      env: { ...process.env, PYTHONPATH: pythonPath },
      maxBuffer: 100 * 1024 * 1024,
    },
  );
}

function queryVertexSimilarIssues(trace, k = 5) {
  const cfg = readJsonOrDefault(VERTEX_CONFIG_FILE, null);
  if (!cfg || !cfg.project_id || !cfg.index_endpoint_name || !cfg.deployed_index_id) {
    return [];
  }

  const script = `
import json
import vertexai
from vertexai.language_models import TextEmbeddingModel
from google.cloud import aiplatform

cfg = json.loads(${JSON.stringify(JSON.stringify(cfg))})
trace = ${JSON.stringify(trace)}
top_k = int(${JSON.stringify(k)})

vertexai.init(project=cfg["project_id"], location=cfg.get("region", "us-central1"))
aiplatform.init(project=cfg["project_id"], location=cfg.get("region", "us-central1"))

model = TextEmbeddingModel.from_pretrained("text-embedding-005")
query_vec = model.get_embeddings([trace])[0].values

endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=cfg["index_endpoint_name"])
neighbors = endpoint.find_neighbors(
    deployed_index_id=cfg["deployed_index_id"],
    queries=[query_vec],
    num_neighbors=top_k,
)

items = []
for n in neighbors[0]:
    item = {
        "id": getattr(n, "id", None),
        "distance": getattr(n, "distance", None),
    }
    md = getattr(n, "embedding_metadata", None)
    if md and isinstance(md, dict):
        item["title"] = md.get("title")
        item["body"] = md.get("body")
        item["labels"] = md.get("labels")
    items.append(item)

print(json.dumps(items))
`;
  const result = runPythonInline(script);
  if (result.status !== 0) return [];
  try {
    const parsed = JSON.parse(result.stdout.trim());
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function addIssueToLocalStore(issue) {
  const issues = readJsonOrDefault(ISSUES_STORE_FILE, []);
  const arr = Array.isArray(issues) ? issues : [];
  arr.push(issue);
  writeFileSync(ISSUES_STORE_FILE, JSON.stringify(arr, null, 2) + "\n", "utf8");
}

function addIssueToVertex(issue) {
  const cfg = readJsonOrDefault(VERTEX_CONFIG_FILE, null);
  if (!cfg || !cfg.project_id || !cfg.index_name) {
    return { ok: false, message: "Missing .contextualize/vertex_config.json with project_id + index_name." };
  }
  const script = `
import json
import vertexai
from vertexai.language_models import TextEmbeddingModel
from google.cloud import aiplatform

cfg = json.loads(${JSON.stringify(JSON.stringify(cfg))})
issue = json.loads(${JSON.stringify(JSON.stringify(issue))})

vertexai.init(project=cfg["project_id"], location=cfg.get("region", "us-central1"))
aiplatform.init(project=cfg["project_id"], location=cfg.get("region", "us-central1"))
model = TextEmbeddingModel.from_pretrained("text-embedding-005")
text = f"{issue.get('title', '')}\\n{issue.get('body', '')}\\nlabels: {', '.join(issue.get('labels', []))}"
embedding = model.get_embeddings([text])[0].values

index = aiplatform.MatchingEngineIndex(index_name=cfg["index_name"])
index.upsert_datapoints([
    {
      "datapoint_id": issue["id"],
      "feature_vector": embedding,
      "restricts": [{"namespace": "labels", "allow_list": issue.get("labels", [])}],
      "embedding_metadata": {
        "title": issue.get("title", ""),
        "body": issue.get("body", ""),
        "labels": ",".join(issue.get("labels", [])),
      },
    }
])
print("ok")
`;
  const result = runPythonInline(script);
  if (result.status !== 0) {
    return { ok: false, message: result.stderr?.trim() || "Failed to upsert issue to Vertex." };
  }
  return { ok: true, message: "Issue added to Vertex index." };
}

function buildFixPromptMarkdown({
  stackTrace,
  dependencySignal,
  similarIssues,
  docContextChunks,
  rcaResponse,
}) {
  const issuesText = similarIssues.length
    ? similarIssues
      .map((i, idx) => `- [${idx + 1}] ${i.title || i.id || "issue"} | labels: ${Array.isArray(i.labels) ? i.labels.join(", ") : (i.labels || "")}\n  ${String(i.body || "").slice(0, 400)}`)
      .join("\n")
    : "- No similar issues found.";
  const docsText = docContextChunks.length
    ? docContextChunks.join("\n\n")
    : "No documentation context found in .contextualize/docs.";
  return `# Contextualize Debug -> Fix Prompt

## Stack Trace
\`\`\`
${stackTrace}
\`\`\`

## Dependency Signal
- dependencyIssueLikely: ${dependencySignal.dependencyIssueLikely}
- reason: ${dependencySignal.reason}
- detectedPackage: ${dependencySignal.detectedPackage ?? "n/a"}

## Similar Issues
${issuesText}

## Retrieved Documentation
${docsText}

## RCA + Fix Suggestion (OpenAI gpt-4.1-mini)
${rcaResponse}

## Task
Apply the smallest safe code change that fixes this issue. Include:
1) Root cause confirmation
2) Exact file-level edits
3) Validation steps and expected output
4) Edge cases and rollback plan
`;
}

async function runAddIssue() {
  ensureContextualizeLayout();
  printBoxBlue("Add issue to Contextualize issue memory");
  printWhiteBullet("Suggested labels: " + SUGGESTED_LABELS.join(", "));

  const title = await promptUser("Issue title: ");
  if (!title) {
    printBoxOrange("Title is required.");
    process.exitCode = 1;
    return;
  }
  const labelsRaw = await promptUser("Labels (comma-separated): ");
  const body = await promptUser("Issue details / resolution notes: ");
  if (!body) {
    printBoxOrange("Issue details are required.");
    process.exitCode = 1;
    return;
  }
  const labels = labelsRaw
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
  const issue = {
    id: `issue_${Date.now()}`,
    title,
    labels,
    body,
    created_at: new Date().toISOString(),
  };

  addIssueToLocalStore(issue);
  confirmation("Issue saved locally to .contextualize/issues_store.json");

  const shouldPushToVertex = await askYesNo("Also add this issue to Vertex AI index?", true);
  if (!shouldPushToVertex) return;

  const upsert = addIssueToVertex(issue);
  if (upsert.ok) {
    confirmation(upsert.message);
  } else {
    printBoxOrange(`Vertex upsert skipped/failed: ${upsert.message}`);
  }
}

async function runDebug(argv) {
  ensureContextualizeLayout();

  let trace = null;
  const traceFlagIndex = argv.findIndex((x) => x === "--trace");
  if (traceFlagIndex >= 0) {
    trace = argv.slice(traceFlagIndex + 1).join(" ").trim();
  }

  if (!trace) {
    const stored = existsSync(LAST_ERROR_FILE)
      ? readFileSync(LAST_ERROR_FILE, "utf8").trim()
      : "";
    if (stored) {
      trace = stored;
      printBlueBullet("Using stack trace from .contextualize/last_error.log");
    }
  }

  if (!trace) {
    trace = await promptUser("Paste stack trace: ");
  }

  if (!trace) {
    printBoxOrange("No stack trace provided.");
    process.exitCode = 1;
    return;
  }

  writeFileSync(LAST_ERROR_FILE, trace + "\n", "utf8");
  printBoxBlue("Running contextualize debug pipeline...");

  const dependencySignal = deriveDependencySignal(trace);
  const [similarIssues, docChunks] = await Promise.all([
    (async () => {
      const vertex = queryVertexSimilarIssues(trace, 5);
      if (vertex.length) return vertex;
      return fetchSimilarIssuesFromStore(trace, 5);
    })(),
    (async () => selectBestDocChunks(trace, 9000))(),
  ]);

  if (!process.env.OPENAI_API_KEY) {
    printBoxOrange("OPENAI_API_KEY is not set — cannot generate RCA.");
    process.exitCode = 1;
    return;
  }

  const openai = createOpenAI({ apiKey: process.env.OPENAI_API_KEY });
  const prompt = [
    "You are a senior debugging engineer.",
    "Given stack trace, likely dependency signal, similar issues, and docs snippets, produce:",
    "1) Root Cause Analysis",
    "2) Fix suggestion (concrete steps, small safe change)",
    "3) Validation checklist",
    "",
    `Stack trace:\n${trace}`,
    "",
    `Dependency signal:\n${JSON.stringify(dependencySignal, null, 2)}`,
    "",
    `Similar issues:\n${JSON.stringify(similarIssues, null, 2)}`,
    "",
    `Documentation snippets:\n${docChunks.join("\n\n") || "No docs found."}`,
  ].join("\n");

  const result = streamText({
    model: openai("gpt-4.1-mini"),
    prompt,
  });

  let rca = "";
  for await (const textPart of result.textStream) {
    process.stdout.write(textPart);
    rca += textPart;
  }
  process.stdout.write("\n");

  const md = buildFixPromptMarkdown({
    stackTrace: trace,
    dependencySignal,
    similarIssues,
    docContextChunks: docChunks,
    rcaResponse: rca.trim(),
  });
  const promptPath = join(DEBUG_DIR, "fix_prompt.md");
  writeFileSync(promptPath, md, "utf8");
  confirmation(`Fix prompt generated at ${promptPath}`);

  const shouldInvokeCodex = await askYesNo("Invoke Codex with this prompt now?", false);
  if (shouldInvokeCodex) {
    const cmd = `codex "$(cat "${promptPath}")"`;
    const invoke = spawnSync(cmd, {
      shell: true,
      stdio: "inherit",
      cwd: process.cwd(),
      env: process.env,
    });
    if (invoke.status !== 0) {
      printBoxOrange("Codex invocation failed.");
      process.exitCode = invoke.status ?? 1;
      return;
    }
    confirmation("Codex invocation complete.");
  }
}

function initPlaceholder() {
  printBanner();
  ensureContextualizeLayout();
  printInitManual();
}

/** Folder names that should never be scanned */
const EXCLUDED_DIRS = new Set([
  "node_modules",
  "__pycache__",
  ".git",
  ".contextualize",
  "dist",
  "build",
  ".next",
  ".venv",
  "venv",
  ".tox",
  ".mypy_cache",
  ".pytest_cache",
  ".ruff_cache",
  "coverage",
  ".turbo",
  ".cache",
]);

/** Patterns for files that should never be concatenated */
const EXCLUDED_FILE_PATTERNS = [
  /\.env($|\.)/, // .env, .env.local, .env.production …
  /\.pem$/,
  /\.key$/,
  /\.p12$/,
  /\.pfx$/,
  /\.lock$/,    // package-lock.json, yarn.lock, …
  /\.log$/,
];

function isExcludedFolder(folderPath) {
  return folderPath.split("/").some((part) => EXCLUDED_DIRS.has(part));
}

async function scanPlaceholder() {
  const output = terminalCall(
    "find . -type d ! -path '*/.*' | sed 's|^\./||'",
  );

  const arrOfFolders = output
    .trim()
    .split("\n")
    .filter(Boolean)
    .filter((f) => !isExcludedFolder(f));

  printBoxBlue("Scanning through all folders...")

  const rootPath = ".contextualize";
  const concatsOutputDir = join(rootPath, "scan/concats");

  mkdirSync(concatsOutputDir, { recursive: true });
  for (const folder of arrOfFolders) {
    let concatText;
    try {
      // List files in this folder (non-recursive), filter out excluded patterns
      const filesOutput = terminalCall(
        `find "${folder}" -maxdepth 1 -type f`,
        { maxBuffer: 10 * 1024 * 1024 }
      );
      const files = filesOutput
        .trim()
        .split("\n")
        .filter(Boolean)
        .filter((f) => !EXCLUDED_FILE_PATTERNS.some((p) => p.test(basename(f))));

      if (files.length === 0) {
        confirmationBullet("Scanned through " + folder + " (empty)");
        continue;
      }

      // Read each file individually so a single large file can't blow the buffer
      const parts = [];
      for (const file of files) {
        try {
          parts.push(readFileSync(file, "utf8"));
        } catch {
          // binary or unreadable file — skip silently
        }
      }
      concatText = parts.join("\n");
    } catch {
      confirmationBullet("Scanned through " + folder + " (skipped)");
      continue;
    }

    const safeName = folder === "." ? "_root_" : folder.replace(/\//g, "_");
    const outputFile = join(concatsOutputDir, `${safeName}.txt`);
    writeFileSync(outputFile, concatText, "utf8");
    confirmationBullet("Scanned through " + folder);
  }
  printBoxBlue("Dependency analysis...")
  const concatsDir = join(rootPath, "scan/concats");
  const concatFiles = readdirSync(concatsDir);
  const all_dependencies = [];
  let rateLimited = false;
  for (const concatFile of concatFiles) {
    const concatText = readFileSync(join(concatsDir, concatFile), "utf8");
    let raw;
    try {
      raw = await analyzeDependencies(concatText);
    } catch (err) {
      const isRateLimit =
        err?.statusCode === 429 ||
        err?.type === "rate_limit_exceeded" ||
        err?.cause?.statusCode === 429 ||
        String(err?.message ?? "").toLowerCase().includes("rate limit");
      if (isRateLimit) {
        rateLimited = true;
        printBoxOrange("Rate limit reached — dependency analysis stopped early.");
        printWhite("Free Vercel AI credits have temporary rate limits. Purchase credits at https://vercel.com/~/ai?modal=top-up to continue.");
        break;
      }
      printOrangeBullet(`Skipped ${concatFile} (error: ${err?.message ?? err})`);
      continue;
    }
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = [];
    }
    const deps = Array.isArray(parsed) ? parsed : parsed != null ? [parsed] : [];
    all_dependencies.push(...deps);
    confirmationBullet(`Scanned dependencies from ${concatFile}`);
  }
  // Deduplicate by lowercase name — scanning file-by-file can produce repeated entries
  const _seen = new Set();
  const unique_dependencies = all_dependencies.filter((dep) => {
    const key = (dep.name ?? "").toLowerCase();
    if (_seen.has(key)) return false;
    _seen.add(key);
    return true;
  });

  writeFileSync(join(rootPath, "scan/dependencies.json"), JSON.stringify(unique_dependencies, null, 2), "utf8");
  if (rateLimited) {
    confirmation(`Partial dependency analysis saved (rate limited) — ${unique_dependencies.length} unique deps`);
  } else {
    confirmation(`Dependencies analyzed and saved — ${unique_dependencies.length} unique deps`);
  }
}

/**
 * Reads all concat files from .contextualize/scan/concats and asks the AI
 * to synthesise a detailed task description for the codebase.
 * Returns the task string, or null if the directory is missing / empty.
 */
async function understandTask() {
  const concatsDir = join(process.cwd(), ".contextualize/scan/concats");
  if (!existsSync(concatsDir)) return null;

  let files;
  try {
    files = readdirSync(concatsDir).filter((f) => f.endsWith(".txt"));
  } catch {
    return null;
  }
  if (files.length === 0) return null;

  const MAX_CHARS = 20_000;
  const perFile = Math.floor(MAX_CHARS / files.length);
  const samples = [];

  for (const file of files) {
    try {
      const content = readFileSync(join(concatsDir, file), "utf8");
      const snippet = content.slice(0, perFile).trim();
      if (snippet) samples.push(`=== ${file} ===\n${snippet}`);
    } catch { /* skip unreadable */ }
  }

  if (samples.length === 0) return null;

  if (!process.env.OPENAI_API_KEY) {
    printBoxOrange("OPENAI_API_KEY is not set — cannot understand codebase task.");
    return null;
  }

  const openai = createOpenAI({ apiKey: process.env.OPENAI_API_KEY });
  const result = streamText({
    model: openai("gpt-4.1-mini"),
    system: `You are a senior engineer. Given concatenated source files from a project, write a detailed task description (3-4 sentences) that describes exactly what this project/codebase is trying to solve or build. Be specific about the technologies used, the core features, and the end goal. Write it in plain prose — no bullet points, no headings.`,
    prompt: `Analyze these source files and describe what this project is building/solving:\n\n${samples.join("\n\n")}`,
  });

  const task = await result.text;
  return task.trim();
}

/**
 * Creates (or updates) the personal Cursor skill for using Contextualize.
 * Reads content from the bundled contextualize-skill.md and writes it to
 * ~/.cursor/skills/using-contextualize/SKILL.md.
 */
function createContextualizeSkill() {
  printBoxBlue("Creating new agent skill...");

  const skillDir = join(homedir(), ".cursor", "skills", "using-contextualize");
  mkdirSync(skillDir, { recursive: true });

  const skillContent = readFileSync(join(__dirname, "contextualize-skill.md"), "utf8");
  writeFileSync(join(skillDir, "SKILL.md"), skillContent, "utf8");
  confirmation(`Successfully Created — skill saved to ${join(skillDir, "SKILL.md")}`);
}


/**
 * Full "fetch docs" workflow:
 * 1. Understand the codebase task from concat files.
 * 2. Call the Python compile-from-deps pipeline with that task.
 */
async function runFetchDocs() {
  printBoxBlue("Understanding your codebase...");

  const task = await understandTask();
  if (!task) {
    printBoxOrange(
      "No concat files found in .contextualize/scan/concats\n" +
      "Run `contextualize scan` first."
    );
    process.exitCode = 1;
    return;
  }

  printBlueBullet("Task: " + task.slice(0, 160) + (task.length > 160 ? "..." : ""));

  const depsFile = join(process.cwd(), ".contextualize/scan/dependencies.json");
  if (!existsSync(depsFile)) {
    printBoxOrange(
      "Dependencies file not found at .contextualize/scan/dependencies.json\n" +
      "Run `contextualize scan` first."
    );
    process.exitCode = 1;
    return;
  }

  printBoxBlue("Fetching and compiling documentation...");

  const packageRoot = resolve(__dirname, "..");
  const pythonVenv = join(packageRoot, ".venv", "bin", "python3");
  const python = existsSync(pythonVenv) ? pythonVenv : "python3";

  // Always ensure the contextualize package root is on PYTHONPATH so
  // contextualize_docs can be found regardless of which venv is active.
  const pythonPath = process.env.PYTHONPATH
    ? `${packageRoot}:${process.env.PYTHONPATH}`
    : packageRoot;

  const result = spawnSync(
    python,
    [
      "-m", "contextualize_docs",
      "compile-from-deps",
      "--deps-file", ".contextualize/scan/dependencies.json",
      "--output-dir", ".contextualize",
      "--task", task,
      "--verbose",
    ],
    {
      encoding: "utf8",
      maxBuffer: 100 * 1024 * 1024,
      cwd: process.cwd(),
      stdio: "inherit",
      env: { ...process.env, PYTHONPATH: pythonPath },
    },
  );

  if (result.status !== 0) {
    printBoxOrange("Docs compilation failed.");
    process.exitCode = result.status ?? 1;
    return;
  }

  confirmation("Documentation fetched and compiled successfully.");
  createContextualizeSkill();
}

function printUsage() {
  console.log("Usage:");
  console.log("  contextualize init          — manual + set up .contextualize/");
  console.log("  contextualize scan            — scan the project (WIP)");
  console.log("  contextualize web             — view dependencies in browser");
  console.log("  contextualize fetch docs      — contextualize agent with docs (WIP)");
  console.log("  contextualize debug [--trace] — RCA + fix suggestion from stack trace");
  console.log("  contextualize add issue       — add issue memory (local + Vertex)");
  console.log("  contextualize history         — commands you’ve run here");
  console.log("  contextualize banner          — welcome banner only");
  console.log("  contextualize terminal        — quick terminal check");
  console.log("  contextualize <prompt>       — send a prompt to the AI");
}

async function main(argv) {
  appendHistory(argv);

  if (argv.length === 0 || argv[0] === "--help" || argv[0] === "-h") {
    printBanner();
    printUsage();
    return;
  }

  const [command, subcommand] = argv;

  printBoxOrangeBullet("Contextualize CLI")

  if (command === "banner") {
    printBanner();
    return;
  }

  if (command === "init") {
    initPlaceholder();
    return;
  }

  if (command === "scan") {
    await scanPlaceholder();
    return;
  }

  if (command === "web") {
    const url = startWebServer(process.cwd());
    printBoxBlue("Dependencies viewer");
    printBlueBullet(`Serving at ${url}`);
    printWhite("Press Ctrl+C to stop.");
    return;
  }

  if (command === "history") {
    printHistory();
    return;
  }

  if (command === "debug") {
    await runDebug(argv.slice(1));
    return;
  }

  if (command === "add" && subcommand === "issue") {
    await runAddIssue();
    return;
  }

  else if (command === "fetch" && subcommand === "docs") {
    await runFetchDocs();
    return;
  }

  else if (command === "terminal") {
    process.stdout.write(terminalPlaceholder());
    return;
  }

  else if (command) {
    if (!process.env.OPENAI_API_KEY) {
      printBoxOrange("OPENAI_API_KEY is not set — add it to .env.local");
      process.exitCode = 1;
      return;
    }
    const openai = createOpenAI({ apiKey: process.env.OPENAI_API_KEY });
    const result = streamText({
      model: openai("gpt-4.1-mini"),
      prompt: argv.join(" "),
    });
    for await (const textPart of result.textStream) {
      process.stdout.write(textPart);
    }
    process.stdout.write("\n");
    return;
  }

  printUsage();
  process.exitCode = 1;
}

main(process.argv.slice(2)).catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
