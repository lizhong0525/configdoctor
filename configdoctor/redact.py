"""Redact home paths and usernames from text before it is shared.

Only applied to shareable output (``--share`` / JSON export); the local
terminal report keeps full paths so the user can act on them.
"""

from __future__ import annotations

import getpass
import os
import re


def _candidate_homes(home_dir: str = "", username: str = ""):
    home = home_dir or os.path.expanduser("~")
    user = username or getpass.getuser()
    homes = {home, os.path.realpath(home)}
    # Common layouts, so redaction also works on synthetic snapshots.
    if user:
        homes.add(os.path.join("/home", user))
        homes.add(os.path.join("/Users", user))
        homes.add(os.path.join("C:\\Users", user))
        homes.add(os.path.join("C:/Users", user))
    return {h for h in homes if h and h not in ("/", "\\")}, user


def redact_text(text: str, home_dir: str = "", username: str = "") -> str:
    """Replace home-directory prefixes and usernames with placeholders."""
    homes, user = _candidate_homes(home_dir, username)
    out = text
    for home in sorted(homes, key=len, reverse=True):
        if len(home) > 2:
            out = out.replace(home, "~")
            # Handle the other path separator style (Windows snapshots read on
            # POSIX and vice versa).
            alt = home.replace("\\", "/") if "\\" in home else home.replace("/", "\\")
            if alt != home:
                out = out.replace(alt, "~")
    if user and len(user) > 1:
        out = re.sub(re.escape(user), "<user>", out)
    return out


def redact_snapshot_text(text: str, snapshot) -> str:
    """Convenience wrapper that pulls identity hints from a snapshot."""
    return redact_text(text, getattr(snapshot, "home_dir", ""), getattr(snapshot, "username", ""))
