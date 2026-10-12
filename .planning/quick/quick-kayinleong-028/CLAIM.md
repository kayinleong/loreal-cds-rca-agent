# Claim: quick-kayinleong-028
- owner: kayinleong
- session: claude-code
- branch: feature/quick-kayinleong-028-easy-install (stacked on feature/phase-kayinleong-03-rca-copilot-xplat / PR #3)
- started: 2026-10-12
- status: in-progress
- summary: Simplify installing rca_copilot_agent for colleagues (one-command setup on macOS + Windows, no missing libraries) and clean unnecessary packages out of requirements.txt without breaking the other agents.

## What will change

Research first (dependency audit per agent package + install-approach research), then:
- Minimal, complete dependency set for `rca_copilot_agent` (per-agent requirements file).
- Root `requirements.txt` cleaned to direct dependencies actually used (nothing other agents need is dropped).
- One-command setup for macOS and Windows + a dependency self-check so nothing is silently missing.
- Docs updated (Copilot agent, Claude skill, AGENTS.md).

## What has changed

_(pending)_

## Verification

_(pending)_
