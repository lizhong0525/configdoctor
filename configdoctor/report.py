"""Render findings as a terminal summary, a repair plan, or shareable JSON."""

from __future__ import annotations

import json

from .model import EnvironmentSnapshot, Finding
from .redact import redact_snapshot_text

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2, "ok": 3}
SEVERITY_BADGE = {
    "error": "[ERROR]",
    "warning": "[WARN] ",
    "info": "[INFO] ",
    "ok": "[ OK ] ",
}


def sort_findings(findings):
    return sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.check_id))


def render_text(snap: EnvironmentSnapshot, findings, redact: bool = False) -> str:
    lines = []
    lines.append("=" * 64)
    lines.append("ConfigDoctor diagnostic summary")
    lines.append("=" * 64)
    lines.append(f"Platform : {snap.platform}")
    lines.append(f"Python   : {snap.python_version} ({snap.python_executable})")
    lines.append(f"Project  : {snap.project_path}")
    lines.append(f"Venv     : {'active' if snap.in_virtualenv else 'not active'}")
    lines.append("")

    counts = {"error": 0, "warning": 0, "info": 0, "ok": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    lines.append(
        f"Result   : {counts['error']} error(s), {counts['warning']} warning(s), "
        f"{counts['info']} note(s), {counts['ok']} ok"
    )
    lines.append("")
    lines.append("Findings")
    lines.append("-" * 64)
    for f in sort_findings(findings):
        lines.append(f"{SEVERITY_BADGE.get(f.severity, '[????]')} {f.title}")
        if f.detail:
            for d in f.detail.splitlines():
                lines.append(f"         {d}")
    text = "\n".join(lines)
    return redact_snapshot_text(text, snap) if redact else text


def render_plan(findings, redact: bool = False, snap=None) -> str:
    lines = []
    lines.append("")
    lines.append("Proposed repair plan")
    lines.append("-" * 64)
    n = 0
    actionable = False
    for f in sort_findings(findings):
        for r in f.repairs:
            n += 1
            lines.append(f"{n}. ({f.check_id}) {r.description}")
            if r.command:
                actionable = True
                lines.append(f"   $ {r.command}")
            if r.destructive:
                lines.append("   ! manual/destructive step - never executed by ConfigDoctor")
            if r.risk:
                lines.append(f"   risk: {r.risk}")
    if n == 0:
        lines.append("Nothing to repair. Your environment looks healthy.")
    elif not actionable:
        lines.append("")
        lines.append("No executable commands proposed; the steps above are manual.")
    text = "\n".join(lines)
    if redact and snap is not None:
        text = redact_snapshot_text(text, snap)
    return text


def to_dict(snap: EnvironmentSnapshot, findings) -> dict:
    return {
        "tool": "configdoctor",
        "platform": snap.platform,
        "python_version": snap.python_version,
        "python_executable": snap.python_executable,
        "project_path": snap.project_path,
        "in_virtualenv": snap.in_virtualenv,
        "findings": [
            {
                "check_id": f.check_id,
                "severity": f.severity,
                "title": f.title,
                "detail": f.detail,
                "repairs": [
                    {
                        "description": r.description,
                        "command": r.command,
                        "risk": r.risk,
                        "destructive": r.destructive,
                    }
                    for r in f.repairs
                ],
            }
            for f in findings
        ],
    }


def _redact_value(value, snap):
    if isinstance(value, str):
        return redact_snapshot_text(value, snap)
    if isinstance(value, dict):
        return {k: _redact_value(v, snap) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v, snap) for v in value]
    return value


def render_json(snap: EnvironmentSnapshot, findings, redact: bool = True) -> str:
    """JSON export. Redaction defaults ON here because this is the shareable form.

    Redaction happens on the data before serialization so that JSON escaping
    cannot hide a home path from the redactor.
    """
    data = to_dict(snap, findings)
    if redact:
        data = _redact_value(data, snap)
    return json.dumps(data, indent=2)
