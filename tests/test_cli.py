import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

from configdoctor.cli import main
from helpers import FIXTURES


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CliFixtureTests(unittest.TestCase):
    def test_pipfile_no_lock_fixture_exits_1_and_reports_error(self):
        code, out, _ = run_cli([os.path.join(FIXTURES, "pipfile_no_lock")])
        self.assertEqual(code, 1)
        self.assertIn("Pipfile.lock is missing", out)
        self.assertIn("pipenv lock", out)

    def test_mixed_managers_fixture_reports_mismatch(self):
        code, out, _ = run_cli([os.path.join(FIXTURES, "mixed_managers")])
        self.assertIn("Multiple package-manager manifests", out)
        self.assertIn("requirements.txt mixed with a lockfile", out)

    def test_venv_not_active_fixture_warns(self):
        _, out, _ = run_cli([os.path.join(FIXTURES, "venv_not_active")])
        self.assertIn("NOT active", out)

    def test_healthy_fixture_no_manager_findings(self):
        _, out, _ = run_cli([os.path.join(FIXTURES, "healthy")])
        self.assertNotIn("Multiple package-manager manifests", out)
        self.assertNotIn("lock is missing", out)

    def test_no_manifest_fixture_notes_absence(self):
        _, out, _ = run_cli([os.path.join(FIXTURES, "no_manifest")])
        self.assertIn("No dependency manifest found", out)

    def test_plan_is_shown_and_never_auto_executes(self):
        _, out, _ = run_cli([os.path.join(FIXTURES, "pipfile_no_lock")])
        self.assertIn("Proposed repair plan", out)
        self.assertIn("$ pipenv lock", out)  # shown, not run

    def test_json_output_is_valid_and_redacted(self):
        code, out, _ = run_cli([os.path.join(FIXTURES, "pipfile_no_lock"), "--json"])
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(data["tool"], "configdoctor")
        self.assertNotIn(os.path.expanduser("~"), json.dumps(data))

    def test_share_flag_redacts_text_output(self):
        _, out, _ = run_cli([os.path.join(FIXTURES, "healthy"), "--share"])
        home = os.path.expanduser("~")
        if len(home) > 2:
            self.assertNotIn(home, out)


class CliValidationTests(unittest.TestCase):
    def test_missing_path_is_error(self):
        code, _, err = run_cli(["/definitely/not/here"])
        self.assertEqual(code, 2)
        self.assertIn("does not exist", err)

    def test_yes_without_fix_rejected(self):
        code, _, err = run_cli(["--yes"])
        self.assertEqual(code, 2)
        self.assertIn("--fix", err)

    def test_invalid_port_rejected(self):
        with self.assertRaises(SystemExit):
            run_cli(["--ports", "abc"])

    def test_out_of_range_port_rejected(self):
        with self.assertRaises(SystemExit):
            run_cli(["--ports", "70000"])

    def test_empty_ports_rejected(self):
        with self.assertRaises(SystemExit):
            run_cli(["--ports", ",,"])

    def test_custom_ports_accepted(self):
        code, out, _ = run_cli([os.path.join(FIXTURES, "healthy"), "--ports", "12345"])
        self.assertIn("12345", out)


class CliEncodingTests(unittest.TestCase):
    def test_non_ascii_path_survives_legacy_console_encoding(self):
        # Simulate a Windows console stuck on a legacy codepage: even with
        # PYTHONIOENCODING=cp1252 the report must be valid UTF-8 and must not
        # mangle a non-ASCII project path.
        with tempfile.TemporaryDirectory(prefix="configdoctor-草稿-") as tmp:
            env = dict(os.environ, PYTHONIOENCODING="cp1252")
            proc = subprocess.run(
                [sys.executable, "-m", "configdoctor", tmp],
                cwd=os.path.dirname(os.path.dirname(FIXTURES)),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        text = proc.stdout.decode("utf-8")
        self.assertIn("草稿", text)


if __name__ == "__main__":
    unittest.main()
