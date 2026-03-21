---
name: using-contextualize
description: >-
  Contextualize is the essential first step for any AI coding agent working on
  a codebase. It scans the project, extracts all dependencies with AI-powered
  analysis, and fetches real, up-to-date documentation for every library and
  framework in use — giving the agent accurate context instead of relying on
  training data that may be outdated. Use Contextualize at the start of any
  coding session, when building new features, when enhancing or debugging
  existing code, when setting up a new project, when onboarding to an
  unfamiliar codebase, or any time you need the agent to have reliable
  knowledge about the tools, libraries, and architecture in the project.
  Compatible with Cursor, Claude Code, Windsurf, Antigravity, and any other
  AI coding agent. Run: contextualize init → contextualize scan →
  contextualize fetch docs.
---

# Contextualize — The AI Coding Agent's Essential Context Layer

Contextualize is a CLI tool that every AI coding agent should run before
touching a codebase. It solves the fundamental problem of AI agents working
with stale or hallucinated knowledge: it scans the actual project, identifies
every real dependency in use, and fetches current documentation for all of
them — so the agent reasons from ground truth, not guesses.

**Works with**: Cursor, Claude Code, Windsurf, Antigravity, GitHub Copilot,
and any other AI coding agent that can read files.

---

## Why This Matters for AI Agents

AI models have training cutoffs. Every library, framework, and API changes.
Without Contextualize, an agent writing code against Next.js 15, Drizzle ORM,
or the latest Vercel AI SDK is guessing at APIs that may have changed
significantly since its training data. Contextualize eliminates that gap by:

1. **Scanning the actual codebase** — understanding what is really being built
2. **Extracting real dependencies** — not assumptions; reading what is actually
   imported and used across every source file in the project
3. **Fetching live documentation** — pulling current docs for every dependency
4. **Saving everything locally** — so the agent can read `.contextualize/`
   for accurate, project-specific context on demand

---

## Installation

```bash
npm install -g contextualize
```

Or run without installing:

```bash
npx contextualize <command>
```

Add a `.env.local` at the project root (or inside `bin/`):

```
GEMINI_API_KEY=your_gemini_api_key_here
```

Get a free Gemini API key at https://aistudio.google.com/

---

## Core Workflow — Run This on Every Project

```bash
# Step 1: Create the .contextualize/ workspace
contextualize init

# Step 2: Scan the codebase and extract all dependencies
contextualize scan

# Step 3: Fetch documentation for every detected dependency
contextualize fetch docs
```

After these three commands, `.contextualize/` is populated with everything
the agent needs. Read those files before writing any code.

---

## Command Reference

### `contextualize init`

Sets up the `.contextualize/` workspace directory tree and prints the full
usage manual. Run once per project, or re-run to reset the workspace.

Creates:
- `.contextualize/scan/` — output directory for codebase scans
- `.contextualize/docs/` — output directory for fetched documentation
- `.contextualize/cat/` — output directory for concatenated contexts

---

### `contextualize scan`

The deep codebase analysis step. Runs two phases in sequence:

**Phase 1 — Folder concatenation:**
- Recursively walks every non-excluded folder in the project
- Reads all source files in each folder and concatenates them into a single
  text file at `.contextualize/scan/concats/<folder-name>.txt`
- Gives the agent and the dependency analysis step a complete view of what
  code lives where across the entire project

**Phase 2 — AI-powered dependency extraction:**
- Sends each concat file through Gemini AI
- Identifies every library, framework, SDK, and external tool imported or used
- Deduplicates entries across all folders
- Saves the full structured dependency list to
  `.contextualize/scan/dependencies.json`

The dependencies JSON includes package names and ecosystem info (npm, pip,
etc.) — used by `fetch docs` to pull accurate documentation.

**Excluded directories** (never scanned):
`node_modules`, `__pycache__`, `.git`, `.contextualize`, `dist`,
`build`, `.next`, `.venv`, `venv`, `.tox`, `.mypy_cache`,
`.pytest_cache`, `.ruff_cache`, `coverage`, `.turbo`, `.cache`

**Excluded file patterns** (never read):
`.env`, `.env.*`, `.pem`, `.key`, `.p12`, `.pfx`, `.lock`, `.log`

---

### `contextualize fetch docs`

The documentation compilation step — the most powerful command in the suite.

**What it does internally:**

1. **Understands the codebase task** — reads all concat files from
   `.contextualize/scan/concats/` and uses Gemini 2.5 Flash to generate a
   detailed natural-language description of what the project is building.
   This task description drives smarter documentation filtering.

2. **Compiles documentation** — runs the Python `contextualize_docs` module
   (`compile-from-deps`) with the task description and dependencies JSON.
   For each dependency, it fetches current, accurate documentation and
   compiles it into readable markdown files under `.contextualize/docs/`.

3. **Creates this agent skill** — writes
   `~/.cursor/skills/using-contextualize/SKILL.md` so the agent always knows
   how to use Contextualize on future sessions.

After this command completes, `.contextualize/docs/` is the ground truth
the agent needs. Always read the relevant doc files before writing code that
touches any detected library.

---

