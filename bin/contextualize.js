#!/usr/bin/env node

import { execSync, spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createGoogleGenerativeAI } from "@ai-sdk/google";
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

function initPlaceholder() {
  printBanner();
  terminalCall("mkdir -p .contextualize/scan");
  terminalCall("mkdir -p .contextualize/docs");
  terminalCall("mkdir -p .contextualize/cat");
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

  if (!process.env.GEMINI_API_KEY) {
    printBoxOrange("GEMINI_API_KEY is not set — cannot understand codebase task.");
    return null;
  }

  const google = createGoogleGenerativeAI({ apiKey: process.env.GEMINI_API_KEY });
  const result = streamText({
    model: google("gemini-2.5-flash"),
    system: `You are a senior engineer. Given concatenated source files from a project, write a detailed task description (3-4 sentences) that describes exactly what this project/codebase is trying to solve or build. Be specific about the technologies used, the core features, and the end goal. Write it in plain prose — no bullet points, no headings.`,
    prompt: `Analyze these source files and describe what this project is building/solving:\n\n${samples.join("\n\n")}`,
  });

  const task = await result.text;
  return task.trim();
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
}

function printUsage() {
  console.log("Usage:");
  console.log("  contextualize init          — manual + set up .contextualize/");
  console.log("  contextualize scan            — scan the project (WIP)");
  console.log("  contextualize web             — view dependencies in browser");
  console.log("  contextualize fetch docs      — contextualize agent with docs (WIP)");
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

  else if (command === "fetch" && subcommand === "docs") {
    await runFetchDocs();
    return;
  }

  else if (command === "terminal") {
    process.stdout.write(terminalPlaceholder());
    return;
  }

  else if (command) {
    if (!process.env.GEMINI_API_KEY) {
      printBoxOrange("GEMINI_API_KEY is not set — add it to .env.local");
      process.exitCode = 1;
      return;
    }
    const google = createGoogleGenerativeAI({ apiKey: process.env.GEMINI_API_KEY });
    const result = streamText({
      model: google("gemini-2.5-flash"),
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
