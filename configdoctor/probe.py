"""Collect a real EnvironmentSnapshot from the local machine.

Everything here is read-only: we inspect files, environment variables, PATH
resolution, and try binding TCP ports (immediately closed). Nothing is
modified and nothing is sent anywhere.
"""

from __future__ import annotations

import os
import platform
import shutil
import socket
import sys

from .model import EnvironmentSnapshot

DEFAULT_PORTS = (3000, 5000, 5432, 6379, 8000, 8080)
REQUIRED_COMMANDS = ("python", "pip")
OPTIONAL_COMMANDS = ("git",)
VENV_DIR_NAMES = (".venv", "venv", "env", ".env")


def normalize_platform(raw: str) -> str:
    if raw.startswith("win"):
        return "windows"
    if raw.startswith("linux"):
        return "linux"
    if raw == "darwin":
        return "darwin"
    return raw


def _split_path(path_value: str, plat: str) -> list:
    sep = ";" if plat == "windows" else ":"
    return [e for e in path_value.split(sep) if e.strip()]


def _port_occupied(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return False
    except OSError:
        return True
    finally:
        s.close()


def scan_project(project_path: str) -> tuple:
    """Return (top_level_file_names, venv_dir_names) for a project directory."""
    files, venvs = [], []
    try:
        entries = sorted(os.listdir(project_path))
    except OSError:
        return files, venvs
    for name in entries:
        full = os.path.join(project_path, name)
        if os.path.isfile(full):
            files.append(name)
        elif os.path.isdir(full) and name in VENV_DIR_NAMES:
            if os.path.isfile(os.path.join(full, "pyvenv.cfg")):
                venvs.append(name)
            else:
                venvs.append(name)  # directory exists; validity checked later
    return files, venvs


def probe(project_path: str = ".", ports=DEFAULT_PORTS, extra_commands=()) -> EnvironmentSnapshot:
    plat = normalize_platform(sys.platform)
    project_path = os.path.abspath(project_path)
    files, venvs = scan_project(project_path)

    executables = {}
    for name in list(REQUIRED_COMMANDS) + list(OPTIONAL_COMMANDS) + list(extra_commands):
        executables[name] = shutil.which(name)

    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)

    return EnvironmentSnapshot(
        platform=plat,
        python_version=platform.python_version(),
        python_executable=sys.executable,
        in_virtualenv=in_venv,
        virtual_env_var=os.environ.get("VIRTUAL_ENV"),
        path_entries=_split_path(os.environ.get("PATH", ""), plat),
        executables=executables,
        project_path=project_path,
        project_files=files,
        project_venv_dirs=venvs,
        occupied_ports={p: _port_occupied(p) for p in ports},
        home_dir=os.path.expanduser("~"),
        username=os.environ.get("USERNAME") or os.environ.get("USER") or "",
    )