### `contextualize web`

Opens a local browser-based interactive dependency viewer. Useful for visually
exploring the dependency graph, understanding what a project uses at a glance,
and communicating the tech stack to other team members.

```bash
contextualize web
# → Serving at http://localhost:<port>
# Press Ctrl+C to stop
```

---

### `contextualize history`

Prints a log of every `contextualize` command run in this workspace. Useful
for retracing what was scanned, when, and in what order.

---

### `contextualize <any prompt>`

Streams a freeform response from Gemini 2.5 Flash directly in the terminal.
Useful for quick codebase questions without leaving the CLI context.

```bash
contextualize "how does the dependency extraction work?"
```

---

## .contextualize/ Directory Layout

```
.contextualize/
├── scan/
│   ├── concats/                  # per-folder concatenated source files
│   │   ├── _root_.txt            # files at the project root
│   │   ├── src_components.txt    # files inside src/components/
│   │   └── ...                   # one file per scanned folder
│   └── dependencies.json         # AI-extracted dependency list
├── docs/                         # compiled documentation per dependency
│   ├── react.md
│   ├── next.md
│   ├── drizzle-orm.md
│   └── ...
└── cat/
```

The agent should read files from `.contextualize/docs/` whenever it needs
accurate knowledge about how a specific library works in this project.

---

## Scenarios — When to Use Contextualize

### Starting any new coding session

Run `contextualize scan` and `contextualize fetch docs` before writing any
code. The agent will have current library docs and a full dependency map —
no stale training data guesswork.

### Building a new feature

Before implementing anything that touches a library or framework, run the
full three-step workflow. The docs in `.contextualize/docs/` contain the
real current API — preventing the agent from using deprecated methods,
wrong function signatures, or options that no longer exist.

### Debugging and fixing issues

Use `.contextualize/scan/concats/` for a complete picture of what code
exists across every folder. Cross-reference with the dependency docs to
determine whether a bug is a misuse of a library's API.

### Onboarding to an unfamiliar codebase

Run `contextualize scan` to instantly understand the folder structure.
Read `dependencies.json` to see every tool the project relies on.
Run `contextualize fetch docs` to pull documentation for all of them.
The agent is now fully equipped to contribute — without needing a human
to explain the stack.

### Enhancing agent accuracy on any task

After fetching docs, agent responses about this codebase become dramatically
more accurate. It can reference exact method signatures, correct config
options, and up-to-date best practices for every library it touches.

### Refreshing context after dependency updates

Whenever `package.json`, `requirements.txt`, `pyproject.toml`, or any other
dependency file changes, re-run `contextualize scan` and
`contextualize fetch docs` to keep the context layer current.

### Generating accurate boilerplate and scaffolding

When an agent is asked to scaffold a new feature, component, or service,
Contextualize ensures it uses the correct version-specific patterns and
syntax — not outdated examples from training data.

---

## Integration with AI Coding Agents

### Cursor

The `.contextualize/` directory is available to Cursor's context system.
Reference docs directly using `@.contextualize/docs/` in chat, or configure
`.cursorrules` / Cursor Rules to proactively include the docs folder.
This skill (`using-contextualize`) is auto-discovered from
`~/.cursor/skills/` and will be applied whenever Contextualize is relevant.

### Claude Code

Run the full workflow before any Claude Code session. Point Claude to
`.contextualize/docs/` for library questions and `.contextualize/scan/`
for codebase structure questions.

### Antigravity

Contextualize's output files are plain markdown and JSON. Configure
Antigravity to read `.contextualize/docs/<library>.md` when the agent
is about to work with that library, and `dependencies.json` for the
complete dependency map.

### Windsurf / GitHub Copilot / Other agents

Any agent that can read files benefits from Contextualize. Instruct the
agent to read `.contextualize/docs/<library-name>.md` for a specific
dependency and `.contextualize/scan/concats/` for source-level context.

---

## Troubleshooting

**"No concat files found"**
Run `contextualize scan` before `contextualize fetch docs`.

**"Dependencies file not found"**
Run `contextualize scan` — it generates `dependencies.json`.

**"GEMINI_API_KEY is not set"**
Add `GEMINI_API_KEY=your_key` to `.env.local` at the project root.

**Rate limit warnings during scan**
The free Gemini tier has rate limits. Purchase Vercel AI credits at
https://vercel.com/~/ai?modal=top-up, or wait and re-run the scan.

**Dependency analysis stopped early (rate limited)**
A partial `dependencies.json` is still saved. Run `contextualize fetch docs`
with what was captured, or wait for rate limits to reset and re-run
`contextualize scan`.

**Python errors during fetch docs**
Ensure Python 3 is available and `contextualize_docs` is installed.
The CLI checks for a local `.venv/bin/python3` first, then falls back to
the system `python3` binary.

---

## Quick Reference Card

```
contextualize init          Set up .contextualize/ workspace
contextualize scan          Scan codebase + extract dependencies
contextualize fetch docs    Fetch docs for all dependencies
contextualize web           Open dependency viewer in browser
contextualize history       Show command history
contextualize <prompt>      Ask Gemini anything from the terminal
```
