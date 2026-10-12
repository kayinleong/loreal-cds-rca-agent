---
status: complete
claim: quick-kayinleong-028
topic: install approach for rca_copilot_agent (macOS + Windows, locked-down laptops)
researched: 2026-10-12
---

# Install research: `git clone` to a working RCA agent

**Tags:** `[V:n]` means verified against source *n* (listed at the end). `[V:repo …]` means verified in this repo or on this machine this session. `[U]` means unverified (training knowledge or inference), so confirm it before you lock it in.
**Working dependency set (owned by the sibling audit):** `requests`, `python-dotenv`, and `playwright` (optional). The minimal pip closure adds `urllib3`, `certifi`, `idna`, `charset-normalizer`, `pyee`, `greenlet` and `typing-extensions` [V:1]. **`greenlet` is the only compiled wheel in that closure.** Every other package is `py3-none` [V:1].

## 1. Options comparison

| Option | Works without admin | Proxy / SSL inspection | PyPI blocked? | Maintenance | Verdict |
|---|---|---|---|---|---|
| **1. venv + pip + bootstrap** (`setup.sh` / `setup.cmd`) | Yes. A venv sits in the repo, and Python can be a per-user install [V:4] | Good. pip ≥ 24.2 on Py ≥ 3.10 uses the OS trust store [V:2]. `PIP_CERT` covers older pip [V:3] | `--index-url` / `PIP_INDEX_URL` points at an internal mirror [V:5]. `--wheelhouse` works offline | Low. One stdlib script plus a short requirements file | **Recommended (primary)** |
| **2. uv** | Yes. The standalone installer goes to `~/.local/bin` [V:7]. Managed Python installs per-user [U] | Weak by default. It uses bundled Mozilla roots and needs `UV_SYSTEM_CERTS=true` or `--system-certs` (`--native-tls` / `UV_NATIVE_TLS` are deprecated) [V:6][V:8] | `UV_DEFAULT_INDEX` [V:8]. Python downloads come from python-build-standalone on GitHub, which is often blocked, so set `UV_PYTHON_INSTALL_MIRROR` [V:8] | A second tool to learn and support. The installer is a `irm … \| iex` script [V:7] that AV/proxy may block [U] | **Optional fallback**: only to get a Python on a Mac with no admin rights and no usable Python |
| **3. Offline wheelhouse** | Yes | Not needed after the download | Solves it | Rebuild for every dependency bump × OS × Python minor (for greenlet). playwright alone is 38.6 MB (win_amd64) and 44.3 MB (macOS universal2) [V:1]. GitHub warns above 50 MiB and blocks above 100 MiB per file [V:9], so **do not commit it**. Use a release asset or a share drive | **Escape hatch only** (`--wheelhouse DIR`) |
| **4. PyInstaller / single exe** | Yes | Not needed at runtime | Solves it | High. One build per OS/arch. Unsigned exes trigger SmartScreen and AV heuristics, and EV signing costs about $300–500/yr [V:10] (community sources). playwright's bundled Node driver complicates freezing [U] | **Reject** |
| **5. VS Code task** | Same as option 1 (it wraps option 1) | Same as option 1 | Same as option 1 | Trivial | **Add as a convenience** (§2.6) |

## 2. Recommendation: one stdlib bootstrap, two thin launchers

### 2.1 Files
- `scripts/bootstrap.py`: **all the logic, stdlib only.** It makes or reuses the venv, upgrades pip, installs, runs the doctor and writes the stamp. Python is the same on both OSes, so pytest can test it and it doesn't depend on PowerShell. If it lives elsewhere, `scripts/` is fine.
- `setup.sh` (macOS) and `setup.cmd` (Windows): each **only finds a suitable Python**, then runs `"$PY" scripts/bootstrap.py "$@"`.
- Use `setup.cmd` rather than `setup.ps1` as the Windows entry point. cmd batch files are **not subject to the PowerShell execution policy** [U, standard Windows behaviour]. A GPO "Turn on Script Execution" policy overrides every scope, including `-ExecutionPolicy Bypass` on the command line [V:11]. So `powershell -NoProfile -ExecutionPolicy Bypass -File setup.ps1` works under the default RemoteSigned/Restricted policy, but **fails under a GPO AllSigned or Restricted policy** [V:11]. If you also ship a `setup.ps1`, keep it as a thin optional wrapper.

