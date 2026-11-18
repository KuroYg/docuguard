"""Customer workflow report tests keep untrusted repository text inert."""

import json

from app.action_report import render_action_summary
from app.action_runner import pull_request_revisions
from app.analyzer import compare_shipping_multiplier
from app.schemas import AnalysisResponse


def test_pull_request_event_uses_exact_immutable_commit_ids(tmp_path):
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps({
        "pull_request": {
            "base": {"sha": "a" * 40},
            "head": {"sha": "b" * 40},
        },
    }), encoding="utf-8")

    assert pull_request_revisions(str(event_path)) == ("a" * 40, "b" * 40)


def test_action_rejects_non_pull_request_events(tmp_path):
    event_path = tmp_path / "event.json"
    event_path.write_text('{"workflow_dispatch":{}}', encoding="utf-8")

    try:
        pull_request_revisions(str(event_path))
    except ValueError as error:
        assert "pull_request workflow" in str(error)
    else:
        raise AssertionError("non-pull-request events must not scan guessed refs")


def test_summary_escapes_customer_paths_and_preserves_evidence():
    code = "def calculate_shipping(total):\n    return total * 1.5\n"
    docs = "Shipping costs are 1.25 times the total."
    finding = compare_shipping_multiplier(
        "def calculate_shipping(total):\n    return total * 1.25\n",
        code,
        docs,
        python_path="<img src=x onerror=alert(1)>.py",
    )[0]
    result = AnalysisResponse(
        repository="private-local-path",
        base_ref="base",
        head_ref="head",
        changed_files=[finding.code_evidence.path],
        findings=[finding],
    )

    summary = render_action_summary(result)

    assert "&lt;img" in summary
    assert "onerror=alert\\(1\\)" in summary
    assert "return total * 1.5" in summary
    assert "1.25 times" in summary
    assert "private-local-path" not in summary
