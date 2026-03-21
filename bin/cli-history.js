import { appendFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { printBlue, printOrange, printWhite } from "./print.js";

const ROOT = ".contextualize";
export const HISTORY_FILENAME = "cli-history.jsonl";
export const HISTORY_PATH = join(ROOT, HISTORY_FILENAME);

export function ensureContextualizeRoot() {
  mkdirSync(ROOT, { recursive: true });
}

/**
 * Appends this invocation to the project-local history file.
 * @param {string[]} argv Arguments after `contextualize` (not including the binary name).
 */
export function appendHistory(argv) {
  try {
    ensureContextualizeRoot();
    const line =
      argv.length > 0 ? `contextualize ${argv.join(" ")}` : "contextualize";
    const entry = {
      ts: new Date().toISOString(),
      argv: [...argv],
      line,
    };
    appendFileSync(HISTORY_PATH, `${JSON.stringify(entry)}\n`, "utf8");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`Could not write CLI history: ${msg}`);
  }
}

/**
 * @returns {Array<{ ts: string, argv: string[], line: string }>}
 */
export function readHistoryEntries() {
  if (!existsSync(HISTORY_PATH)) return [];
  const raw = readFileSync(HISTORY_PATH, "utf8").trim();
  if (!raw) return [];
  return raw
    .split("\n")
    .filter(Boolean)
    .map((row) => JSON.parse(row));
}

export function printHistory() {
  const entries = readHistoryEntries();
  console.log();
  printBlue("Command history (this project, oldest → newest)");
  printWhite("─".repeat(56));
  console.log();

  if (entries.length === 0) {
    printOrange(
      "No commands recorded yet. Run contextualize from this directory and they will appear here."
    );
    console.log();
    return;
  }

  for (const e of entries) {
    printWhite(`${e.ts}  ${e.line}`);
  }
  console.log();
}
