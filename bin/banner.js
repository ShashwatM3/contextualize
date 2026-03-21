import chalk from "chalk";
import boxen from "boxen";
import figlet from "figlet";
import { COLOR_BLUE as LIGHT_BLUE, COLOR_ORANGE as ACCENT } from "./print.js";

/**
 * Prints a welcome box, large “Contextualize” ASCII art, and a status line.
 */
export function printBanner() {
  const titleLine =
    chalk.red("*") +
    chalk.white(" Welcome to the ") +
    chalk.bold.white("Contextualize") +
    chalk.white(" CLI!");

  console.log(
    boxen(titleLine, {
      padding: { left: 1, right: 1, top: 0, bottom: 0 },
      margin: { top: 0, bottom: 1, left: 0, right: 0 },
      borderStyle: "round",
      borderColor: ACCENT,
    })
  );

  let art;
  try {
    art = figlet.textSync("Contextualize", {
      font: "Small",
      horizontalLayout: "fitted",
    });
  } catch {
    try {
      art = figlet.textSync("Contextualize", { font: "Standard" });
    } catch {
      art = "Contextualize";
    }
  }

  console.log(
    art
      .split("\n")
      .map((line) => chalk.bold.hex(ACCENT)(line))
      .join("\n")
  );

  console.log();
  console.log(
    "🎉 " +
      chalk.hex(LIGHT_BLUE)("Ready.") +
      " " +
      chalk.white("Press ") +
      chalk.bold.hex(LIGHT_BLUE)("Enter") +
      chalk.white(" to continue, or run ") +
      chalk.bold.hex(LIGHT_BLUE)("contextualize --help") +
      chalk.white(" for commands.")
  );
  console.log();
}
