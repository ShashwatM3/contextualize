# Contextualize

**Contextualize** is a command-line tool that turns a repository into **AI-ready context**: it walks your project, infers dependencies, compiles focused documentation cards for those libraries, and keeps everything under a single workspace folder (`.contextualize/`) that agents and humans can read.

Use it when you want coding assistants to “know” your stack—frameworks, SDKs, and services—without pasting huge READMEs into every chat.

---

## What it does

1. **`init`** — Creates the `.contextualize/` layout and prints an in-terminal manual.
2. **`scan`** — Walks the tree (skipping heavy or sensitive paths), concatenates each folder’s files into `.contextualize/scan/concats/`, then uses an LLM to infer dependencies and writes `.contextualize/scan/dependencies.json`.
3. **`fetch docs`** — Reads those concat files to summarize what the codebase is building, then runs the Python **contextualize-docs** compiler to fetch and distill documentation into **context cards** under `.contextualize/docs/` (including `index.json` and `cards/`). On success it also installs/updates the **Cursor skill** at `~/.cursor/skills/using-contextualize/SKILL.md` so agents know how to use this workflow.
4. **`web`** — Serves a small local viewer (default port **4297**) for dependency/context cards—handy after a docs run.
5. ** 'debug' ** — Analyzes your code trace -> checks previous github issues + documentation for increased context -> produces RSA + Fix Suggestion 
6. **Free-form prompts** — Any invocation that is not a subcommand is sent to **Gemini** as a single prompt and streamed to your terminal.

Command history for the current project is appended to `.contextualize/cli-history.jsonl`.

---

## Requirements

| Requirement | Notes |
|-------------|--------|
| **Node.js** | ES modules; install deps with `npm install`. |
| **Python ≥ 3.11** | Needed for `contextualize fetch docs` (`contextualize_docs` package in this repo). |
| **API keys** | See [Environment variables](#environment-variables). |

---

## Installation (from this repository)

This package is marked **private** in `package.json`, so install it from a clone rather than expecting a global package name on the public npm registry.

```bash
git clone <your-fork-or-url> contextualize
cd contextualize
npm install
```

**Option A — run via npm script (good for trying it in this repo)**

```bash
npm run contextualize -- --help
```

**Option B — link the CLI globally**

```bash
npm link
# then, from any project:
contextualize --help
```

**Option C — call the binary directly**

```bash
node /path/to/contextualize/bin/contextualize.js --help
```

### Python environment (for `fetch docs`)

Install the docs compiler into a virtualenv (the CLI prefers `./.venv/bin/python3` if that exists):

```bash
cd /path/to/contextualize
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

The Node CLI sets `PYTHONPATH` to the repository root when invoking `python3 -m contextualize_docs`, so the module resolves whether or not your shell’s venv is active—as long as dependencies are installed somewhere on that interpreter.

---

## Environment variables

Create a **`.env.local`** at the **root of the project you are analyzing** (the directory from which you run `contextualize`). The CLI also loads `.env.local` next to `bin/` if present.

| Variable | Used for |
|----------|-----------|
| **`GEMINI_API_KEY`** | Dependency analysis during `scan`, codebase “task” understanding and **free-form prompts** (`contextualize <prompt>`). |
| **`VERCEL_AI_GATEWAY_KEY`** | Primary path for the **Python** docs compiler (see `contextualize_docs/config.py`). |
| **`GEMINI_API_KEY`** (again) | Fallback for the docs pipeline when the gateway key is not set. |

Optional tuning for the docs compiler (see `contextualize_docs/config.py`): `CONTEXTUALIZE_LLM_MODEL`, `CONTEXTUALIZE_LLM_TEMP`, `CONTEXTUALIZE_LLM_RETRIES`, `CONTEXTUALIZE_LLM_TIMEOUT`, `CONTEXTUALIZE_MIN_CONFIDENCE`.

---

## Quick start

From the **root of the codebase you want to contextualize**:

```bash
contextualize init
contextualize scan
contextualize fetch docs
contextualize web
```

Then open the URL printed in the terminal (or visit `http://127.0.0.1:4297`) to browse cards. Point your agent at `.contextualize/`—especially `scan/dependencies.json` and `docs/`.

---

## Commands

| Command | Description |
|---------|-------------|
| `contextualize` / `contextualize --help` | Banner and short usage. |
| `contextualize init` | Create `.contextualize/{scan,docs,cat}` and show the full manual. |
| `contextualize scan` | Build concat files and `dependencies.json`. |
| `contextualize fetch docs` | Requires prior `scan`; runs the Python compiler; refreshes the Cursor skill. |
| `contextualize web` | Local viewer for docs output. |
| `contextualize history` | Show commands recorded in this project. |
| `contextualize banner` | Banner only. |
| `contextualize terminal` | Lightweight terminal check (placeholder). |
| `contextualize <prompt>` | Stream an LLM reply (requires `GEMINI_API_KEY`). |

---

## `.contextualize/` layout (after a full run)

```
.contextualize/
├── cli-history.jsonl          # append-only log of CLI invocations
├── scan/
│   ├── concats/               # one .txt per folder (concatenated sources)
│   └── dependencies.json      # inferred libraries / services
├── docs/
│   ├── index.json             # card index for tooling and web UI
│   └── cards/                 # per-library context cards (JSON)
└── cat/                       # reserved / future use
```

---

## What `scan` skips

**Directories** (any path segment): `node_modules`, `__pycache__`, `.git`, `.contextualize`, `dist`, `build`, `.next`, `.venv`, `venv`, `.tox`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `coverage`, `.turbo`, `.cache`.

**File basename patterns**: `.env*`, `.pem`, `.key`, `.p12`, `.pfx`, `*.lock`, `*.log`.

---

## Troubleshooting

- **`GEMINI_API_KEY is not set`** — Add it to `.env.local` in the project root (or next to `bin/` for CLI-only use).
- **`No concat files found` / missing `dependencies.json`** — Run `contextualize scan` from the repository root first.
- **Rate limits during `scan`** — Dependency analysis calls the model per concat file; if you hit limits, partial results may still be written to `dependencies.json`. The CLI surfaces a short message when this happens.
- **Python errors on `fetch docs`** — Ensure Python 3.11+, run `pip install -e .` from this repo, and that `GEMINI_API_KEY` or `VERCEL_AI_GATEWAY_KEY` is set for the docs pipeline.

---

## Repository layout (high level)

- `bin/` — Node CLI (`contextualize.js`, helpers).
- `contextualize_docs/` — Python package: `compile-from-deps` and related pipeline.
- `pyproject.toml` — Python package metadata and dependencies (`contextualize-docs`).

---

## License / status

Version **0.1.0**. Behavior and flags may evolve; when in doubt, run `contextualize --help` or `contextualize init` for the latest in-terminal copy.
