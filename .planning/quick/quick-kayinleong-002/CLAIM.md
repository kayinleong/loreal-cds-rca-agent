# Claim: quick-kayinleong-002
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: done
- summary: Create project-level CLAUDE.md for space-cds-etl-core RCA agent, extending global rules with project-specific context

## What will change
- Create `./CLAUDE.md` in repo root
- Project-specific sections: stack, architecture, secrets, BQ safety, patterns, run instructions

## What has changed
- Created `./CLAUDE.md` in repo root with project-specific context

## Verification
- No code changed — doc-only addition, regression surface is zero
- Verified against project structure: all file paths, env vars, and tool names match actual repo layout
- Secrets rules reinforce existing .gitignore (my_reports/, attachments/ already gitignored)
- BQ safety rules match existing bigquery_tool.py implementation
- "What Not To Do" section derived from actual architectural decisions in mcp_server.py and agent_runner.py
