import unittest

from configdoctor.checks import (
    check_interpreter,
    check_package_manager,
    check_path,
    check_ports,
    check_required_commands,
    check_virtualenv,
    run_all_checks,
)
from helpers import make_snapshot


class InterpreterTests(unittest.TestCase):
    def test_modern_python_ok(self):
        f = check_interpreter(make_snapshot(python_version="3.12.4"))
        self.assertEqual(f.severity, "ok")

    def test_eol_python_warns(self):
        f = check_interpreter(make_snapshot(python_version="3.7.17"))
        self.assertEqual(f.severity, "warning")
        self.assertIn("3.7", f.title)


class VirtualenvTests(unittest.TestCase):
    def test_active_venv_ok(self):
        f = check_virtualenv(make_snapshot())
        self.assertEqual(f.severity, "ok")

    def test_venv_dir_present_but_not_active_linux(self):
        snap = make_snapshot(in_virtualenv=False, virtual_env_var=None, project_venv_dirs=[".venv"])
        f = check_virtualenv(snap)
        self.assertEqual(f.severity, "warning")
        self.assertEqual(f.repairs[0].command, "source .venv/bin/activate")

    def test_venv_dir_present_but_not_active_windows(self):
        snap = make_snapshot(
            platform="windows", in_virtualenv=False, virtual_env_var=None, project_venv_dirs=[".venv"]
        )
        f = check_virtualenv(snap)
        self.assertEqual(f.repairs[0].command, ".venv\\Scripts\\activate")

    def test_no_venv_with_deps_proposes_creation(self):
        snap = make_snapshot(in_virtualenv=False, virtual_env_var=None)
        f = check_virtualenv(snap)
        self.assertEqual(f.severity, "warning")
        self.assertIn("python -m venv .venv", [r.command for r in f.repairs])

    def test_no_venv_without_deps_is_info(self):
        snap = make_snapshot(in_virtualenv=False, virtual_env_var=None, project_files=["main.py"])
        f = check_virtualenv(snap)
        self.assertEqual(f.severity, "info")


class PackageManagerTests(unittest.TestCase):
    def test_pipfile_without_lock_is_error(self):
        findings = check_package_manager(make_snapshot(project_files=["Pipfile"]))
        self.assertTrue(any(f.check_id == "lockfile-missing" and f.severity == "error" for f in findings))

    def test_multiple_manifests_flagged(self):
        findings = check_package_manager(
            make_snapshot(project_files=["requirements.txt", "Pipfile", "Pipfile.lock"])
        )
        mismatch = [f for f in findings if f.check_id == "manager-mismatch"]
        self.assertTrue(mismatch)
        self.assertTrue(all(r.command is None or not r.destructive for f in mismatch for r in f.repairs if r.command))

    def test_requirements_mixed_with_poetry_lock(self):
        findings = check_package_manager(make_snapshot(project_files=["requirements.txt", "poetry.lock"]))
        self.assertTrue(any(f.check_id == "manager-mismatch" for f in findings))

    def test_pyproject_without_lockfile_warns(self):
        findings = check_package_manager(make_snapshot(project_files=["pyproject.toml"]))
        self.assertTrue(any(f.check_id == "lockfile-missing" and f.severity == "warning" for f in findings))

    def test_pyproject_with_lockfile_clean(self):
        findings = check_package_manager(make_snapshot(project_files=["pyproject.toml", "uv.lock"]))
        self.assertFalse(any(f.severity in ("error", "warning") for f in findings))

    def test_no_manifest_is_info(self):
        findings = check_package_manager(make_snapshot(project_files=["main.py"]))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "info")


class CommandTests(unittest.TestCase):
    def test_all_present_ok(self):
        f = check_required_commands(make_snapshot())
        self.assertEqual(f.severity, "ok")

    def test_missing_pip_is_error(self):
        f = check_required_commands(make_snapshot(executables={"python": "/usr/bin/python3", "pip": None}))
        self.assertEqual(f.severity, "error")
        self.assertIn("pip", f.title)


class PathTests(unittest.TestCase):
    def test_duplicates_detected_linux(self):
        snap = make_snapshot(path_entries=["/usr/bin", "/usr/local/bin", "/usr/bin"])
        findings = check_path(snap, path_exists=lambda p: True)
        self.assertTrue(any(f.check_id == "path-duplicates" for f in findings))

    def test_duplicates_case_insensitive_on_windows(self):
        snap = make_snapshot(
            platform="windows",
            path_entries=[r"C:\Tools", r"c:\tools", r"C:\Windows"],
        )
        findings = check_path(snap, path_exists=lambda p: True)
        self.assertTrue(any(f.check_id == "path-duplicates" for f in findings))

    def test_nonexistent_entries_detected(self):
        snap = make_snapshot(path_entries=["/usr/bin", "/gone/dir"])
        findings = check_path(snap, path_exists=lambda p: p != "/gone/dir")
        dead = [f for f in findings if f.check_id == "path-nonexistent"]
        self.assertTrue(dead)
        self.assertIn("/gone/dir", dead[0].detail)

    def test_clean_path_ok(self):
        findings = check_path(make_snapshot(), path_exists=lambda p: True)
        self.assertEqual(findings[0].severity, "ok")


class PortTests(unittest.TestCase):
    def test_free_ports_ok(self):
        f = check_ports(make_snapshot())
        self.assertEqual(f.severity, "ok")

    def test_busy_port_warns_linux(self):
        f = check_ports(make_snapshot(occupied_ports={8000: True}))
        self.assertEqual(f.severity, "warning")
        self.assertIn("ss -ltnp", f.repairs[0].command)

    def test_busy_port_warns_windows(self):
        f = check_ports(make_snapshot(platform="windows", occupied_ports={8000: True}))
        self.assertIn("netstat -ano", f.repairs[0].command)

    def test_port_kill_step_is_marked_destructive_and_manual(self):
        f = check_ports(make_snapshot(occupied_ports={3000: True}))
        destructive = [r for r in f.repairs if r.destructive]
        self.assertTrue(destructive)
        self.assertTrue(all(r.command is None for r in destructive))


class RunAllTests(unittest.TestCase):
    def test_run_all_returns_findings_for_every_area(self):
        findings = run_all_checks(make_snapshot(), path_exists=lambda p: True)
        ids = {f.check_id for f in findings}
        self.assertIn("interpreter", ids)
        self.assertIn("virtualenv", ids)
        self.assertIn("commands", ids)
        self.assertIn("ports", ids)


if __name__ == "__main__":
    unittest.main()
