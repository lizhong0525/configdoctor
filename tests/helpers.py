"""Shared helpers for building synthetic EnvironmentSnapshots."""

import os

from configdoctor.model import EnvironmentSnapshot

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def make_snapshot(**overrides) -> EnvironmentSnapshot:
    base = dict(
        platform="linux",
        python_version="3.11.9",
        python_executable="/usr/bin/python3",
        in_virtualenv=True,
        virtual_env_var="/home/dev/project/.venv",
        path_entries=["/usr/bin", "/usr/local/bin"],
        executables={"python": "/usr/bin/python3", "pip": "/usr/bin/pip", "git": "/usr/bin/git"},
        project_path="/home/dev/project",
        project_files=["requirements.txt"],
        project_venv_dirs=[],
        occupied_ports={3000: False, 8000: False},
        home_dir="/home/dev",
        username="dev",
    )
    base.update(overrides)
    return EnvironmentSnapshot(**base)