### 2.2 Python discovery (accept ≥ 3.11, 64-bit; prefer 3.13 → 3.12 → 3.14 → 3.11 → 3.15)
- **Floor 3.11.** Project CLAUDE.md says "Python 3.11+" [V:repo CLAUDE.md]. The pinned `requests 2.33.1` and `python-dotenv 1.2.2` require ≥ 3.10 [V:1]. 3.10 has been EOL since 2026-10-01 [V:12].
- **Accept 3.15 last.** It was released 2026-10-09, three days before this research [V:13]. The repo's exact pin `greenlet==3.5.0` has **no cp315 wheel** (cp310–cp314 only), while greenlet 3.5.6 does [V:1].
- **Validate every candidate by probing it, not by its path.** Run `<cand> -c "import sys,struct,venv,ensurepip; print(sys.version_info[0], sys.version_info[1], struct.calcsize('P')*8)"` and accept it only if the exit code is 0 and the output parses. This rejects the **Microsoft Store App Execution Alias stub**, which opens the Store when called with no arguments and errors when given arguments [V:14]. Path checks alone are not enough, because a *real* Store Python also lives under `%LOCALAPPDATA%\Microsoft\WindowsApps\…` [V:14]. Require **64-bit**: greenlet 3.5.x ships no `win32` wheels [V:1].
- **Windows order:** `--python PATH` → `py -V:3.13`, `py -3.13`, … (the install-manager and legacy launcher syntax respectively [V:4]) → `python` on PATH (after probing) → `%LOCALAPPDATA%\Programs\Python\Python31x\python.exe` (python.org per-user default) [U].
- **macOS order:** `--python` → `python3.13`, `python3.12`, … on PATH and in `/opt/homebrew/bin`, `/usr/local/bin`, `/Library/Frameworks/Python.framework/Versions/3.x/bin` [U paths] → `python3`. **Reject `/usr/bin/python3`**: on this Mac it is the Xcode CLT Python 3.9.6 with pip 21.2.4 [V:repo local probe]. That Python is EOL [V:12] and its pip has no truststore support [V:2].
- **If nothing is found**, print the fix for each OS and exit 2. Windows: python.org "Install Now" needs no admin [V:4], or the Python Install Manager, which installs runtimes per-user only [V:4]. Its winget ID is `9NQ7512CXL7T` [V:4]. The Store or winget may be blocked by policy [U]. macOS: company Self Service, or `--use-uv`, which runs `uv python install 3.13` into the user dir [U]. The python.org macOS `.pkg` needs admin [U].

### 2.3 `bootstrap.py` steps (idempotent, safe to re-run)
1. **Venv at `.venv/`** in the repo root. It is already gitignored [V:repo .gitignore:132,196] and is the path the docs tell users to activate [V:repo .github/agents/rca_copilot.agent.md:89].
   - Reuse it if `.venv/<bin>/python` probes OK and its version is ≥ 3.11.
   - Rebuild it if it is broken: the Python behind it was removed, or the repo was moved [U]. Rename it to `.venv.broken-<ts>` instead of deleting it. `--recreate` forces a rebuild.
2. Run `python -m pip install --upgrade pip` inside the venv. This gets truststore behaviour, i.e. the OS trust store on Py ≥ 3.10 with pip ≥ 24.2 [V:2].
   - If this first call fails with `CERTIFICATE_VERIFY_FAILED`, stop with the hint: export the corporate root CA to PEM, then set `PIP_CERT`, or use `pip config set global.cert …` [V:3][V:5].
