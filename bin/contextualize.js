#!/usr/bin/env node

import { execSync } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { streamText } from "ai";
import dotenv from "dotenv";
import { printBanner } from "./banner.js";
import { appendHistory, printHistory } from "./cli-history.js";
import { printInitManual } from "./init-manual.js";
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
 */
function terminalCall(cmd) {
  return execSync(cmd, { encoding: "utf8" });
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

function scanPlaceholder() {
  printBanner();

  const output = terminalCall(
    "find . -type d ! -name '.*' ! -path '*/.*' | sed 's|^\./||'",
  );

  const arrOfFolders = output
    .trim()
    .split("\n")
    .filter(Boolean);

  printBoxOrange("Scanning through all folders...")

  const rootPath = ".contextualize";
  const concatsOutputDir = join(rootPath, "scan/concats");

  mkdirSync(concatsOutputDir, { recursive: true });
  for (const folder of arrOfFolders) {
    const concatText = terminalCall(
      `find "${folder}" -maxdepth 1 -type f -exec cat {} +`
    );
    const outputFile = join(concatsOutputDir, `${basename(folder)}.txt`);

    writeFileSync(outputFile, concatText, "utf8");

    confirmationBullet("Scanned through " + folder);
  }
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

function printUsage() {
  console.log("Usage:");
  console.log("  contextualize init          — manual + set up .contextualize/");
  console.log("  contextualize scan            — scan the project (WIP)");
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

  if (command === "banner") {
    printBanner();
    return;
  }

  if (command === "init") {
    initPlaceholder();
    return;
  }

  if (command === "scan") {
    scanPlaceholder();
    return;
  }

  if (command === "history") {
    printHistory();
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

  printUsage();
  process.exitCode = 1;
}

main(process.argv.slice(2)).catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
