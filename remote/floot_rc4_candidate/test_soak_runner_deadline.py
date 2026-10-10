"""Regression checks for soak-runner deadline handling (runner v1.0.1)."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

RUNNER = pathlib.Path(__file__).with_name("soak_runner.py")


def run_probe(duration, exit_code):
    with tempfile.TemporaryDirectory(prefix="bodul_soak_regression_") as root:
        root = pathlib.Path(root)
        probe = root / "probe.py"
        probe.write_text(
            "import sys, time\n"
            "time.sleep(float(sys.argv[1]))\n"
            "raise SystemExit(int(sys.argv[2]))\n",
            encoding="utf-8",
        )
        output = root / "result"
        command = f"python {probe} {duration} {exit_code}"
        result = subprocess.run(
            [sys.executable, str(RUNNER), "--command", command,
             "--hours", "0.0002", "--output", str(output)],
            capture_output=True, text=True, timeout=30,
        )
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        iterations = [json.loads(line) for line in
                      (output / "iterations.jsonl").read_text(encoding="utf-8").splitlines()]
        return result, summary, iterations


class DeadlineRegression(unittest.TestCase):
    def test_started_iteration_can_finish_after_soak_deadline(self):
        result, summary, iterations = run_probe(1.5, 0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(summary["runner_version"], "1.0.1")
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["failures"], 0)
        self.assertGreaterEqual(summary["duration_seconds"], 0.72)
        self.assertEqual(iterations[-1]["returncode"], 0)

    def test_real_failure_remains_failure(self):
        result, summary, iterations = run_probe(0.05, 7)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(summary["failures"], 1)
        self.assertEqual(iterations[0]["returncode"], 7)


if __name__ == "__main__":
    unittest.main()
