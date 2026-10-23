"""Diagnostic checks. Each check is a pure function of an EnvironmentSnapshot
(plus an injectable path-existence predicate for PATH checks), so they can be
tested offline against synthetic snapshots and fixtures.
"""

from __future__ import annotations

import os
from collections import Counter

from .model import EnvironmentSnapshot, Finding, Repair

MIN_SUPPORTED_PYTHON = (3, 9)

MANAGER_FILES = {
    "requirements.txt": "pip",
    "Pipfile": "pipenv",
    "pyproject.toml": "pyproject (pip/pdm/hatch/poetry)",
    "setup.py": "setuptools",
}
LOCK_FILES = {
    "Pipfile.lock": "pipenv",
    "poetry.lock": "poetry",
    "pdm.lock": "pdm",
    "uv.lock": "uv",
}


def _version_tuple(version: str):
    parts = []
    for chunk in version.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_interpreter(snap: EnvironmentSnapshot) -> Finding:
    version = _version_tuple(snap.python_version)
    if version < MIN_SUPPORTED_PYTHON:
        return Finding(
            check_id="interpreter",
            severity="warning",
            title=f"Python {snap.python_version} is end-of-life",
            detail=(
                f"Interpreter: {snap.python_executable}\n"
                f"Python < {'.'.join(map(str, MIN_SUPPORTED_PYTHON))} no longer receives "
                "security fixes."
            ),
            repairs=[
                Repair(
                    description="Install a current Python release from python.org or your "
                    "package manager, then recreate your virtual environment.",
                    risk="Existing virtual environments keep pointing at the old "
                    "interpreter until recreated.",
                )
            ],
        )
    return Finding(
        check_id="interpreter",
        severity="ok",
        title=f"Python {snap.python_version}",
        detail=f"Interpreter: {snap.python_executable}",
    )


def check_virtualenv(snap: EnvironmentSnapshot) -> Finding:
    has_deps = any(f in snap.project_files for f in MANAGER_FILES)
    if snap.in_virtualenv:
        return Finding(
            check_id="virtualenv",
            severity="ok",
            title="Virtual environment active",
            detail=f"VIRTUAL_ENV={snap.virtual_env_var or '(set via sys.prefix)'}",
        )
    if snap.project_venv_dirs:
        activate = (
            f"{snap.project_venv_dirs[0]}\\Scripts\\activate"
            if snap.platform == "windows"
            else f"source {snap.project_venv_dirs[0]}/bin/activate"
        )
        return Finding(
            check_id="virtualenv",
            severity="warning",
            title="Project virtual environment exists but is NOT active",
            detail=(
                f"Found {', '.join(snap.project_venv_dirs)} in the project, but the "
                "current interpreter is the global one. Installs would go to the "
                "global site-packages."
            ),
            repairs=[Repair(description="Activate the project environment.", command=activate)],
        )
    if has_deps:
        create = "python -m venv .venv"
        return Finding(
            check_id="virtualenv",
            severity="warning",
            title="No virtual environment active",
            detail=(
                "The project declares dependencies but you are using the global "
                "interpreter; installs may pollute the system environment."
            ),
            repairs=[
                Repair(
                    description="Create an isolated environment for this project.",
                    command=create,
                ),
                Repair(
                    description="Activate it afterwards.",
                    command=".venv\\Scripts\\activate" if snap.platform == "windows" else "source .venv/bin/activate",
                ),
            ],
        )
    return Finding(
        check_id="virtualenv",
        severity="info",
        title="No virtual environment active",
        detail="No dependency files detected in the project; this may be fine.",
    )


def check_package_manager(snap: EnvironmentSnapshot) -> list:
    findings = []
    files = set(snap.project_files)
    managers = {f: m for f, m in MANAGER_FILES.items() if f in files}
    locks = {f: m for f, m in LOCK_FILES.items() if f in files}

    if "Pipfile" in files and "Pipfile.lock" not in files:
        findings.append(
            Finding(
                check_id="lockfile-missing",
                severity="error",
                title="Pipfile present but Pipfile.lock is missing",
                detail="Teammates and CI cannot reproduce this environment exactly.",
                repairs=[
                    Repair(
                        description="Generate the lockfile.",
                        command="pipenv lock",
                        risk="Resolves dependency versions anew; review the resulting "
                        "Pipfile.lock diff before committing.",
                    )
                ],
            )
        )

    if "pyproject.toml" in files and not any(l in files for l in ("poetry.lock", "pdm.lock", "uv.lock")):
        findings.append(
            Finding(
                check_id="lockfile-missing",
                severity="warning",
                title="pyproject.toml without any lockfile",
                detail="No poetry.lock, pdm.lock, or uv.lock found; builds are not "
                "reproducible. (Not all pyproject workflows use a lockfile — this may "
                "be intentional.)",
            )
        )

    if len(managers) > 1:
        names = ", ".join(sorted(managers))
        findings.append(
            Finding(
                check_id="manager-mismatch",
                severity="warning",
                title="Multiple package-manager manifests detected",
                detail=(
                    f"Found: {names}. Installing from the wrong manifest yields a "
                    "different environment than intended. Pick one source of truth."
                ),
                repairs=[
                    Repair(
                        description="Decide on one manager, delete the other manifest(s), "
                        "and regenerate the lockfile. This is a manual, destructive step "
                        "- ConfigDoctor will not run it for you.",
                        destructive=True,
                        risk="Deleting a manifest loses its pinned/declared versions.",
                    )
                ],
            )
        )

    if "requirements.txt" in files and locks:
        findings.append(
            Finding(
                check_id="manager-mismatch",
                severity="warning",
                title="requirements.txt mixed with a lockfile from another manager",
                detail=f"Found requirements.txt plus {', '.join(sorted(locks))}.",
            )
        )

    if not managers and not locks:
        findings.append(
            Finding(
                check_id="lockfile-missing",
                severity="info",
                title="No dependency manifest found",
                detail="No requirements.txt, Pipfile, pyproject.toml, or lockfile in "
                "the project root.",
            )
        )
    return findings


