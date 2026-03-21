import { createServer } from "node:http";
import { existsSync, readFileSync, readdirSync } from "node:fs";
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

function escHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Load all context cards from .contextualize/docs/cards/ */
function loadCards(rootPath) {
  const indexPath = join(rootPath, ".contextualize/docs/index.json");
  if (!existsSync(indexPath)) return null;

  let index;
  try {
    index = JSON.parse(readFileSync(indexPath, "utf8"));
  } catch {
    return null;
  }

  const cardsDir = join(rootPath, ".contextualize/docs/cards");
  if (!existsSync(cardsDir)) return { index, cards: [] };

  const cards = [];
  try {
    for (const file of readdirSync(cardsDir)) {
      if (!file.endsWith(".json")) continue;
      try {
        const card = JSON.parse(readFileSync(join(cardsDir, file), "utf8"));
        cards.push(card);
      } catch {
        // skip unreadable card
      }
    }
  } catch {
    // skip unreadable dir
  }

  cards.sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
  return { index, cards };
}

function renderConfidenceBadge(conf) {
  const pct = Math.round((conf ?? 0) * 100);
  const color = pct >= 80 ? "var(--green)" : pct >= 50 ? "var(--blue)" : "var(--orange)";
  return `<span class="badge" style="color:${color};border-color:${color}">${pct}%</span>`;
}

function renderList(items, cls = "") {
  if (!items?.length) return "";
  const lis = items.map((s) => `<li>${escHtml(s)}</li>`).join("");
  return `<ul class="card-list ${cls}">${lis}</ul>`;
}

function renderApis(apis) {
  if (!apis?.length) return "";
  return apis.map((api) => `
    <div class="api-block">
      <div class="api-name">${escHtml(api.name)}</div>
      ${api.full_signature ? `<code class="api-sig">${escHtml(api.full_signature)}</code>` : ""}
      ${api.when_to_use ? `<p class="api-desc">${escHtml(api.when_to_use)}</p>` : ""}
      ${api.return_shape ? `<p class="api-return"><span class="label">returns</span> ${escHtml(api.return_shape)}</p>` : ""}
      ${api.constraints?.length ? `<p class="label">constraints</p>${renderList(api.constraints)}` : ""}
      ${api.pitfalls?.length ? `<p class="label">pitfalls</p>${renderList(api.pitfalls, "pitfall-list")}` : ""}
    </div>`).join("");
}

function renderExamples(examples) {
  if (!examples?.length) return "";
  return examples.map((ex) => `
    <div class="example-block">
      <div class="example-title">${escHtml(ex.title)}</div>
      <pre class="example-code"><code>${escHtml(ex.code)}</code></pre>
    </div>`).join("");
}

function renderCard(card) {
  const id = `card-${escHtml(card.normalized_name ?? card.library)}`;
  const sourceUrls = card.source_evidence?.source_urls ?? [];

  return `
  <article class="doc-card" id="${id}">
    <div class="doc-card-header">
      <div class="doc-card-title-row">
        <h2 class="doc-card-lib">${escHtml(card.library)}</h2>
        ${card.version ? `<span class="doc-card-version">v${escHtml(card.version)}</span>` : ""}
        ${renderConfidenceBadge(card.confidence)}
      </div>
      ${card.purpose_in_repo ? `<p class="doc-card-purpose">${escHtml(card.purpose_in_repo)}</p>` : ""}
      ${card.why_relevant_for_task ? `<p class="doc-card-why"><span class="label">why relevant</span> ${escHtml(card.why_relevant_for_task)}</p>` : ""}
    </div>

    ${card.rules_for_agent?.length ? `
    <div class="doc-card-section">
      <div class="section-title">rules for agent</div>
      ${renderList(card.rules_for_agent, "rules-list")}
    </div>` : ""}

    ${card.relevant_apis?.length ? `
    <div class="doc-card-section">
      <div class="section-title">relevant APIs</div>
      ${renderApis(card.relevant_apis)}
    </div>` : ""}

    ${card.minimal_examples?.length ? `
    <div class="doc-card-section">
      <div class="section-title">examples</div>
      ${renderExamples(card.minimal_examples)}
    </div>` : ""}

    ${card.gotchas?.length ? `
    <div class="doc-card-section">
      <div class="section-title">gotchas</div>
      ${renderList(card.gotchas, "gotcha-list")}
    </div>` : ""}

    ${card.repo_patterns?.length ? `
    <div class="doc-card-section">
      <div class="section-title">repo patterns</div>
      ${renderList(card.repo_patterns)}
    </div>` : ""}

    ${sourceUrls.length ? `
    <div class="doc-card-section">
      <div class="section-title">sources</div>
      <ul class="card-list">
        ${sourceUrls.map((u) => `<li><a class="src-link" href="${escHtml(u)}" target="_blank" rel="noopener">${escHtml(u)}</a></li>`).join("")}
      </ul>
    </div>` : ""}
  </article>`;
}