3. Run `python -m pip install --only-binary=:all: -r rca_copilot_agent/requirements.txt` plus any passthrough flags. `--only-binary` means pip never tries a C build (greenlet) on machines without compilers. It fails fast instead [V:15].
4. **Skip pip when nothing changed.** Write `.venv/.rca-setup.json` with the sha256 of the requirements file, the Python version and the timestamp. Skip step 3 when the hash matches *and* the doctor passes. `--force` reinstalls.
5. Run the **doctor** (§4). Print the activate commands for zsh, PowerShell and cmd, exactly as in agent.md line 89. Exit codes: 0 = ok, 1 = doctor failed, 2 = no Python, 3 = pip failed.

### 2.4 Flags (passed through by both launchers)
| Flag | Effect |
|---|---|
| `--index-url URL` | Passed to pip. pip also honours `PIP_INDEX_URL` without the flag [V:5] |
| `--wheelhouse DIR` | Adds `--no-index --find-links DIR` for fully offline installs [V:15] |
| `--python PATH` | Skips discovery |
| `--no-playwright` | Skips the optional SSO dependency. The agent falls back to the manual cookie instructions [V:repo AGENTS.md:48] |
| `--use-uv` | Lets uv provide the interpreter and venv (sets `UV_SYSTEM_CERTS=true`) |
| `--recreate`, `--force`, `--doctor-only` | Rebuild the venv / reinstall even if the stamp matches / run only the doctor |

**Building the wheelhouse** (maintainer, per OS and Python): `pip download --only-binary=:all: --platform win_amd64 --python-version 3.13 -d wheelhouse/win-py313 -r rca_copilot_agent/requirements.txt` [V:15]. Use `macosx_11_0_universal2` for Mac [V:1]. Ship it as a release asset [V:9].

### 2.5 Pinning: complete, without blocking new Pythons
- **"Nothing missing" comes from the dependency closure, not from exact pins.** pip resolves transitive dependencies itself. Libraries go missing when the requirements file leaves out *direct* imports, so the sibling audit plus the doctor import check are the real guard [U, reasoning].
- **Use compatible ranges for direct dependencies.** Set each floor to the version tested in the repo: `requests>=2.33,<3`, `python-dotenv>=1.2,<2`, `playwright>=1.59,<2` [V:repo requirements.txt]. All three require Python ≥ 3.10 [V:1]. Don't add an explicit `urllib3` line, even though the code imports `urllib3.util.retry` directly [V:repo snow_reader.py:23]: requests already depends on `urllib3<3,>=1.26` [V:1].
- **Don't exact-pin greenlet.** A `greenlet==3.5.0` pin breaks on Python 3.15 [V:1]. With ranges plus `--only-binary`, pip picks a version that ships a wheel. If you need reproducibility, keep an opt-in `constraints-tested.txt` (`pip freeze`) behind a `--locked` flag [U]. pip-tools or uv lock files carry the same new-Python risk [U].
- **Wheel risk per package.** `requests` and `python-dotenv` are pure `py3-none-any` and carry no risk [V:1]. playwright is `py3-none-<platform>`, which means **one wheel per OS, independent of Python version** (win32/amd64/arm64, macOS x86_64/arm64/universal2) [V:1]. `greenlet` is the only package tied to a CPython minor version [V:1].
- **Registry gate:** `gsd-tools package-legitimacy` returned SUS for requests, python-dotenv, playwright and truststore. All SUS reasons are `unknown-downloads` (PyPI exposes no download counts) or `too-new` (a recent release), and no package was flagged SLOP [V:repo tool run]. All three working deps are already in the repo's requirements. The repo URLs psf/requests and theskumar/python-dotenv check out [V:1].

### 2.6 VS Code and Copilot
- Add `.vscode/tasks.json` with two tasks, **"RCA: Setup"** and **"RCA: Doctor"**. Use the `windows` / `osx` per-OS command properties [V:16] so `setup.cmd` runs on Windows and `./setup.sh` on Mac.
- **Don't** use `runOn: folderOpen` by default. It prompts once per workspace and never runs in an untrusted workspace [V:16].
- **The agent should not run setup itself.** agent.md limits the agent's terminal use to `run_tool.py` [V:repo agent.md:30], and pip changes the machine.
  - Instead, add `run_tool.py doctor`. It must short-circuit **before** the startup sequence: today `main()` always runs `ensure_credentials` (which can open Edge for SSO) and `ensure_gcloud_auth` before dispatch [V:repo run_tool.py:190-202].
  - On `ModuleNotFoundError`, or when the doctor fails, the agent tells the user to run the "RCA: Setup" task, `setup.cmd` or `./setup.sh`.