def check_required_commands(snap: EnvironmentSnapshot) -> Finding:
    missing = [name for name, path in snap.executables.items() if path is None]
    if not missing:
        resolved = "; ".join(f"{k} -> {v}" for k, v in sorted(snap.executables.items()))
        return Finding(
            check_id="commands",
            severity="ok",
            title="All expected commands found",
            detail=resolved,
        )
    severity = "error" if any(m in ("python", "pip") for m in missing) else "warning"
    return Finding(
        check_id="commands",
        severity=severity,
        title=f"Missing commands: {', '.join(sorted(missing))}",
        detail="These executables were not found on PATH.",
        repairs=[
            Repair(
                description=f"Install {m} or add its install directory to PATH, then "
                "open a new shell."
            )
            for m in sorted(missing)
        ],
    )


def check_path(snap: EnvironmentSnapshot, path_exists=os.path.isdir) -> list:
    findings = []
    norm = [e.rstrip("/\\").lower() if snap.platform == "windows" else e.rstrip("/") for e in snap.path_entries]
    dupes = sorted({e for e, count in Counter(norm).items() if count > 1})
    if dupes:
        findings.append(
            Finding(
                check_id="path-duplicates",
                severity="warning",
                title="Duplicate PATH entries",
                detail="Repeated entries (harmless but noisy, and they slow command "
                f"lookup): {', '.join(dupes)}",
                repairs=[
                    Repair(
                        description="Edit your user/system PATH and remove duplicates. "
                        "Manual step; back up the current PATH first.",
                        risk="A typo while editing PATH can break command resolution "
                        "for new shells.",
                    )
                ],
            )
        )
    dead = [e for e in snap.path_entries if not path_exists(e)]
    if dead:
        findings.append(
            Finding(
                check_id="path-nonexistent",
                severity="warning",
                title="PATH entries pointing at non-existent directories",
                detail="Stale entries: " + ", ".join(dead),
                repairs=[
                    Repair(
                        description="Remove the stale entries from PATH (manual step).",
                        risk="Only remove entries you recognize; some installers "
                        "recreate theirs.",
                    )
                ],
            )
        )
    if not findings:
        findings.append(
            Finding(check_id="path", severity="ok", title="PATH looks clean")
        )
    return findings


def check_ports(snap: EnvironmentSnapshot) -> Finding:
    busy = sorted(p for p, occupied in snap.occupied_ports.items() if occupied)
    if not busy:
        return Finding(
            check_id="ports",
            severity="ok",
            title="Common development ports are free",
            detail="Checked: " + ", ".join(str(p) for p in sorted(snap.occupied_ports)),
        )
    if snap.platform == "windows":
        inspect_cmd = "netstat -ano | findstr :" + str(busy[0])
    else:
        inspect_cmd = "ss -ltnp | grep :" + str(busy[0])
    return Finding(
        check_id="ports",
        severity="warning",
        title=f"Port conflict(s): {', '.join(map(str, busy))} already in use",
        detail="A local server on one of these ports will fail to bind.",
        repairs=[
            Repair(
                description="Identify which process owns the first busy port.",
                command=inspect_cmd,
            ),
            Repair(
                description="Stop that process, or configure your app to use a "
                "different port. Stopping processes is manual and never automated.",
                destructive=True,
                risk="Killing the wrong process can lose unsaved work.",
            ),
        ],
    )


def run_all_checks(snap: EnvironmentSnapshot, path_exists=os.path.isdir) -> list:
    findings = [check_interpreter(snap), check_virtualenv(snap)]
    findings.extend(check_package_manager(snap))
    findings.append(check_required_commands(snap))
    findings.extend(check_path(snap, path_exists=path_exists))
    findings.append(check_ports(snap))
    return findings
