# MSP Tool — Mutual Success Plan Generator

Transform customer conversation transcripts into structured, actionable Mutual Success Plans using Claude AI.

## What It Does

The MSP Tool reads your customer meeting notes (`.md` format) and uses Claude to automatically:

1. **Analyze transcripts** — Extract pain points, goals, success criteria, stakeholders, risks, and timeline
2. **Generate a structured MSP** — Create a professional, Markdown-based Mutual Success Plan tailored to your deal
3. **Track checkbox completion** — Edit the MSP with task checkboxes (GitHub-flavored Markdown) to track progress
4. **Export for sharing** — Generate print-ready HTML or plain Markdown for customers or Salesforce

The tool is designed for **sales reps and solutions engineers** who need to convert discovery/demo conversations into trial test plans that can be shared with customers and updated collaboratively.

## Installation

### Requirements
- Python 3.9+
- Anthropic API key

### Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/tonesjones/poc-tool.git
   cd poc-tool
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your API key:**
   ```bash
   cp .env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   ```

## Quick Start

### 1. Create a Customer Partition

```bash
python main.py new "Acme Corp"
```

This creates a folder structure:
```
customers/acme-corp/
├── transcripts/        # Drop your .md files here
├── msp.md              # Generated MSP (editable)
└── metadata.json       # Caches, hashes, run history
```

### 2. Add Your Transcripts

Copy your meeting notes into `customers/acme-corp/transcripts/` as `.md` files:
- `discovery-call.md`
- `demo-followup.md`
- `security-review.md`

The tool will synthesize ALL transcripts into a single coherent MSP.

### 3. Generate the MSP

```bash
python main.py generate acme-corp --template saas_trial
```

The tool:
- **Analyzes** all transcripts with Claude (cached if unchanged)
- **Generates** the MSP markdown from a template
- **Preserves manual edits** — if you've edited the MSP before, the tool merges your changes with regenerated sections

Options:
- `--template saas_trial` — for 2–4 week SaaS product trials (default: `default`)
- `--template enterprise` — for multi-stakeholder, 4–12 week evaluations with procurement/legal gates
- `--force` — overwrite all sections (ignores your manual edits)

### 4. Export for Sharing

```bash
python main.py export acme-corp
```

Produces:
- `acme-corp_msp.html` — Open in browser, print to PDF for Salesforce or customer sharing
- `.md` export also available with `--format md`

### 5. Review & Trim the MSP

```bash
python main.py review acme-corp
```

Walk through the MSP section by section. For each `##` section:
- See a 5-line preview
- Choose: `y` (keep), `n` (delete), or `skip` (decide later)
- Changes are saved immediately

This is the best way to remove redundant sections without losing important information. The tool generates comprehensively; you trim to fit your deal.

### 6. List All Customers

```bash
python main.py list
```

Shows status of all customer partitions, transcript counts, and last generation date.

## Features

### Multi-Transcript Synthesis

Drop multiple `.md` files into a customer's `transcripts/` folder. The tool concatenates them with clear delimiters so Claude can understand the conversation flow and prioritize the most recent information.

### Three MSP Templates

- **`default.md`** — Generic template for any evaluation
- **`saas_trial.md`** — Optimized for SaaS product trials (features, integrations, UAT, pricing discussion)
- **`enterprise.md`** — Optimized for enterprise evaluations (architecture, security, compliance, procurement, stakeholder sign-off)

### Confidence Flagging

Claude marks uncertain items with `[NEEDS CONFIRMATION]` so you know what to verify with the customer before sharing:

```markdown
- Deploy on-premise instance by August 15 [NEEDS CONFIRMATION]
```

### Diff-Aware Regeneration

Edit the generated MSP manually (e.g., update dates, add notes, check off tasks). When you re-run `generate`:
- Unchanged sections are regenerated fresh
- Manually edited sections are **preserved** with a notice
- Use `--force` to overwrite everything

### Salesforce-Ready Summary

Every MSP ends with a **plain-text Salesforce Summary** — three paragraphs with no Markdown formatting — so you can copy-paste directly into Salesforce Notes/Description fields.

### Section Hashing

The tool stores SHA256 hashes of each section in `metadata.json` to detect which parts you've edited. This enables the diff-aware merge logic.

## File Structure

```
poc-tool/
├── main.py                    # Click CLI: new, generate, export, list
├── analyzer.py                # Claude analysis: transcripts → JSON
├── generator.py               # Claude generation: JSON + template → Markdown
├── config.py                  # Configuration and paths
├── requirements.txt           # Python dependencies
├── .env.example               # Template for API key (copy to .env)
├── .gitignore                 # Excludes .env, customer data
├── templates/
│   ├── default.md             # Generic template
│   ├── saas_trial.md          # SaaS trial template
│   └── enterprise.md          # Enterprise evaluation template
└── customers/
    └── {customer-slug}/       # One per customer
        ├── transcripts/       # .md files you provide
        ├── msp.md             # Generated output (editable)
        └── metadata.json      # Analysis cache, hashes, history
```

