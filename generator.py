from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, MODEL

GENERATION_PROMPT = """\
You are writing a Mutual Success Plan (MSP) for a software trial. Generate a complete, \
professional document in GitHub-Flavored Markdown.

Rules:
1. Follow the template structure exactly — preserve every ## section header from the template
2. Use `- [ ]` for ALL actionable tasks; never use numbered lists for task items
3. Append [NEEDS CONFIRMATION] to any line item whose underlying data had confidence "uncertain"
4. Make every success criterion specific and measurable
5. The "## Salesforce Summary" section MUST contain plain text only — no markdown, no bullets, \
no sub-headers, just 2–3 plain paragraphs suitable for pasting into a Salesforce Notes field
6. Be specific and actionable throughout; avoid vague filler language
7. Do not include the HTML comment instructions from the template in your output

Customer Analysis (JSON):
{analysis}

Template to follow:
{template}

Generate the complete MSP document now:
"""


def hash_section(content: str) -> str:
    return hashlib.sha256(content.strip().encode()).hexdigest()[:16]


def parse_sections(content: str) -> dict[str, str]:
    """Parse markdown into {header_line: body_text} preserving order."""
    result: dict[str, str] = {}
    # Split on ## level headers only (##+ followed by a space)
    parts = re.split(r"^(#{2,} [^\n]+)", content, flags=re.MULTILINE)

    if parts[0].strip():
        result["__preamble__"] = parts[0]

    for i in range(1, len(parts) - 1, 2):
        header = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        result[header] = body

    return result


def assemble_sections(sections: dict[str, str]) -> str:
    parts = []
    for header, body in sections.items():
        if header == "__preamble__":
            parts.append(body)
        else:
            parts.append(f"{header}{body}")
    return "".join(parts)


def compute_section_hashes(content: str) -> dict[str, str]:
    sections = parse_sections(content)
    return {
        header: hash_section(body)
        for header, body in sections.items()
        if header != "__preamble__"
    }


def merge_with_existing(
    new_content: str,
    existing_content: str,
    stored_hashes: dict[str, str],
) -> tuple[str, list[str]]:
    """
    Merge new generation into existing MSP, preserving manually-edited sections.
    Returns (merged_content, list_of_preserved_section_names).

    A section is considered manually edited if its current hash differs from the
    stored hash that was recorded when Claude last wrote it.
    """
    new_sections = parse_sections(new_content)
    existing_sections = parse_sections(existing_content)
    preserved: list[str] = []
    merged: dict[str, str] = {}

    for header, new_body in new_sections.items():
        if header == "__preamble__":
            merged[header] = new_body
            continue

        existing_body = existing_sections.get(header)
        if existing_body is None:
            # New section from regeneration — append it
            merged[header] = new_body
            continue

        stored_hash = stored_hashes.get(header)
        current_hash = hash_section(existing_body)

        if stored_hash and current_hash != stored_hash:
            # User edited this section — preserve it, add a soft notice
            label = header.lstrip("#").strip()
            preserved.append(label)
            notice = (
                "\n\n> **Regeneration notice:** This section has local edits and was not "
                "overwritten. Run with `--force` to replace with the regenerated version.\n"
            )
            merged[header] = existing_body.rstrip() + notice
        else:
            merged[header] = new_body

    # Keep any user-added sections not present in the new generation
    for header, body in existing_sections.items():
        if header not in new_sections and header != "__preamble__":
            preserved.append(header.lstrip("#").strip())
            merged[header] = body

    return assemble_sections(merged), preserved


def generate_msp(
    analysis: dict,
    template_content: str,
    existing_msp: str | None,
    stored_hashes: dict[str, str],
    force: bool,
) -> tuple[str, list[str], dict[str, str]]:
    """
    Call Claude to generate the MSP. Merges with existing manual edits unless force=True.
    Returns (final_content, preserved_section_names, new_section_hashes).
    """
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        sys.exit(1)

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = GENERATION_PROMPT.format(
        analysis=json.dumps(analysis, indent=2),
        template=template_content,
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    new_content = response.content[0].text.strip()

    # Strip code fences if Claude wrapped the Markdown
    if new_content.startswith("```"):
        lines = new_content.splitlines()
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        new_content = "\n".join(lines[start:end])

    preserved: list[str] = []
    if existing_msp and not force:
        final_content, preserved = merge_with_existing(new_content, existing_msp, stored_hashes)
    else:
        final_content = new_content

    new_hashes = compute_section_hashes(final_content)
    return final_content, preserved, new_hashes


def export_html(msp_path: Path, output_path: Path) -> None:
    """Render msp.md to a self-contained, print-ready HTML file."""
    import markdown2  # type: ignore

    content = msp_path.read_text(encoding="utf-8")
    body_html = markdown2.markdown(
        content,
        extras=["task_list", "fenced-code-blocks", "tables", "header-ids", "strike"],
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mutual Success Plan</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 15px; line-height: 1.65; color: #1a1a1a; background: #fff;
      max-width: 860px; margin: 0 auto; padding: 48px 28px 96px;
    }}
    h1 {{ font-size: 2em; margin: 0 0 6px; color: #0f172a; }}
    h2 {{
      font-size: 1.35em; margin: 44px 0 14px; padding-bottom: 8px;
      border-bottom: 2px solid #e2e8f0; color: #1e293b;
    }}
    h3 {{ font-size: 1.05em; margin: 22px 0 8px; color: #334155; }}
    p {{ margin: 0 0 12px; }}
    ul, ol {{ margin: 0 0 12px 22px; }}
    li {{ margin-bottom: 5px; }}
    /* Task list checkboxes */
    ul.task-list {{ list-style: none; margin-left: 0; }}
    ul.task-list li {{ padding-left: 4px; }}
    ul.task-list li input[type=checkbox] {{ margin-right: 7px; accent-color: #2563eb; }}
    blockquote {{
      border-left: 3px solid #94a3b8; padding: 8px 14px;
      color: #64748b; margin: 16px 0; background: #f8fafc;
      border-radius: 0 6px 6px 0; font-size: 0.93em;
    }}
    code {{
      background: #f1f5f9; padding: 2px 6px; border-radius: 4px;
      font-size: 0.88em; font-family: "SF Mono", Consolas, monospace;
    }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 0.93em; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 8px 14px; text-align: left; }}
    th {{ background: #f8fafc; font-weight: 600; color: #374151; }}
    tr:nth-child(even) td {{ background: #fafafa; }}
    hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 32px 0; }}
    strong {{ color: #0f172a; }}
    @media print {{
      body {{ max-width: 100%; padding: 16px 20px; }}
      h2 {{ page-break-before: auto; }}
      blockquote {{ border-left: 2px solid #94a3b8; }}
    }}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
