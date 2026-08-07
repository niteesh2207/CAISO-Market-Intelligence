from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "detect_secrets",
        "scan",
        "--all-files",
        "--exclude-files",
        r"(^|[\\/])(?:\.git|\.venv|\.ruff_cache|\.pytest_cache)(?:[\\/]|$)",
        "--exclude-lines",
        "PUBLIC_API_KEY",
        "--exclude-secrets",
        r"^test-key$",
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    results = json.loads(completed.stdout).get("results", {})

    if results:
        print("Potential secrets detected:", file=sys.stderr)
        print(json.dumps(results, indent=2, sort_keys=True), file=sys.stderr)
        return 1

    print("Secret scan passed: no unapproved findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