function buildHtml(deps, docsData) {
  // ── Dependency grid ─────────────────────────────────────────────────────
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
  const depSections = categories.map((cat) => {
    const items = grouped[cat]
      .map((name) =>
        `<li class="dep-item"><span class="bullet">•</span><span class="dep-name">${escHtml(name)}</span></li>`
      ).join("\n");
    return `
    <section class="category">
      <h2 class="category-title">${escHtml(cat)}</h2>
      <ul class="dep-list">${items}</ul>
    </section>`;
  }).join("\n");

  const total = deps.length;
  const catCount = categories.length;

  // ── Docs section ─────────────────────────────────────────────────────────
  const hasCards = docsData && docsData.cards.length > 0;
  const docsTab = hasCards ? `<button class="tab" id="tab-docs" onclick="switchTab('docs')">context cards <span class="tab-badge">${docsData.cards.length}</span></button>` : "";
  const docsPanel = hasCards ? `
  <div id="panel-docs" class="tab-panel hidden">
    <div class="docs-meta">
      <span class="docs-task-title">${escHtml(docsData.index.task_title ?? "")}</span>
      <span class="docs-generated">generated ${escHtml(docsData.index.generated_at?.slice(0, 10) ?? "")}</span>
    </div>
    <div class="cards-grid">
      ${docsData.cards.map(renderCard).join("\n")}
    </div>
  </div>` : "";

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>contextualize</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

    :root {
      --orange:  #D27D5B;
      --blue:    #7EB6FF;
      --green:   #4EC994;
      --red:     #FF7B7B;
      --bg:      #0a0a0a;
      --bg2:     #111111;
      --bg3:     #181818;
      --bg4:     #1e1e1e;
      --border:  #222222;
      --border2: #2a2a2a;
      --muted:   #555555;
      --muted2:  #777777;
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
      padding: 40px 32px 64px;
    }

    /* ── Header ── */
    header {
      border: 1px solid var(--orange);
      border-radius: 6px;
      padding: 14px 20px;
      display: inline-flex;
      flex-direction: column;
      gap: 4px;
      margin-bottom: 32px;
    }
    .header-title { color: var(--orange); font-size: 15px; font-weight: 700; letter-spacing: 0.04em; }
    .header-meta { color: var(--muted); font-size: 11px; }
    .header-meta span { color: var(--blue); }

    /* ── Tabs ── */
    .tabs {
      display: flex;
      gap: 4px;
      margin-bottom: 24px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 0;
    }
    .tab {
      background: none;
      border: none;
      border-bottom: 2px solid transparent;
      color: var(--muted2);
      cursor: pointer;
      font-family: inherit;
      font-size: 12px;
      font-weight: 500;
      letter-spacing: 0.06em;
      padding: 8px 16px 10px;
      text-transform: uppercase;
      transition: color .15s, border-color .15s;
      margin-bottom: -1px;
    }
    .tab:hover { color: var(--white); }
    .tab.active { color: var(--orange); border-bottom-color: var(--orange); }
    .tab-badge {
      background: var(--bg3);
      border: 1px solid var(--border2);
      border-radius: 10px;
      color: var(--blue);
      font-size: 10px;
      padding: 1px 6px;
      margin-left: 6px;
    }
    .tab-panel { }
    .tab-panel.hidden { display: none; }

    /* ── Dependency grid ── */
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
    .dep-list { list-style: none; display: flex; flex-direction: column; gap: 5px; }
    .dep-item { display: flex; align-items: baseline; gap: 8px; }
    .bullet { color: var(--orange); font-size: 10px; flex-shrink: 0; }
    .dep-name { color: var(--white); font-size: 12px; }

    /* ── Docs panel ── */
    .docs-meta {
      display: flex;
      align-items: baseline;
      gap: 16px;
      margin-bottom: 24px;
      color: var(--muted2);
      font-size: 11px;
    }
    .docs-task-title { color: var(--white); font-size: 12px; }
    .docs-generated { color: var(--muted); }

    .cards-grid {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    /* ── Context card ── */
    .doc-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }
    .doc-card-header {
      padding: 18px 20px 16px;
      border-bottom: 1px solid var(--border);
      background: var(--bg3);
    }
    .doc-card-title-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
    }
    .doc-card-lib {
      color: var(--orange);
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.03em;
    }
    .doc-card-version { color: var(--muted2); font-size: 11px; }
    .badge {
      border: 1px solid;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 700;
      padding: 1px 6px;
      letter-spacing: 0.05em;
      margin-left: auto;
    }
    .doc-card-purpose {
      color: var(--white);
      font-size: 12px;
      margin-bottom: 6px;
    }
    .doc-card-why {
      color: var(--muted2);
      font-size: 11px;
    }

    .doc-card-section {
      padding: 14px 20px;
      border-bottom: 1px solid var(--border);
    }
    .doc-card-section:last-child { border-bottom: none; }

    .section-title {
      color: var(--blue);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }

    .label {
      color: var(--muted2);
      font-size: 10px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      margin-right: 6px;
    }

    /* Lists */
    .card-list { list-style: none; display: flex; flex-direction: column; gap: 4px; }
    .card-list li { color: var(--white); font-size: 12px; padding-left: 12px; position: relative; }
    .card-list li::before { content: "•"; color: var(--muted); position: absolute; left: 0; }
    .rules-list li::before { color: var(--green); }
    .gotcha-list li::before { color: var(--orange); }
    .pitfall-list li { color: var(--muted2); font-size: 11px; }
    .pitfall-list li::before { color: var(--red); }

    /* API blocks */
    .api-block {
      background: var(--bg4);
      border: 1px solid var(--border2);
      border-radius: 6px;
      padding: 12px 14px;
      margin-bottom: 8px;
    }
    .api-block:last-child { margin-bottom: 0; }
    .api-name { color: var(--blue); font-size: 12px; font-weight: 700; margin-bottom: 4px; }
    .api-sig {
      display: block;
      color: var(--muted2);
      font-size: 11px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 4px 8px;
      margin-bottom: 6px;
      white-space: pre-wrap;
      word-break: break-all;
    }
    .api-desc { color: var(--white); font-size: 11px; margin-bottom: 4px; }
    .api-return { color: var(--muted2); font-size: 11px; margin-bottom: 4px; }

    /* Examples */
    .example-block { margin-bottom: 10px; }
    .example-block:last-child { margin-bottom: 0; }
    .example-title {
      color: var(--muted2);
      font-size: 11px;
      margin-bottom: 4px;
    }
    .example-code {
      background: var(--bg);
      border: 1px solid var(--border2);
      border-radius: 6px;
      color: var(--white);
      font-size: 11px;
      line-height: 1.7;
      overflow-x: auto;
      padding: 12px 14px;
      white-space: pre;
    }

    /* Source links */
    .src-link {
      color: var(--blue);
      font-size: 11px;
      text-decoration: none;
      word-break: break-all;
    }
    .src-link:hover { text-decoration: underline; }

    /* Footer */
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
    <div class="header-title">• contextualize</div>
    <div class="header-meta">
      <span>${total}</span> packages &nbsp;·&nbsp; <span>${catCount}</span> categories
      &nbsp;·&nbsp; ${hasCards ? `<span>${docsData.cards.length}</span> context cards` : `<span style="color:var(--muted)">no context cards yet — run fetch docs</span>`}
    </div>
  </header>

  <nav class="tabs">
    <button class="tab active" id="tab-deps" onclick="switchTab('deps')">dependencies <span class="tab-badge">${total}</span></button>
    ${docsTab}
  </nav>

  <div id="panel-deps" class="tab-panel">
    <main class="grid">
      ${depSections}
    </main>
  </div>

  ${docsPanel}

  <footer>auto-refreshes on reload &nbsp;·&nbsp; <span>contextualize web</span></footer>

  <script>
    function switchTab(name) {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
      document.getElementById('tab-' + name).classList.add('active');
      document.getElementById('panel-' + name).classList.remove('hidden');
    }
  </script>
</body>
</html>`;
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

    const docsData = loadCards(rootPath);
    const html = buildHtml(deps, docsData);
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(html);
  });

  server.listen(PORT, "127.0.0.1", () => {
    const url = `http://localhost:${PORT}`;
    try {
      execSync(`open "${url}"`);
    } catch {
      // non-macOS — just print
    }
    return url;
  });

  return `http://localhost:${PORT}`;
}
