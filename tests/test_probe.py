import os
import unittest

from configdoctor.probe import normalize_platform, probe, scan_project
from helpers import FIXTURES


class NormalizePlatformTests(unittest.TestCase):
    def test_windows(self):
        self.assertEqual(normalize_platform("win32"), "windows")

    def test_linux(self):
        self.assertEqual(normalize_platform("linux"), "linux")

    def test_macos(self):
        self.assertEqual(normalize_platform("darwin"), "darwin")


class ScanProjectTests(unittest.TestCase):
    def test_fixture_files_detected(self):
        files, venvs = scan_project(os.path.join(FIXTURES, "mixed_managers"))
        self.assertIn("requirements.txt", files)
        self.assertIn("Pipfile", files)
        self.assertIn("poetry.lock", files)
        self.assertEqual(venvs, [])

    def test_venv_dir_detected(self):
        _, venvs = scan_project(os.path.join(FIXTURES, "venv_not_active"))
        self.assertEqual(venvs, [".venv"])

    def test_missing_directory_returns_empty(self):
        files, venvs = scan_project("/definitely/not/here")
        self.assertEqual((files, venvs), ([], []))


class ProbeSmokeTests(unittest.TestCase):
    def test_probe_returns_consistent_snapshot(self):
        snap = probe(os.path.join(FIXTURES, "healthy"), ports=(19999,))
        self.assertIn(snap.platform, ("windows", "linux", "darwin"))
        self.assertTrue(snap.python_version.count(".") >= 1)
        self.assertTrue(os.path.isfile(snap.python_executable))
        self.assertIn("requirements.txt", snap.project_files)
        self.assertIn(19999, snap.occupied_ports)
        self.assertIn("python", snap.executables)
        self.assertTrue(snap.path_entries)  # PATH is never empty in CI/dev shells


if __name__ == "__main__":
    unittest.main()
