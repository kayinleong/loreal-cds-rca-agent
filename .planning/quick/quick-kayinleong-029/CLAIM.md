# Claim: quick-kayinleong-029
- owner: kayinleong
- session: claude-code
- branch: chore/quick-kayinleong-029-release-ignore
- started: 2026-10-14
- status: done
- summary: Keep release zips local — gitignore release/ and document the reproducible release-zip build command.

## What will change
- `.gitignore`: ignore `release/` (built zips are shared manually, never committed — user decision 2026-10-14).
- `README.md` "For developers": the exact `git archive` command used to build `release/loreal-cds-rca-agent-<version>.zip` + `.sha256`.

## What has changed
- `.gitignore`: `release/` added (end of file, commented).
- `README.md`: new "Building a release zip" subsection under "For developers" with the exact recipe.
- Built (local, not committed): `release/loreal-cds-rca-agent-2026.10.14.zip` (+ `.sha256`) from `main` @ `2707f61`,
  67 files, 811 KB, SHA-256 `fcc2ecb597d61215842eeebe395262990d9c007f386cb276646efc846f8c786b`.

## Verification
- `git check-ignore release/` → ignored; `git status` clean apart from the two edited files.
- The documented recipe rebuilt a byte-identical zip (same SHA-256 as the released one).
- Zip content: no `.planning/`, `.serena/`, `tests/`, `.env`, `.venv/`, reports, attachments, `.rca_tmp/`, credentials,
  `__pycache__`; `setup.cmd` CRLF, `setup.sh` mode 755.
- Release smoke test (macOS, fresh unzip, real PyPI): `./setup.sh` → all 3 agents OK (~1.5 min), doctor 0 failures
  (2 expected warnings: non-@loreal.com gcloud account, no `.env`); all three `run_tool.py --help` from system
  Python 3.9 re-exec into `.venv`; all agent libraries import.

### Regression report
Docs/config only: `.gitignore` gains one ignore rule for a new directory (no existing path matched `release/`
before — `git ls-files release` empty); README gains a subsection. No code paths touched. Not verified: Windows
run of the zip (no Windows host).
