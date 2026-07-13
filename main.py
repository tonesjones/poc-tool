from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from analyzer import analyze_transcripts, load_transcripts
from config import CUSTOMERS_DIR, DEFAULT_TEMPLATE, MODEL, TEMPLATES_DIR
from generator import compute_section_hashes, export_html, generate_msp

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug


def load_metadata(customer_dir: Path) -> dict:
    meta_file = customer_dir / "metadata.json"
    if meta_file.exists():
        return json.loads(meta_file.read_text(encoding="utf-8"))
    return {}


def save_metadata(customer_dir: Path, metadata: dict) -> None:
    meta_file = customer_dir / "metadata.json"
    meta_file.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")


def get_template_content(template_name: str) -> str:
    template_file = TEMPLATES_DIR / f"{template_name}.md"
    if not template_file.exists():
        console.print(f"[red]Template '{template_name}' not found. Available templates:[/red]")
        for t in sorted(TEMPLATES_DIR.glob("*.md")):
            console.print(f"  • {t.stem}")
        sys.exit(1)
    return template_file.read_text(encoding="utf-8")


def resolve_customer(slug: str) -> Path:
    customer_dir = CUSTOMERS_DIR / slug
    if not customer_dir.exists():
        console.print(
            f"[red]Customer '{slug}' not found.[/red]\n"
            f"Run: [bold]python main.py new \"<Customer Name>\"[/bold]"
        )
        sys.exit(1)
    return customer_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """MSP Tool — generate Mutual Success Plans from customer conversation transcripts."""
    CUSTOMERS_DIR.mkdir(exist_ok=True)


@cli.command()
@click.argument("name")
def new(name: str):
    """Create a new customer partition.

    NAME is the human-readable customer name, e.g. "Acme Corp".
    A URL-safe slug is derived automatically.
    """
    slug = slugify(name)
    customer_dir = CUSTOMERS_DIR / slug

    if customer_dir.exists():
        console.print(f"[yellow]Customer partition '{slug}' already exists.[/yellow]")
        sys.exit(1)

    (customer_dir / "transcripts").mkdir(parents=True)

    metadata: dict = {
        "customer_name": name,
        "customer_slug": slug,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "template": DEFAULT_TEMPLATE,
        "transcript_files": [],
        "section_hashes": {},
        "analysis_cache": {},
        "last_generated": None,
    }
    save_metadata(customer_dir, metadata)

    console.print(f"[green]✓[/green] Created partition: [bold]{customer_dir}[/bold]")
    console.print(f"\n  1. Drop transcript .md files into:")
    console.print(f"     [bold]{customer_dir / 'transcripts'}[/bold]")
    console.print(f"\n  2. Generate the MSP:")
    console.print(f"     [bold]python main.py generate {slug}[/bold]")


@cli.command()
@click.argument("slug")
@click.option("--template", "template_name", default=None,
              help="Template to use (overrides stored preference).")
@click.option("--force", is_flag=True, default=False,
              help="Overwrite all sections, including any you have manually edited.")
