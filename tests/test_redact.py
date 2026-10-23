import json
import os
import unittest
import unittest.mock

from configdoctor.model import EnvironmentSnapshot, Finding, Repair
from configdoctor.redact import redact_text
from configdoctor.report import render_json, render_text


class RedactTextTests(unittest.TestCase):
    def test_linux_home_redacted(self):
        out = redact_text("path /home/alice/project/x.py", home_dir="/home/alice", username="alice")
        self.assertIn("~/project/x.py", out)
        self.assertNotIn("/home/alice", out)

    def test_windows_home_redacted_both_separators(self):
        out = redact_text(
            r"home C:\Users\bob\AppData and C:/Users/bob/other",
            home_dir=r"C:\Users\bob",
            username="bob",
        )
        self.assertNotIn(r"C:\Users\bob", out)
        self.assertNotIn("C:/Users/bob", out)
        self.assertIn("~", out)

    def test_macos_home_redacted(self):
        out = redact_text("dir /Users/carol/work", home_dir="/Users/carol", username="carol")
        self.assertNotIn("/Users/carol", out)

    def test_username_replaced_even_outside_home(self):
        out = redact_text("process owned by dave on port 8000", home_dir="/home/dave", username="dave")
        self.assertNotIn("dave", out)
        self.assertIn("<user>", out)

    def test_short_username_not_blindly_replaced(self):
        # Single-char usernames would nuke the text; they are left alone.
        out = redact_text("a b c", home_dir="/home/x", username="x")
        self.assertIn("a b c", out)

    def test_empty_identity_is_noop(self):
        out = redact_text("nothing to hide", home_dir="/nonexistent-hh", username="")
        self.assertIn("nothing to hide", out)

    def test_survives_environment_without_username(self):
        # Minimal containers unset USER/LOGNAME/etc.; getpass.getuser() then
        # raises OSError on Python 3.13+. Redaction must not crash.
        env = {k: v for k, v in os.environ.items()
               if k not in ("LOGNAME", "USER", "LNAME", "USERNAME")}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            out = redact_text("still works", home_dir="/nonexistent-hh", username="")
        self.assertIn("still works", out)


def _snapshot() -> EnvironmentSnapshot:
    return EnvironmentSnapshot(
        platform="windows",
        python_version="3.11.9",
        python_executable=r"C:\Users\erin\Python311\python.exe",
        in_virtualenv=False,
        virtual_env_var=None,
        path_entries=[r"C:\Users\erin\bin"],
        executables={"python": r"C:\Users\erin\Python311\python.exe", "pip": None},
        project_path=r"C:\Users\erin\project",
        project_files=["Pipfile"],
        project_venv_dirs=[],
        occupied_ports={8000: True},
        home_dir=r"C:\Users\erin",
        username="erin",
    )


def _findings():
    return [
        Finding(
            check_id="lockfile-missing",
            severity="error",
            title="Pipfile present but Pipfile.lock is missing",
            detail=r"Project at C:\Users\erin\project",
            repairs=[Repair(description="Generate the lockfile.", command="pipenv lock")],
        )
    ]


class ReportRedactionTests(unittest.TestCase):
    def test_text_report_unredacted_by_default(self):
        out = render_text(_snapshot(), _findings(), redact=False)
        self.assertIn(r"C:\Users\erin\project", out)

    def test_text_report_share_redacts(self):
        out = render_text(_snapshot(), _findings(), redact=True)
        self.assertNotIn(r"C:\Users\erin", out)
        self.assertNotIn("erin", out)
        self.assertIn("~", out)

    def test_json_report_redacts_by_default(self):
        out = render_json(_snapshot(), _findings())
        data = json.loads(out)  # must stay valid JSON after redaction
        self.assertNotIn(r"C:\Users\erin", out)
        self.assertNotIn("erin", out)
        self.assertTrue(data["project_path"].startswith("~"))
        self.assertEqual(data["findings"][0]["severity"], "error")


if __name__ == "__main__":
    unittest.main()
