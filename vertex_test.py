"""
vertex_test.py — Test GCP auth + Vertex AI Vector Search setup
Run: python vertex_test.py

Requires:
  pip install google-cloud-aiplatform google-genai python-dotenv
  GOOGLE_APPLICATION_CREDENTIALS and GCP_PROJECT_ID in .env.local
"""

import os
import json
import time
from dotenv import load_dotenv

load_dotenv(".env.local")

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = "us-central1"
INDEX_DISPLAY_NAME = "contextualize-issues-index"
DIMENSIONS = 768  # text-embedding-004 output size
LEAF_NODE_EMBEDDING_COUNT = 500
LEAF_NODES_TO_SEARCH_PERCENT = 7

# ── Fake seed issues ──────────────────────────────────────────────────────────

SEED_ISSUES = [
    {"id": "issue_001", "title": "ModuleNotFoundError: No module named 'httpx'", "body": "Running contextualize fetch docs throws ModuleNotFoundError for httpx. Fix: pip install httpx in the active venv.", "labels": ["bug", "dependency"]},
    {"id": "issue_002", "title": "Gemini API returns 429 during scan on large repos", "body": "Rate limit hit when scanning repos with 50+ folders. Fix: added exponential backoff with max 3 retries in analyze_codebase.js.", "labels": ["bug", "api"]},
    {"id": "issue_003", "title": "dependencies.json empty after scan", "body": "Scan completes but dependencies.json is empty. Root cause: concat files were empty because repo only had files in root, not subfolders. Fix: handle root-level files in scan.", "labels": ["bug"]},
    {"id": "issue_004", "title": "TypeError: Cannot read properties of undefined reading 'cards'", "body": "contextualize web crashes if fetch docs was never run. Fix: added guard for missing docs/index.json before serving.", "labels": ["bug"]},
    {"id": "issue_005", "title": "VERCEL_AI_GATEWAY_KEY not picked up in Python pipeline", "body": "Python compiler ignores .env.local in project root. Fix: load_dotenv must be called with explicit path relative to CWD.", "labels": ["bug", "config"]},
    {"id": "issue_006", "title": "fetch docs hangs indefinitely on DuckDuckGo scrape", "body": "doc_fetcher.py hangs when DuckDuckGo returns a CAPTCHA page. Fix: added 10s timeout + fallback to npm/PyPI only.", "labels": ["bug", "dependency"]},
    {"id": "issue_007", "title": "cards/ folder not created when output dir missing", "body": "Pipeline crashes with FileNotFoundError if .contextualize/docs/cards/ doesn't exist. Fix: mkdir -p in writer.py before writing cards.", "labels": ["bug"]},
    {"id": "issue_008", "title": "contextualize scan skips .ts files in src/", "body": "TypeScript files not included in concats. Root cause: file extension filter was too restrictive. Fix: added .ts, .tsx to allowed extensions.", "labels": ["bug"]},
    {"id": "issue_009", "title": "SyntaxError in generated card JSON — unescaped quotes", "body": "LLM occasionally returns JSON with unescaped double quotes inside string values. Fix: added post-generation JSON sanitizer in validate_and_fix stage.", "labels": ["bug", "llm"]},
    {"id": "issue_010", "title": "contextualize web port 4297 already in use", "body": "Server fails silently if port is taken. Fix: try ports 4297-4300 in sequence, print which one was bound.", "labels": ["enhancement"]},
    {"id": "issue_011", "title": "KeyError: 'homepage' when npm package has no homepage field", "body": "doc_fetcher crashes on packages that omit homepage in npm registry response. Fix: use .get('homepage') with None fallback.", "labels": ["bug", "dependency"]},
    {"id": "issue_012", "title": "scan performance: large monorepos take 5+ minutes", "body": "Scanning a monorepo with 200 folders is too slow. Fix: parallelize concat writes with Promise.all, batch Gemini calls to 5 at a time.", "labels": ["performance"]},
    {"id": "issue_013", "title": "GOOGLE_APPLICATION_CREDENTIALS not resolved correctly on Windows", "body": "Path with backslashes breaks GCP auth on Windows. Fix: normalize path with os.path.abspath before setting env var.", "labels": ["bug", "config"]},
    {"id": "issue_014", "title": "contextualize debug: last_error.log not found", "body": "debug command exits with error if .contextualize/last_error.log doesn't exist yet. Fix: create empty file on init, prompt user if empty.", "labels": ["bug"]},
    {"id": "issue_015", "title": "Pydantic ValidationError on ContextCard missing confidence field", "body": "LLM occasionally omits confidence score in card output. Fix: set default=0.5 in ContextCard model so validation doesn't hard-fail.", "labels": ["bug", "llm"]},
]