def generate(slug: str, template_name: str | None, force: bool):
    """Analyze transcripts and generate (or regenerate) the MSP.

    SLUG is the customer directory name, e.g. acme-corp.
    """
    customer_dir = resolve_customer(slug)
    metadata = load_metadata(customer_dir)
    template = template_name or metadata.get("template", DEFAULT_TEMPLATE)
    template_content = get_template_content(template)

    console.print(
        f"[bold]Customer:[/bold] {metadata.get('customer_name', slug)}  "
        f"[dim]template={template}  model={MODEL}[/dim]"
    )

    # Load transcripts
    transcripts, transcript_hash = load_transcripts(customer_dir)
    if not transcripts:
        console.print(
            f"[red]No .md files found in {customer_dir / 'transcripts'}[/red]\n"
            f"Add transcript files and retry."
        )
        sys.exit(1)

    console.print(f"  Transcripts: {', '.join(transcripts.keys())}")

    # Cache check — skip Claude analysis if transcripts haven't changed
    cache = metadata.get("analysis_cache", {})
    if not force and cache.get("transcript_hash") == transcript_hash and cache.get("analysis"):
        console.print("[dim]  Analysis cache hit — transcripts unchanged, skipping re-analysis.[/dim]")
        analysis = cache["analysis"]
    else:
        console.print("  [bold]Step 1/2[/bold] Analyzing transcripts with Claude...")
        analysis = analyze_transcripts(transcripts)
        metadata["analysis_cache"] = {
            "transcript_hash": transcript_hash,
            "analysis": analysis,
        }

    # Load existing MSP for diff-aware merge
    msp_file = customer_dir / "msp.md"
    existing_msp = msp_file.read_text(encoding="utf-8") if msp_file.exists() else None
    stored_hashes = metadata.get("section_hashes", {})

    console.print("  [bold]Step 2/2[/bold] Generating MSP document with Claude...")
    msp_content, preserved, new_hashes = generate_msp(
        analysis, template_content, existing_msp, stored_hashes, force
    )

    msp_file.write_text(msp_content, encoding="utf-8")

    metadata["section_hashes"] = new_hashes
    metadata["last_generated"] = datetime.now(timezone.utc).isoformat()
    metadata["template"] = template
    metadata["transcript_files"] = list(transcripts.keys())
    save_metadata(customer_dir, metadata)

    console.print(f"\n[green]✓ MSP written →[/green] {msp_file}")

    if preserved:
        console.print(
            f"\n[yellow]⚠  {len(preserved)} section(s) had manual edits and were preserved:[/yellow]"
        )
        for s in preserved:
            console.print(f"   • {s}")
        console.print("   Use [bold]--force[/bold] to overwrite them with regenerated content.")

    console.print(
        f"\n  Next: [bold]python main.py export {slug}[/bold]  — to produce a shareable HTML file"
    )


@cli.command()
@click.argument("slug")
@click.option("--format", "fmt", default="html",
              type=click.Choice(["html", "md"], case_sensitive=False),
              help="Export format (default: html).")
def export(slug: str, fmt: str):
    """Export the MSP to a shareable file.

    HTML output can be opened in a browser and printed to PDF via File → Print.
    """
    customer_dir = resolve_customer(slug)
    msp_file = customer_dir / "msp.md"

    if not msp_file.exists():
        console.print(
            f"[red]No MSP found for '{slug}'.[/red] "
            f"Run: [bold]python main.py generate {slug}[/bold]"
        )
        sys.exit(1)

    metadata = load_metadata(customer_dir)
    safe_name = metadata.get("customer_slug", slug)

    if fmt == "html":
        output_path = customer_dir / f"{safe_name}_msp.html"
        export_html(msp_file, output_path)
        console.print(f"[green]✓ HTML exported →[/green] {output_path}")
        console.print(
            "  Open in your browser → File → Print → Save as PDF  (best for Salesforce upload)"
        )
    else:
        output_path = customer_dir / f"{safe_name}_msp_export.md"
        shutil.copy(msp_file, output_path)
        console.print(f"[green]✓ Markdown exported →[/green] {output_path}")


@cli.command("list")
def list_customers():
    """List all customer partitions."""
    customers = [d for d in sorted(CUSTOMERS_DIR.iterdir()) if d.is_dir()]
    if not customers:
        console.print("[dim]No customers yet. Run: python main.py new \"<Customer Name>\"[/dim]")
        return

    table = Table(title="Customers", show_header=True, header_style="bold cyan")
    table.add_column("Slug", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Transcripts", justify="center")
    table.add_column("MSP", justify="center")
    table.add_column("Template")
    table.add_column("Last Generated")

    for d in customers:
        meta = load_metadata(d)
        name = meta.get("customer_name", d.name)
        tr_dir = d / "transcripts"
        transcript_count = len(list(tr_dir.glob("*.md"))) if tr_dir.exists() else 0
        has_msp = "[green]✓[/green]" if (d / "msp.md").exists() else "[dim]—[/dim]"
        tmpl = meta.get("template", "—")
        last_gen = meta.get("last_generated") or "Never"
        if last_gen != "Never":
            last_gen = last_gen[:10]
        table.add_row(d.name, name, str(transcript_count), has_msp, tmpl, last_gen)

    console.print(table)


if __name__ == "__main__":
    cli()
