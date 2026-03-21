#!/usr/bin/env node

import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { streamText } from "ai";
import dotenv from "dotenv";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const envInBin = resolve(__dirname, ".env.local");
const envInRoot = resolve(__dirname, "..", ".env.local");
dotenv.config({ path: existsSync(envInBin) ? envInBin : envInRoot, quiet: true });

function initPlaceholder() {
  // scan_codebase()
  return "scanning codebase";
}

function fetchDocs(inputJsonPath, outputDir) {
  const python = resolve(__dirname, "..", ".venv", "bin", "python3");
  const cmd = existsSync(python) ? python : "python3";
  const args = ["-m", "contextualize_docs", "--output-dir", outputDir];
  if (inputJsonPath) {
    args.push("--input", inputJsonPath);
  }
  try {
    const result = execSync([cmd, ...args].join(" "), {
      encoding: "utf8",
      cwd: resolve(__dirname, ".."),
    });
    return result;
  } catch (err) {
    console.error("Docs compilation failed:", err.message);
    process.exitCode = 1;
    return JSON.stringify({ success: false, error: err.message });
  }
}

function terminalPlaceholder() {
  return execSync("ls", { encoding: "utf8" });
}

async function main(argv) {
  const [command, subcommand] = argv;

  if (command === "init") {
    console.log(initPlaceholder());
    return;
  }

  else if (command === "fetch" && subcommand === "docs") {
    const inputPath = argv[2] || null;
    const outputDir = argv[3] || ".contextualize";
    console.log(fetchDocs(inputPath, outputDir));
    return;
  }

  else if (command === "terminal") {
    process.stdout.write(terminalPlaceholder());
    return;
  }

  else if (command) {
    const result = streamText({
      model: "openai/gpt-5.4",
      prompt: argv.join(" "),
    });
    for await (const textPart of result.textStream) {
      process.stdout.write(textPart);
    }
    process.stdout.write("\n");
    return;
  }

  console.log("Usage:");
  console.log("  contextualize init");
  console.log("  contextualize fetch docs");
  console.log("  contextualize terminal");
  process.exitCode = 1;
}

main(process.argv.slice(2)).catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
