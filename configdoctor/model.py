"""Core data structures shared by probing, checks, reporting, and repair."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Repair:
    """A single proposed repair action.

    ``command`` is shown verbatim to the user and is only ever executed after
    explicit opt-in. ``risk`` explains what could go wrong.
    """

    description: str
    command: Optional[str] = None  # None = manual step, nothing to execute
    risk: str = ""
    destructive: bool = False


@dataclass
class Finding:
    """One diagnostic result."""

    check_id: str
    severity: str  # "error" | "warning" | "info" | "ok"
    title: str
    detail: str = ""
    repairs: list = field(default_factory=list)  # list[Repair]


@dataclass
class EnvironmentSnapshot:
    """Everything checks need to know about the machine and project.

    Built by probe.probe() for the real system, or constructed directly in
    tests / from fixture JSON for synthetic scenarios. Checks are pure
    functions of this snapshot, which keeps them testable offline and
    platform-independent.
    """

    platform: str  # "windows" | "linux" | "darwin"
    python_version: str  # e.g. "3.13.11"
    python_executable: str
    in_virtualenv: bool
    virtual_env_var: Optional[str]  # value of $VIRTUAL_ENV, if set
    path_entries: list = field(default_factory=list)  # PATH split into entries
    executables: dict = field(default_factory=dict)  # name -> resolved path or None
    project_path: str = ""
    project_files: list = field(default_factory=list)  # top-level file names
    project_venv_dirs: list = field(default_factory=list)  # e.g. [".venv"]
    occupied_ports: dict = field(default_factory=dict)  # port -> True if bind failed
    home_dir: str = ""
    username: str = ""
