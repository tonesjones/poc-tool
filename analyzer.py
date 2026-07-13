from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, MODEL

ANALYSIS_PROMPT = """\
You are analyzing customer conversation transcripts to extract structured data for a \
Mutual Success Plan (MSP).

Synthesize ALL transcripts provided. When multiple transcripts are present, prioritize \
the most recent information and note any evolution in requirements between sessions.

Return ONLY a valid JSON object — no markdown fences, no explanation, just the JSON.

Required structure:
{
  "customer_name": "string",
  "industry": "string or null",
  "company_size": "string or null",
  "primary_contact": "string or null",
  "pain_points": [
    {"description": "string", "priority": "high|medium|low", "confidence": "certain|likely|uncertain"}
  ],
  "business_goals": [
    {"description": "string", "timeframe": "string or null", "confidence": "certain|likely|uncertain"}
  ],
  "technical_requirements": [
    {"description": "string", "confidence": "certain|likely|uncertain"}
  ],
  "success_criteria": [
    {"description": "string", "measurable": true, "confidence": "certain|likely|uncertain"}
  ],
  "stakeholders": [
    {"name": "string", "role": "string", "involvement": "decision_maker|champion|user|blocker"}
  ],
  "timeline": {
    "trial_start": "string or null",
    "trial_end": "string or null",
    "decision_date": "string or null",
    "key_milestones": ["string"]
  },
  "risks": [
    {"description": "string", "likelihood": "high|medium|low", "mitigation": "string or null"}
  ],
  "trial_scope": {
    "modules_to_test": ["string"],
    "use_cases": ["string"],
    "out_of_scope": ["string"]
  },
  "context_notes": "string — important caveats or cross-transcript observations"
}

Confidence rules:
- "certain": customer stated it directly and clearly
- "likely": implied clearly or mentioned across multiple transcripts
- "uncertain": vague, conflicting across transcripts, or inferred — items with this confidence
  will be flagged [NEEDS CONFIRMATION] in the final document for the rep to verify

Transcripts:
{transcripts}
"""


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def load_transcripts(customer_dir: Path) -> tuple[dict[str, str], str]:
    """Load all .md transcript files. Returns ({filename: content}, combined_hash)."""
    transcripts_dir = customer_dir / "transcripts"
    transcripts: dict[str, str] = {}
    for f in sorted(transcripts_dir.glob("*.md")):
        transcripts[f.name] = f.read_text(encoding="utf-8")
    combined = "\n\n".join(transcripts.values())
    return transcripts, hash_content(combined)


def format_transcripts(transcripts: dict[str, str]) -> str:
    parts = []
    for filename, content in transcripts.items():
        parts.append(f"=== TRANSCRIPT: {filename} ===\n{content}")
    return "\n\n".join(parts)


def analyze_transcripts(transcripts: dict[str, str]) -> dict:
    """Send all transcripts to Claude and return structured analysis dict."""
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    formatted = format_transcripts(transcripts)
    prompt = ANALYSIS_PROMPT.format(transcripts=formatted)

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if Claude wrapped the JSON
    if raw.startswith("```"):
        lines = raw.splitlines()
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines) - 1 if lines[-1] == "```" else len(lines)
        raw = "\n".join(lines[start:end])

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: Claude returned malformed JSON during analysis: {e}")
        print("Raw response:", raw[:500])
        sys.exit(1)
