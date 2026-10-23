"""Execute repair commands - only ever with explicit per-command opt-in.

ConfigDoctor NEVER runs anything automatically. Every executable repair is
shown verbatim and requires a ``y`` answer (or ``--yes`` plus ``--fix`` on the
command line). Steps marked destructive are manual advice and are never run.

Commands run through the platform shell so that the exact string shown to the
user is the exact string executed; this is safe because each command is
displayed and individually approved first.
"""

from __future__ import annotations

import subprocess

from .model import Finding


def executable_repairs(findings):
    """Yield (finding, repair) pairs that have a command and are not destructive."""
    for f in findings:
        for r in f.repairs:
            if r.command and not r.destructive:
                yield f, r


def run_repairs(findings, assume_yes: bool = False, input_fn=input, print_fn=print) -> int:
    """Walk the user through repairs. Returns the number of commands that exited 0."""
    executed = 0
    for finding, repair in executable_repairs(findings):
        print_fn("")
        print_fn(f"Repair for [{finding.check_id}]: {repair.description}")
        print_fn(f"  command: {repair.command}")
        if repair.risk:
            print_fn(f"  risk:    {repair.risk}")
        if assume_yes:
            print_fn("  (--yes given) running.")
            approved = True
        else:
            try:
                approved = input_fn("Run this command? [y/N] ").strip().lower() == "y"
            except (EOFError, KeyboardInterrupt):
                print_fn("  no input available - skipping (default is always 'no').")
                approved = False
        if not approved:
            print_fn("  skipped.")
            continue
        try:
            result = subprocess.run(repair.command, shell=True, check=False)
        except OSError as exc:
            print_fn(f"  failed to run: {exc}")
            continue
        print_fn(f"  exited with code {result.returncode}")
        if result.returncode == 0:
            executed += 1
    return executed
