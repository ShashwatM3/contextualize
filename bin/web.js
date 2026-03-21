import { createServer } from "node:http";
import { existsSync, readFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { join } from "node:path";

const PORT = 4297;

const CATEGORY_ORDER = [
  "AI/LLM",
  "database",
  "auth",
  "voice/audio",
  "video",
  "infra",
  "other",
];

function buildHtml(deps) {
  const grouped = {};
  for (const dep of deps) {
    const cat = dep.category ?? "other";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(dep.name);
  }

  const categories = [
    ...CATEGORY_ORDER.filter((c) => grouped[c]),
    ...Object.keys(grouped).filter((c) => !CATEGORY_ORDER.includes(c)),
  ];

  const sections = categories
    .map((cat) => {
      const items = grouped[cat]
        .map(
          (name) =>
            `<li class="dep-item"><span class="bullet">•</span><span class="dep-name">${escHtml(name)}</span></li>`
        )
        .join("\n");
      return `
      <section class="category">
        <h2 class="category-title">${escHtml(cat)}</h2>
        <ul class="dep-list">${items}</ul>
      </section>`;
    })
    .join("\n");

  const total = deps.length;
  const catCount = categories.length;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>contextualize — dependencies</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

    :root {
      --orange:  #D27D5B;
      --blue:    #7EB6FF;
      --green:   #4EC994;
      --bg:      #0a0a0a;
      --bg2:     #111111;
      --bg3:     #181818;
      --border:  #222222;
      --muted:   #555555;
      --white:   #e8e8e8;
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: var(--bg);
      color: var(--white);
      font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
      font-size: 13px;
      line-height: 1.6;
      min-height: 100vh;
      padding: 48px 32px;
    }

    header {
      border: 1px solid var(--orange);
      border-radius: 6px;
      padding: 14px 20px;
      display: inline-flex;
      flex-direction: column;
      gap: 4px;
      margin-bottom: 40px;
    }

    .header-title {
      color: var(--orange);
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.04em;
    }

    .header-meta {
      color: var(--muted);
      font-size: 11px;
    }

    .header-meta span {
      color: var(--blue);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 16px;
    }

    .category {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 16px 18px;
    }

    .category-title {
      color: var(--blue);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border);
    }

    .dep-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 5px;
    }

    .dep-item {
      display: flex;
      align-items: baseline;
      gap: 8px;
    }

    .bullet {
      color: var(--orange);
      font-size: 10px;
      flex-shrink: 0;
    }

    .dep-name {
      color: var(--white);
      font-size: 12px;
    }

    footer {
      margin-top: 48px;
      color: var(--muted);
      font-size: 11px;
    }

    footer span { color: var(--green); }
  </style>
</head>
<body>
  <header>
    <div class="header-title">• contextualize / dependencies</div>
    <div class="header-meta">
      <span>${total}</span> packages across <span>${catCount}</span> categories
      &nbsp;·&nbsp; .contextualize/scan/dependencies.json
    </div>
  </header>

  <main class="grid">
    ${sections}
  </main>

  <footer>auto-refreshes on reload &nbsp;·&nbsp; <span>contextualize web</span></footer>
</body>
</html>`;
}

function escHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function startWebServer(rootPath) {
  const depsPath = join(rootPath, ".contextualize/scan/dependencies.json");

  const server = createServer((_req, res) => {
    let deps = [];
    if (existsSync(depsPath)) {
      try {
        const raw = readFileSync(depsPath, "utf8");
        const parsed = JSON.parse(raw);
        deps = Array.isArray(parsed) ? parsed : [];
      } catch {
        deps = [];
      }
    }
    const html = buildHtml(deps);
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(html);
  });

  server.listen(PORT, "127.0.0.1", () => {
    const url = `http://localhost:${PORT}`;
    try {
      execSync(`open "${url}"`);
    } catch {
      // non-macOS fallback — just print
    }
    return url;
  });

  return `http://localhost:${PORT}`;
}