## How It Works

### 1. Analysis Phase

When you run `generate`, the tool:
1. Reads all `.md` files from `transcripts/`
2. Sends them to Claude along with an analysis prompt
3. Claude returns structured JSON with:
   - Pain points, business goals, success criteria (each tagged with confidence level)
   - Stakeholders, timeline, risks, trial scope
   - Context notes about the conversation

This result is **cached** in `metadata.json` keyed by a hash of the transcript content. If you re-run without changing transcripts, analysis is skipped.

### 2. Generation Phase

The tool:
1. Takes the cached (or freshly generated) analysis JSON
2. Loads your chosen template (`default`, `saas_trial`, or `enterprise`)
3. Sends both to Claude with a prompt to fill in the template
4. Claude returns a complete, ready-to-share MSP in Markdown

### 3. Merge Phase (if editing)

If an `msp.md` already exists:
1. Tool compares each section's current hash against the stored hash in `metadata.json`
2. If hashes match → section is unchanged, regenerate it
3. If hashes differ → you edited it, preserve it and add a notice
4. Use `--force` to skip this logic and overwrite everything

## Command Reference

```bash
# Create a new customer partition
python main.py new "<Customer Name>"

# Generate or regenerate MSP
python main.py generate <customer-slug> [--template <template-name>] [--force]

# Interactively review and trim sections
python main.py review <customer-slug>

# Export to HTML or Markdown
python main.py export <customer-slug> [--format html|md]

# List all customers and their status
python main.py list
```

## Known Limitations & Notes

- **API Key Required** — You must provide an Anthropic API key in `.env`
- **Sonnet 4.6 Only** — Uses Claude Sonnet 4.6 for quality; not configurable per-customer (but can be edited in `config.py`)
- **Windows Console Encoding** — Some special characters don't render in the Windows terminal; the functionality is unaffected
- **No Web UI** — This is a CLI tool; no browser interface
- **Manual Checkbox Updates** — Task completion checkboxes must be edited manually in the `.md` file; no API to update them programmatically
- **No Salesforce Integration** — Export the Markdown or PDF and manually paste/upload to Salesforce (can be scripted separately)
- **Over-generation** — Templates generate comprehensively (242 lines); use `review` command to trim to fit your actual needs

## Example Workflow

```bash
# Create partition for a prospect
python main.py new "Acme Corp"

# Add meeting notes
cp ~/Downloads/2026-07-01-discovery.md customers/acme-corp/transcripts/
cp ~/Downloads/2026-07-08-demo.md customers/acme-corp/transcripts/

# Generate MSP (comprehensive by default)
python main.py generate acme-corp --template saas_trial

# Interactively trim to fit your deal
python main.py review acme-corp
# Walks through each section, you decide what to keep

# Export to HTML
python main.py export acme-corp

# Print HTML to PDF and share with customer
open customers/acme-corp/acme-corp_msp.html

# Customer reviews and you update manually as needed
# (e.g., confirm dates, add notes, check off completed tasks)

# Regenerate to refresh analysis without losing your edits
python main.py generate acme-corp --template saas_trial

# Copy Salesforce Summary into Salesforce Notes field
```

## Troubleshooting

**"ANTHROPIC_API_KEY is not set"**
- Copy `.env.example` to `.env` and add your key

**"Template 'xyz' not found"**
- Available templates: `default`, `saas_trial`, `enterprise`
- Add new templates as `.md` files in the `templates/` folder

**"Customer 'xyz' not found"**
- Run `python main.py list` to see available customers
- Use the exact slug (e.g., `acme-corp` not `Acme Corp`)

**"No .md files found in transcripts/"**
- Add `.md` files to `customers/{slug}/transcripts/` before running `generate`

## Typical Usage Pattern

Based on early testing, the recommended workflow is:

1. **Generate comprehensive** — Let Claude extract everything
2. **Review & trim** — Use `review` to keep only what matters for this deal
3. **Export & share** — Send HTML to customer or Salesforce
4. **Edit manually** — Update dates, add notes, check off tasks as work progresses
5. **Regenerate carefully** — Re-run `generate` to refresh analysis, the tool will preserve your manual edits

The tool generates thoroughly so nothing is missed, but you trim it to fit the actual scope of each deal.

---

## Contributing & Feedback

This tool is actively being improved. See `FEEDBACK.md` for current findings and direction.

### Reporting Issues

Create an issue on GitHub describing:
1. What command you ran
2. What you expected to happen
3. What actually happened
4. Any error messages

---

**Built with:** Python, Click, Rich, Anthropic API, Markdown2  
**Status:** Early Alpha 
