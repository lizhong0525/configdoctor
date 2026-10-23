"""Command-line interface for ConfigDoctor."""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .checks import run_all_checks
from .probe import DEFAULT_PORTS, probe
from .repair import run_repairs
from .report import render_json, render_plan, render_text


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="configdoctor",
        description="Safe, read-only diagnostics for local Python development "
        "environments. Repair commands are shown, never run without opt-in.",
    )
    p.add_argument("path", nargs="?", default=".", help="project directory to diagnose (default: cwd)")
    p.add_argument("--json", action="store_true", help="emit a redacted JSON report (safe to share)")
    p.add_argument("--share", action="store_true", help="redact home paths and usernames in text output")
    p.add_argument("--fix", action="store_true", help="interactively offer to run proposed repair commands")
    p.add_argument("--yes", action="store_true", help="with --fix: skip the per-command prompt (still prints each command)")
    p.add_argument("--ports", default=",".join(str(x) for x in DEFAULT_PORTS),
                   help="comma-separated ports to check (default: %(default)s)")
    p.add_argument("--version", action="version", version=f"configdoctor {__version__}")
    return p


def _parse_ports(raw: str):
    ports = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            port = int(chunk)
        except ValueError:
            raise ValueError(f"invalid port {chunk!r} in --ports")
        if not (1 <= port <= 65535):
            raise ValueError(f"port {port} out of range 1-65535")
        ports.append(port)
    if not ports:
        raise ValueError("--ports must list at least one port")
    return ports


def _force_utf8_stdio():
    # Windows consoles default to a legacy codepage (e.g. cp936/cp1252), which
    # mangles non-ASCII project paths in the report. Reconfigure when possible.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv=None) -> int:
    _force_utf8_stdio()
    args = build_parser().parse_args(argv)

    if args.yes and not args.fix:
        print("error: --yes only makes sense together with --fix", file=sys.stderr)
        return 2
    if args.json and args.fix:
        print("error: --json cannot be combined with --fix "
              "(repairs need an interactive terminal)", file=sys.stderr)
        return 2
    if not os.path.isdir(args.path):
        print(f"error: project path does not exist or is not a directory: {args.path}", file=sys.stderr)
        return 2

    try:
        ports = _parse_ports(args.ports)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    snap = probe(args.path, ports=ports)
    findings = run_all_checks(snap)

    if args.json:
        # JSON output is always redacted: it is the shareable form.
        print(render_json(snap, findings, redact=True))
        return 1 if any(f.severity == "error" for f in findings) else 0

    print(render_text(snap, findings, redact=args.share))
    print(render_plan(findings, redact=args.share, snap=snap))

    if args.fix:
        print("")
        print("--fix: each command below is shown before it runs; nothing runs")
        print("without your approval. Manual/destructive steps are never executed.")
        run_repairs(findings, assume_yes=args.yes)

    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