## 3. Corporate-network gotchas and fixes
1. **SSL inspection breaks pip.** Fix: upgrade pip to ≥ 24.2 on Py ≥ 3.10, which then uses the OS store [V:2]. Py 3.9 only gets certifi [V:2]. Otherwise set `PIP_CERT=<corp-root.pem>` (or `REQUESTS_CA_BUNDLE`) [V:3]. Don't use `--trusted-host`/`PIP_TRUSTED_HOST`: it switches off certificate checks for that host and hides the real problem [U].
2. **SSL inspection breaks the agent at runtime** (ServiceNow calls). requests uses **certifi, not the OS store** [V:17]. Fix: set `REQUESTS_CA_BUNDLE` [V:17], or (a code decision for the planner) call `truststore.inject_into_ssl()` at startup. That needs Py ≥ 3.10 and uses macOS Security.framework / Windows CryptoAPI [V:18]. truststore 0.10.4 is a pure wheel [V:1].
3. **Proxy.** requests and pip honour `HTTPS_PROXY`/`NO_PROXY` [V:17] (pip by inheritance [U]). gcloud honours `https_proxy`, but the value must be an `http://` URL. Set `gcloud config set core/custom_ca_certs_file <pem>` for SSL inspection [V:19]. Whether `bq` follows those settings is undocumented [V:19 is silent → U].
4. **PyPI blocked.** Use `--index-url https://<internal-artifactory>/simple`, or set it persistently in `%APPDATA%\pip\pip.ini` (Windows) / `~/.config/pip/pip.conf` (macOS). `pip config debug` shows which file applies [V:5]. Otherwise use `--wheelhouse`.
5. **uv behind inspection** needs `UV_SYSTEM_CERTS=true` (0.11.0+) [V:8]. `SSL_CERT_FILE` overrides it [V:6][V:8].
6. **PowerShell.** A downloaded ZIP is marked as coming from the internet, so RemoteSigned blocks its unsigned `.ps1` files. Fix: `Unblock-File` [V:11]. GPO overrides `-ExecutionPolicy` [V:11]. Use `setup.cmd`.
7. **AppLocker/WDAC** may block `.venv\Scripts\python.exe` or `uv.exe` because they sit in a user-writable directory [U]. The doctor reports "venv python failed to start"; escalate to IT.
8. **gcloud found from a terminal but not from VS Code.** GUI launches strip PATH. `_find_gcloud()` already falls back to standard SDK directories and `GCLOUD_BIN` [V:repo gcloud_tool.py:73-93]. When it finds nothing it **returns the bare string `"gcloud"`** [V:repo gcloud_tool.py:93], so the doctor must check that the result is a real file.
9. **Edge.** `channel="msedge"` [V:repo auth_tool.py:83] needs **only an installed Edge. `playwright install` is not required** [V:20]. Running `playwright install msedge` overwrites the system Edge [V:20], so never script it. Playwright looks in fixed places: macOS **`/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge` only** (an Edge in `~/Applications` is not found). Windows: `\Microsoft\Edge\Application\msedge.exe` under `LOCALAPPDATA`, `PROGRAMFILES` and `PROGRAMFILES(X86)` [V:21].
10. **gcloud SDK without admin.** On macOS, extract the tar.gz into your home directory and run `./google-cloud-sdk/install.sh`; it bundles Python 3.14 [V:22]. On Windows, choose a per-user install to `%LOCALAPPDATA%\Google\Cloud SDK` [U]. The agent already looks there [V:repo gcloud_tool.py:48-51].

