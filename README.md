# ConfigDoctor

A safe, read-only diagnostic CLI for Python developers: it inspects your local development environment, explains what is misconfigured, and hands you a repair plan — with the exact commands and their risks — without ever running anything on its own.

## Quickstart

```bash
python -m configdoctor path/to/your/project
```

No dependencies. Python 3.9+ standard library only. Nothing is sent anywhere; all probing is local and read-only.

## What it checks

| Area | What ConfigDoctor reports |
|---|---|
| Interpreter | Python version and executable path; warns on end-of-life versions (< 3.9) |
| Virtual environment | Whether a venv is active; detects a project `.venv` that exists but isn't activated; warns when a project with dependencies uses the global interpreter |
| Package manager / lockfiles | `Pipfile` without `Pipfile.lock`, `pyproject.toml` with no lockfile, multiple competing manifests (e.g. `requirements.txt` + `Pipfile` + `poetry.lock`) |
| Required commands | `python`, `pip`, `git` resolvable on PATH |
| PATH hygiene | Duplicate entries (case-insensitive on Windows), entries pointing at directories that no longer exist |
| Port conflicts | Common dev ports (3000, 5000, 5432, 6379, 8000, 8080 — configurable) already in use |

Every finding carries a severity (`error` / `warning` / `info` / `ok`), an explanation, and a repair plan.

## Safety model

- **Read-only by default.** A plain run only inspects files, environment variables, PATH resolution, and port availability (bind-and-close). Nothing is modified.
- **No automatic repairs.** `--fix` walks the repair plan interactively: each command is printed verbatim and runs only after you answer `y`. `--fix --yes` pre-approves, but still prints every command before it runs.
- **Destructive steps are never executed.** Actions like deleting a manifest or killing a process are presented as manual advice only.
- **No uploads, no telemetry.** There are no network calls at all. `--json` (the shareable form) and `--share` redact home paths and usernames before printing.

## Demo walkthrough (included fixtures)

Synthetic broken projects live in `tests/fixtures/`. Try the one with a `Pipfile` but no lockfile:

```bash
python -m configdoctor tests/fixtures/pipfile_no_lock
```

Output (abridged):

```
[ERROR] Pipfile present but Pipfile.lock is missing
         Teammates and CI cannot reproduce this environment exactly.
...
Proposed repair plan
1. (lockfile-missing) Generate the lockfile.
   $ pipenv lock
   risk: Resolves dependency versions anew; review the resulting Pipfile.lock diff before committing.
```

Exit code is `1` when any `error`-severity finding exists, `0` otherwise — usable as a pre-commit or CI sanity gate.

Other fixtures:

```bash
python -m configdoctor tests/fixtures/mixed_managers   # requirements.txt + Pipfile + poetry.lock
python -m configdoctor tests/fixtures/venv_not_active  # .venv exists but is not activated
python -m configdoctor tests/fixtures/healthy          # clean project
python -m configdoctor tests/fixtures/pipfile_no_lock --json   # redacted, shareable report
```

## CLI reference

```
python -m configdoctor [path] [--json] [--share] [--fix] [--yes] [--ports 3000,8000]
```

- `path` — project directory to diagnose (default: current directory)
- `--json` — emit a redacted JSON report (safe to paste into an issue)
- `--share` — redact home paths / usernames in the text report
- `--fix` — interactively offer to run proposed (non-destructive) repair commands
- `--yes` — with `--fix`, skip the per-command confirmation prompt
- `--ports` — comma-separated list of ports to check

## Development

```bash
python -m pytest -q        # 59 tests, fully offline, no third-party deps
```

Architecture: `probe.py` builds an `EnvironmentSnapshot` from the real machine; `checks.py` is a set of pure functions over that snapshot (so tests inject synthetic snapshots and fixture directories); `report.py` renders text/JSON with redaction; `repair.py` handles the opt-in execution flow.

## Troubleshooting

- **"Missing commands: pip"** — run `python -m ensurepip` or reinstall Python with pip included; make sure the Python `Scripts` directory is on PATH.
- **Venv "exists but not active"** — activate it: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Linux/macOS). If activation scripts are missing, recreate with `python -m venv .venv --clear`.
- **Port conflict reported but you don't know the owner** — run the suggested `netstat -ano | findstr :<port>` (Windows) or `ss -ltnp | grep :<port>` (Linux) command shown in the repair plan.
- **PATH warnings keep coming back** — some installers re-add their entries; remove duplicates from *both* the user and system PATH (Windows) or check shell rc files (Linux/macOS).

## Known limitations

- Python ecosystem only (v1 scope).
- Port checks detect *that* a port is busy, not *which* process owns it (the plan gives you the platform command for that).
- Lockfile detection is filename-based; it does not parse `pyproject.toml` to see whether the project actually uses poetry/pdm/uv.
- PATH staleness is checked against the local filesystem only.

## Roadmap

1. Parse `pyproject.toml` (via `tomllib`) to detect the actual build backend and only warn about genuinely missing lockfiles.
2. Additional ecosystems behind the same snapshot/check architecture (Node.js: node/npm version vs `.nvmrc`, `package.json` vs lockfile drift).
3. Process-owner lookup for busy ports (opt-in, via platform tools) and a `--watch` mode for pre-commit usage.

## License

MIT — see [LICENSE](LICENSE).
