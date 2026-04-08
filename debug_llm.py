"""Quick debug script for the OpenAI LLM provider.

Mirrors exactly what OpenAIProvider does so you can isolate 404s
without running the full pipeline.

Usage:
    python debug_llm.py
"""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load .env.local the same way AppConfig does
for parent in [Path.cwd(), *Path.cwd().parents]:
    candidate = parent / ".env.local"
    if candidate.is_file():
        load_dotenv(candidate, override=False)
        print(f"Loaded env from: {candidate}")
        break

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("CONTEXTUALIZE_LLM_MODEL", "gpt-4.1-mini")

print(f"OPENAI_API_KEY set: {'yes' if OPENAI_API_KEY else 'NO — this will fail'}")
print(f"Model:              {MODEL}")
print()

if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY is not set. Add it to .env.local")
    sys.exit(1)

print(f"Sending test prompt to {MODEL!r} …")
try:
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello in one word."},
            ],
            "temperature": 0.2,
        },
        timeout=30.0,
    )
    response.raise_for_status()
    text = response.json()["choices"][0]["message"]["content"]
    print(f"Response: {text!r}")
    print("\nSUCCESS — the model is reachable.")
except Exception as exc:
    print(f"\nFAILED: {exc}")
