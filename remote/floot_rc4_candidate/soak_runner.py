#!/usr/bin/env python3
"""Local duration-based soak runner. No external dependencies."""
import argparse
import datetime as dt
import json
import pathlib
import subprocess
import time

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--command", required=True, help="Existing verified test command (shell syntax)")
    p.add_argument("--hours", type=float, default=8)
    p.add_argument("--pause-seconds", type=float, default=0)
    p.add_argument("--output", default="soak-results")
    args = p.parse_args()
    if not (0 < args.hours <= 24):
        p.error("--hours must be between 0 and 24")
    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now(dt.timezone.utc)
    deadline = time.monotonic() + args.hours * 3600
    count = failures = 0
    records = out / "iterations.jsonl"
    status = "INCOMPLETE"
    try:
        with records.open("a", encoding="utf-8") as f:
            while time.monotonic() < deadline:
                count += 1
                begin = time.monotonic()
                # No shell: avoid command injection and ambiguous quoting.
                import shlex
                argv = shlex.split(args.command, posix=False if __import__("os").name == "nt" else True)
                if not argv:
                    raise ValueError("Empty test command")
                try:
                    result = subprocess.run(argv, capture_output=True, text=True, timeout=max(1, min(1800, deadline - time.monotonic())))
                    rc = result.returncode
                    stdout, stderr = result.stdout[-12000:], result.stderr[-12000:]
                except subprocess.TimeoutExpired as e:
                    rc, stdout, stderr = 124, "", "iteration timed out"
                failures += int(rc != 0)
                f.write(json.dumps({"iteration": count, "elapsed_seconds": round(time.monotonic()-begin, 3), "returncode": rc, "stdout_tail": stdout, "stderr_tail": stderr}, ensure_ascii=False) + "\n")
                f.flush()
                if rc != 0:
                    status = "FAIL"
                    break
                if args.pause_seconds:
                    time.sleep(min(args.pause_seconds, max(0, deadline-time.monotonic())))
        if status != "FAIL":
            status = "PASS" if time.monotonic() >= deadline and count > 0 and failures == 0 else "INCOMPLETE"
    except Exception as e:
        status = "ERROR"
        with (out / "error.txt").open("w", encoding="utf-8") as f:
            f.write(repr(e))
    finished = dt.datetime.now(dt.timezone.utc)
    report = {"status": status, "started_utc": started.isoformat(), "finished_utc": finished.isoformat(), "duration_seconds": (finished-started).total_seconds(), "target_hours": args.hours, "iterations": count, "failures": failures, "command": args.command}
    (out / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if status == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
