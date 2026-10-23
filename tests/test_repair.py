import sys
import unittest

from configdoctor.model import Finding, Repair
from configdoctor.repair import executable_repairs, run_repairs


def _findings():
    return [
        Finding(
            check_id="lockfile-missing",
            severity="error",
            title="lockfile missing",
            repairs=[
                Repair(description="Generate lockfile.", command=f'"{sys.executable}" --version'),
                Repair(description="Delete the manifest.", destructive=True, risk="loses pins"),
            ],
        ),
        Finding(
            check_id="commands",
            severity="error",
            title="missing pip",
            repairs=[Repair(description="Install pip (manual).")],  # no command
        ),
    ]


class ExecutableFilterTests(unittest.TestCase):
    def test_destructive_and_manual_steps_never_yielded(self):
        pairs = list(executable_repairs(_findings()))
        self.assertEqual(len(pairs), 1)
        self.assertIn("--version", pairs[0][1].command)


class RunRepairsTests(unittest.TestCase):
    def test_declined_command_does_not_run(self):
        messages = []
        executed = run_repairs(
            _findings(), assume_yes=False, input_fn=lambda prompt: "n", print_fn=messages.append
        )
        self.assertEqual(executed, 0)
        self.assertTrue(any("skipped" in m for m in messages))
        self.assertTrue(any("command:" in m for m in messages))  # shown before asking

    def test_approved_command_runs(self):
        executed = run_repairs(
            _findings(), assume_yes=False, input_fn=lambda prompt: "y", print_fn=lambda m: None
        )
        self.assertEqual(executed, 1)

    def test_assume_yes_runs_without_prompting(self):
        def boom(prompt):
            raise AssertionError("input_fn must not be called with assume_yes")

        executed = run_repairs(_findings(), assume_yes=True, input_fn=boom, print_fn=lambda m: None)
        self.assertEqual(executed, 1)

    def test_missing_executable_is_reported_not_raised(self):
        findings = [
            Finding(
                check_id="x",
                severity="warning",
                title="t",
                repairs=[Repair(description="run ghost", command="definitely-not-a-real-cmd-xyz --help")],
            )
        ]
        messages = []
        executed = run_repairs(findings, assume_yes=True, print_fn=messages.append)
        self.assertEqual(executed, 0)
        self.assertTrue(any("exited with code" in m and "code 0" not in m for m in messages))


if __name__ == "__main__":
    unittest.main()
