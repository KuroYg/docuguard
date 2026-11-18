"""Entry point for the repository-local GitHub Action; it never uploads source."""

import json
import os
import sys
from pathlib import Path

from .action_report import render_action_summary
from .analyzer import analyze_repository


def pull_request_revisions(event_path: str) -> tuple[str, str]:
    """Read immutable base/head commit IDs from GitHub's signed workflow event."""
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        pull_request = event["pull_request"]
        base = pull_request["base"]["sha"]
        head = pull_request["head"]["sha"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError("Run DocuGuard from a pull_request workflow so it can compare the exact base and head commits.") from error
    if not isinstance(base, str) or not isinstance(head, str) or not base or not head:
        raise ValueError("The pull request event did not include valid base and head commit IDs.")
    return base, head


def _append_github_file(path: str, content: str) -> None:
    """Append one report to GitHub's step summary/output file if available."""
    if not path:
        return
    with Path(path).open("a", encoding="utf-8", newline="\n") as output:
        output.write(content)


def main() -> int:
    event_path = os.getenv("GITHUB_EVENT_PATH", "")
    workspace = os.getenv("GITHUB_WORKSPACE", "")
    if not event_path or not workspace:
        print("DocuGuard Action requires the GitHub pull request event and checked-out workspace.", file=sys.stderr)
        return 2

    try:
        base, head = pull_request_revisions(event_path)
        result = analyze_repository(workspace, base, head)
        summary = render_action_summary(result)
    except (ValueError, OSError) as error:
        # Keep host paths and raw Git errors out of customer workflow logs.
        print(f"DocuGuard could not analyze this pull request: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        # An unexpected provider/runtime failure should be visible without
        # dumping repository paths, environment values, or tracebacks.
        print(f"DocuGuard encountered an unexpected analysis failure ({type(error).__name__}).", file=sys.stderr)
        return 2

    _append_github_file(os.getenv("GITHUB_STEP_SUMMARY", ""), summary)
    _append_github_file(os.getenv("GITHUB_OUTPUT", ""), f"finding-count={len(result.findings)}\n")
    print(f"DocuGuard found {len(result.findings)} evidence-backed finding(s).")
    if result.findings and os.getenv("DOCUGUARD_FAIL_ON_FINDINGS", "false").strip().lower() in {"1", "true", "yes"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
