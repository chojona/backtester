"""Run independent NQ mathematical checks and write a machine-readable result.

Usage: python -m scripts.validate_nq_math --output results/nq-math-validation.json
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest


class ResultCollector:
    def __init__(self):
        self.checks = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or (report.when in ("setup", "teardown") and report.failed):
            self.checks.append({"id": report.nodeid, "phase": report.when,
                                "status": report.outcome,
                                "detail": str(report.longrepr) if report.failed else None})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/nq-math-validation.json"))
    args = parser.parse_args(argv)
    collector = ResultCollector()
    exit_code = int(pytest.main(["tests/test_nq_math_validation.py", "-q"], plugins=[collector]))
    result = {"suite": "nq-independent-math-v1", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "command": "python -m scripts.validate_nq_math --output " + str(args.output),
              "pytest_exit_code": exit_code, "checks": collector.checks,
              "summary": {status: sum(item["status"] == status for item in collector.checks)
                          for status in ("passed", "failed", "skipped")}}
    result["status"] = "PASS" if exit_code == 0 and result["summary"]["passed"] > 0 else "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Validation {result['status']}: {args.output}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
