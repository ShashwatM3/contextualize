import chalk from "chalk";
import boxen from "boxen";

export const COLOR_ORANGE = "#D27D5B";
export const COLOR_BLUE = "#7EB6FF";

/** Unicode bullet + space, prepended in *Bullet variants */
const BULLET = "• ";

/** Green tick shown at the end of `confirmation()` / `confirmationBullet()` */
const TICK = "\u2713";

const boxDefaults = {
  padding: { left: 1, right: 1, top: 0, bottom: 0 },
  margin: { top: 0, bottom: 0, left: 0, right: 0 },
  borderStyle: "round",
};

/** @param {unknown} text */
export function printWhite(text) {
  console.log(chalk.white(String(text)));
}

/** @param {unknown} text */
export function printOrange(text) {
  console.log(chalk.hex(COLOR_ORANGE)(String(text)));
}

/** @param {unknown} text */
export function printBlue(text) {
  console.log(chalk.hex(COLOR_BLUE)(String(text)));
}

/** @param {unknown} text */
export function printBoxWhite(text) {
  console.log(
    boxen(chalk.white(String(text)), {
      ...boxDefaults,
      borderColor: "white",
    })
  );
}

/** @param {unknown} text */
export function printBoxOrange(text) {
  console.log(
    boxen(chalk.hex(COLOR_ORANGE)(String(text)), {
      ...boxDefaults,
      borderColor: COLOR_ORANGE,
    })
  );
}

/** @param {unknown} text */
export function printBoxBlue(text) {
  console.log(
    boxen(chalk.hex(COLOR_BLUE)(String(text)), {
      ...boxDefaults,
      borderColor: COLOR_BLUE,
    })
  );
}

/**
 * Prints text in green with a green tick (✓) at the end.
 * @param {unknown} text
 */
export function confirmation(text) {
  const line = chalk.green(String(text)) + chalk.green(` ${TICK}`);
  console.log(line);
}

// —— Bullet variants (same behavior + “• ” before the text; tick still at end for confirmation) ——

/** @param {unknown} text */
export function printWhiteBullet(text) {
  console.log(chalk.white(BULLET + String(text)));
}

/** @param {unknown} text */
export function printOrangeBullet(text) {
  console.log(chalk.hex(COLOR_ORANGE)(BULLET + String(text)));
}

/** @param {unknown} text */
export function printBlueBullet(text) {
  console.log(chalk.hex(COLOR_BLUE)(BULLET + String(text)));
}

/** @param {unknown} text */
export function printBoxWhiteBullet(text) {
  console.log(
    boxen(chalk.white(BULLET + String(text)), {
      ...boxDefaults,
      borderColor: "white",
    })
  );
}

/** @param {unknown} text */
export function printBoxOrangeBullet(text) {
  console.log(
    boxen(chalk.hex(COLOR_ORANGE)(BULLET + String(text)), {
      ...boxDefaults,
      borderColor: COLOR_ORANGE,
    })
  );
}

/** @param {unknown} text */
export function printBoxBlueBullet(text) {
  console.log(
    boxen(chalk.hex(COLOR_BLUE)(BULLET + String(text)), {
      ...boxDefaults,
      borderColor: COLOR_BLUE,
    })
  );
}

/**
 * Same as {@link confirmation}, with a green bullet before the text and a green tick at the end.
 * @param {unknown} text
 */
export function confirmationBullet(text) {
  const line =
    chalk.green(BULLET + String(text)) + chalk.green(` ${TICK}`);
  console.log(line);
}