## 4. Doctor checklist (stdlib only, no network, no secret reads)
Each line reports PASS, WARN or FAIL, with a one-line fix command for the OS. Exit 1 on any FAIL.
1. Python ≥ 3.11, 64-bit, and running inside `.venv` (`sys.prefix != sys.base_prefix`). Otherwise: "activate: …".
2. **Required imports.** `requests`, `dotenv`, `urllib3`, `certifi`. Print versions with `importlib.metadata.version("python-dotenv")` etc., because the distribution name differs from the import name [U]. FAIL leads to "run setup".
3. **Optional imports.** `playwright` (WARN if missing: manual-cookie fallback), plus `google.cloud.bigquery` only if the sibling audit keeps that lazy path [V:repo bigquery_tool.py:211].
4. **Edge** at the Playwright paths in §3.9 (WARN).
5. **gcloud and bq.** Find them with `tools.gcloud_tool._find_gcloud()` / `tools.bigquery_tool._find_bq()` so detection matches runtime [V:repo]. Then check `os.path.isfile` (FAIL with install hint, §3.10). Optionally run `gcloud config get-value account` (local config read [U]) and WARN if it is not `@loreal.com`.
6. **Repo files.** `schema.json` exists. `.env` *exists*: check presence only, never read it or print its values. `.rca_tmp/` is writable.
7. **Network config summary.** Print only the **names** of the variables that are set (`HTTPS_PROXY`, `NO_PROXY`, `PIP_INDEX_URL`, `PIP_CERT`, `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`). Never print values, because proxy URLs can contain credentials.
8. Report the pip version and whether it is ≥ 24.2 (truststore) [V:2].

## Sources
1. PyPI JSON API, fetched 2026-10-12: https://pypi.org/pypi/{playwright,requests,python-dotenv,greenlet,pyee,truststore}/json and the pinned-version endpoints `/pypi/<pkg>/<ver>/json`
2. pip 24.2 release announcement and HTTPS certificates docs: https://discuss.python.org/t/announcement-pip-24-2-release/59402 · https://pip.pypa.io/en/latest/topics/https-certificates/
3. https://pip.pypa.io/en/stable/topics/https-certificates/ (`--cert`/`PIP_CERT`, `REQUESTS_CA_BUNDLE`, `--use-deprecated=legacy-certs`)
4. https://docs.python.org/3/using/windows.html (install manager, `py -V:`, per-user install, Store alias troubleshooting, python.org installer deprecated since 3.14)
5. https://pip.pypa.io/en/stable/topics/configuration/ (pip.ini/pip.conf locations, `PIP_<OPTION>`, precedence)
6. https://docs.astral.sh/uv/concepts/authentication/certificates/
7. https://docs.astral.sh/uv/getting-started/installation/
8. https://docs.astral.sh/uv/reference/environment/ (`UV_SYSTEM_CERTS` 0.11.0, `UV_NATIVE_TLS` deprecated, `UV_PYTHON_INSTALL_MIRROR`, `UV_DEFAULT_INDEX`); https://github.com/astral-sh/uv/issues/18689
9. https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github
10. https://discuss.python.org/t/pyinstaller-false-positive/43171 · https://beatsyncpro.ai/blog/why-pyinstaller-gets-antivirus-flags (community)
11. https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies
12. https://peps.python.org/api/release-cycle.json (3.9 EOL 2025-10-31, 3.10 EOL 2026-10-01)
13. https://www.python.org/downloads/release/python-3150/ (released Oct 9 2026)
14. https://elevenforum.com/t/what-are-python-exe-and-python3-exe-and-why-do-they-appear-to-point-to-app-installer.24886/ · https://learn.microsoft.com/en-us/answers/questions/2180769/ (community)
15. https://pip.pypa.io/en/stable/cli/pip_download/
16. https://code.visualstudio.com/docs/debugtest/tasks
17. https://requests.readthedocs.io/en/latest/user/advanced/ (CA certificates, proxies)
18. https://truststore.readthedocs.io/en/latest/
19. https://docs.cloud.google.com/sdk/docs/proxy-settings
20. https://playwright.dev/python/docs/browsers
21. https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/server/registry/index.ts (lines 631-639, 814-842; main branch)
22. https://docs.cloud.google.com/sdk/docs/install
