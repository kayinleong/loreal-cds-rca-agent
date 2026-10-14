# space-cds-etl-core — SPACE CDS Copilot agents

Three AI agents for L'Oréal SPACE CDS, usable from GitHub Copilot Chat (VS Code) or Claude Code. The tools are plain Python; the LLM stays in your client.

| Agent (Copilot name) | What it does |
|----------------------|--------------|
| **RCA Copilot Agent** | Root-cause analysis of ServiceNow incidents, validated with BigQuery; saves an RCA report and can email it |
| **Ticket Assignment Copilot Agent** | Recommends the assignment group for a ticket |
| **Mock Data Copilot Agent** | Generates mock INSERT SQL for DV testing |

## Prerequisites

- git
- Python 3.10+ (64-bit; 3.12 recommended)
- Google Cloud SDK (`gcloud`, `bq`)
- Microsoft Edge (used to capture your ServiceNow session)
- VS Code with GitHub Copilot (or Claude Code)

## Quick start

```bash
git clone <repo-url>
cd space-cds-etl-core
./setup.sh          # macOS/Linux
# setup.cmd         # Windows
gcloud auth login   # sign in with your @loreal.com account
```

Then open the folder in VS Code, open Copilot Chat and pick an agent (**RCA Copilot Agent**, **Ticket Assignment Copilot Agent** or **Mock Data Copilot Agent**). In Claude Code use `/rca-copilot`, `/ticketasg-copilot` or `/mockdata-copilot`.

Setup creates `.venv/` and installs everything; you never need to activate it. Optionally copy `.env.example` to `.env` to configure SMTP email.

## Troubleshooting

- Check your environment (offline, prints fixes): `python3 scripts/doctor.py` (or the VS Code task "RCA: Doctor").
- Behind a proxy: `./setup.sh --proxy http://user@host:8080`
- Internal package mirror: `--index-url <url>`; no internet: `--wheelhouse <dir>` with pre-downloaded wheels.
- Skip the large kNN retrieval dependencies (torch) for ticketasg: `--skip-retrieval`.
- SSL errors behind corporate inspection: set `REQUESTS_CA_BUNDLE` to your company CA bundle.
- Broken environment: `./setup.sh --recreate`.
- All options: `python3 scripts/bootstrap.py --help`.

## Where output goes

Reports and downloads stay local and are gitignored (they may contain personal data): RCA reports and incident files under `rca_copilot_agent/my_reports/` and `attachments/`, mock data under `mockdata_copilot_agent/mockdata/`. Never commit them.

## For developers

See `CLAUDE.md` and each package's `AGENTS.md`. Tests: `python3 -m unittest discover -s scripts/tests`.

### Building a release zip

Release zips are built from `main` into `release/` (gitignored — share the zip directly, don't commit it). Only
committed files are included (never `.env`, `.venv`, reports or attachments); `.planning/`, `.serena/` and test
folders are left out:

```bash
V=$(date +%Y.%m.%d); N="loreal-cds-rca-agent-$V"; mkdir -p release
git archive --format=zip --prefix="$N/" -o "release/$N.zip" main -- . ':(exclude).planning' ':(exclude).serena' ':(exclude,glob)**/tests/**'
(cd release && shasum -a 256 "$N.zip" > "$N.zip.sha256")
```

Check it by unzipping into an empty folder and running `./setup.sh` / `setup.cmd` there.
