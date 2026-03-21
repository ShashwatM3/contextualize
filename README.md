## CLI

- `contextualize` or `contextualize --help` — welcome banner + short usage
- `contextualize init` — set up `.contextualize/` and show the full command manual
- `contextualize scan` — scan the project (WIP)
- `contextualize fetch docs` — load tool docs for the agent (WIP)
- `contextualize history` — list commands run in this project (stored in `.contextualize/cli-history.jsonl`)
- `contextualize banner` — welcome banner only
- `contextualize <prompt>` — anything else is sent to the AI

---

Structure of the .contextualize folder:

.contextualize/
├── scan/
│   ├── COMPLETE.md
│   └── TOOLS.json
├── docs/
│   ├── LIVEKIT.md
│   └── VAPI.md
├── cat/
│   ├── ROOT.md
│   └── FOLDER_1.md
│   └── FOLDER_2.md
│   └── FOLDER_3.md
│   └── ...
└── ...


Atin will be working inside the fetchDocsPlaceholder

todos
=====
CREATE A NEW SKILL THAT MAKES CONTEXTUALIZE COMPATIBLE WITH AGENTS (SKILLS)
- manually

TO CREATE A NEW SKILL
npx skills init my-skill

