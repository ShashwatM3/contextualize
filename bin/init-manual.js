import boxen from "boxen";
import chalk from "chalk";
import {
  COLOR_ORANGE,
  printBlue,
  printBlueBullet,
  printOrange,
  printWhite,
  printWhiteBullet,
} from "./print.js";

/**
 * Detailed manual shown after `contextualize init` (after the banner + folder setup).
 */
export function printInitManual() {
  console.log();

  console.log(
    boxen(
      chalk.bold.white("Contextualize CLI") +
        chalk.white(" — what you can run from this folder"),
      {
        padding: { left: 1, right: 1, top: 0, bottom: 0 },
        margin: { top: 0, bottom: 1, left: 0, right: 0 },
        borderStyle: "round",
        borderColor: COLOR_ORANGE,
      }
    )
  );

  printOrange("Commands");
  printWhite("─".repeat(56));
  console.log();

  printWhiteBullet(
    chalk.bold.white("contextualize init") +
      chalk.white(
        " — Creates the local .contextualize layout and shows this manual (overview of every command)."
      )
  );
  printWhiteBullet(
    chalk.bold.white("contextualize scan") +
      chalk.white(
        " — Walks the project and builds scan artifacts under .contextualize (full implementation in progress)."
      )
  );
  printWhiteBullet(
    chalk.bold.white("contextualize fetch docs") +
      chalk.white(
        " — Inspects tooling in the repo and pulls in documentation so the agent stays contextualized (in progress)."
      )
  );
  printWhiteBullet(
    chalk.bold.white("contextualize history") +
      chalk.white(
        " — Lists every contextualize command you’ve run in this project (stored under .contextualize)."
      )
  );
  printWhiteBullet(
    chalk.bold.white("contextualize <anything else>") +
      chalk.white(
        " — Any text that isn’t a built-in command is sent to the AI as a single prompt (e.g. "
      ) +
      chalk.bold.white("contextualize explain this folder") +
      chalk.white(").")
  );

  console.log();
  printBlue("Shortcuts & extras");
  printWhite("─".repeat(56));
  console.log();

  printBlueBullet(
    chalk.bold.white("contextualize") +
      chalk.white(" or ") +
      chalk.bold.white("contextualize --help") +
      chalk.white(" — Banner plus a short usage summary.")
  );
  printBlueBullet(
    chalk.bold.white("contextualize banner") +
      chalk.white(" — Show the welcome banner only.")
  );
  printBlueBullet(
    chalk.bold.white("contextualize terminal") +
      chalk.white(" — Runs a quick terminal check (placeholder).")
  );

  console.log();
  printOrange(
    "Tip: run commands from your project root so paths and history stay consistent."
  );
  console.log();
}