# ── Step 1: Auth check ────────────────────────────────────────────────────────

def check_auth():
    print("\n[1/4] Checking GCP auth...")
    try:
        from google.auth import default
        credentials, project = default()
        print(f"  ✓ Authenticated. Project from credentials: {project or '(not set)'}")
        print(f"  ✓ Using PROJECT_ID from env: {PROJECT_ID}")
    except Exception as e:
        print(f"  ✗ Auth failed: {e}")
        print("  → Make sure GOOGLE_APPLICATION_CREDENTIALS is set in .env.local")
        exit(1)

# ── Step 2: Embed issues ──────────────────────────────────────────────────────

def embed_issues():
    print("\n[2/4] Embedding seed issues with text-embedding-004...")
    from google.cloud import aiplatform
    aiplatform.init(project=PROJECT_ID, location=REGION)

    from vertexai.language_models import TextEmbeddingModel
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")

    texts = [f"{issue['title']} {issue['body']}" for issue in SEED_ISSUES]
    
    # Batch embed (max 5 per call)
    embeddings = []
    for i in range(0, len(texts), 5):
        batch = texts[i:i+5]
        results = model.get_embeddings(batch)
        embeddings.extend([r.values for r in results])
        print(f"  Embedded {min(i+5, len(texts))}/{len(texts)}")
        time.sleep(0.5)  # avoid rate limit

    print(f"  ✓ All {len(embeddings)} issues embedded. Dimension: {len(embeddings[0])}")
    return embeddings

# ── Step 3: Create index + upsert ────────────────────────────────────────────

def create_index_and_upsert(embeddings):
    print("\n[3/4] Creating Vertex AI Vector Search index...")
    from google.cloud import aiplatform

    # Check if index already exists
    existing = aiplatform.MatchingEngineIndex.list(filter=f'display_name="{INDEX_DISPLAY_NAME}"')
    if existing:
        print(f"  ✓ Index already exists: {existing[0].name}")
        index = existing[0]
    else:
        print("  Creating new index (this takes ~5-10 mins for first time)...")
        index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
            display_name=INDEX_DISPLAY_NAME,
            dimensions=DIMENSIONS,
            approximate_neighbors_count=10,
            leaf_node_embedding_count=LEAF_NODE_EMBEDDING_COUNT,
            leaf_nodes_to_search_percent=LEAF_NODES_TO_SEARCH_PERCENT,
            distance_measure_type="COSINE_DISTANCE",
        )
        print(f"  ✓ Index created: {index.name}")

    # Write embeddings to a JSONL file for batch upsert
    upsert_path = "/tmp/issues_upsert.json"
    with open(upsert_path, "w") as f:
        for issue, embedding in zip(SEED_ISSUES, embeddings):
            f.write(json.dumps({
                "id": issue["id"],
                "embedding": embedding,
                "restricts": [{"namespace": "labels", "allow": issue["labels"]}]
            }) + "\n")

    print(f"  ✓ Upsert file written to {upsert_path}")
    print(f"  → To upsert, run batch import via GCP console or gcloud. Index name: {index.name}")
    
    # Save index name for use in debug command
    os.makedirs(".contextualize", exist_ok=True)
    with open(".contextualize/vertex_config.json", "w") as f:
        json.dump({
            "index_name": index.name,
            "project_id": PROJECT_ID,
            "region": REGION,
            "dimensions": DIMENSIONS
        }, f, indent=2)
    print("  ✓ Saved index config to .contextualize/vertex_config.json")

    return index

# ── Step 4: Test query ────────────────────────────────────────────────────────

def test_query(embeddings):
    print("\n[4/4] Testing a query against the index...")
    print("  (Skipping live query — index needs an endpoint deployed first)")
    print("  → After deploying an index endpoint in GCP console, update vertex_config.json")
    print("    with 'endpoint_name' and re-run with --query flag")
    print("\n  ✓ Basic setup verified. Next step: deploy index endpoint in GCP console.")

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not PROJECT_ID:
        print("✗ GCP_PROJECT_ID not set in .env.local")
        exit(1)

    check_auth()
    embeddings = embed_issues()
    create_index_and_upsert(embeddings)
    test_query(embeddings)

    print("\n✓ Done. Check .contextualize/vertex_config.json for index details.")
    print("  Next: deploy an Index Endpoint in GCP console, then we wire it into contextualize debug.")