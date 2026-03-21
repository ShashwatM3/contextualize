"""Quick debug script for the Gemini LLM provider.

Mirrors exactly what GeminiProvider does so you can isolate 404s
without running the full pipeline.

Usage:
    python debug_llm.py
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

# Load .env.local the same way AppConfig does
for parent in [Path.cwd(), *Path.cwd().parents]:
    candidate = parent / ".env.local"
    if candidate.is_file():
        load_dotenv(candidate, override=False)
        print(f"Loaded env from: {candidate}")
        break

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
RAW_MODEL = os.getenv("CONTEXTUALIZE_LLM_MODEL", "google/gemini-2.5-flash")
MODEL = RAW_MODEL.split("/", 1)[-1] if "/" in RAW_MODEL else RAW_MODEL

print(f"GEMINI_API_KEY set: {'yes' if GEMINI_API_KEY else 'NO — this will fail'}")
print(f"Model (raw):        {RAW_MODEL}")
print(f"Model (SDK):        {MODEL}")
print()

if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY is not set. Add it to .env.local")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)


async def test_generate() -> None:
    print(f"Sending test prompt to {MODEL!r} …")
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents="Say hello in one word.",
            config=genai_types.GenerateContentConfig(
                system_instruction="You are a helpful assistant.",
                temperature=0.2,
            ),
        )
        print(f"Response: {response.text!r}")
        print("\nSUCCESS — the model is reachable.")
    except Exception as exc:
        print(f"\nFAILED: {exc}")
        print()
        print("Listing available models so you can find the right name:")
        try:
            models = client.models.list()
            for m in models:
                print(f"  {m.name}")
        except Exception as list_exc:
            print(f"  Could not list models: {list_exc}")


asyncio.run(test_generate())
