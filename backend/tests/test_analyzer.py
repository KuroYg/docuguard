"""Tests explain the behavior we expect before adding more drift rules."""

import subprocess

from app.analyzer import analyze_repository, compare_shipping_multiplier, parse_markdown_sentences


def git(repo, *args):
    """Run Git against a temporary repository used by the integration test."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_markdown_parser_keeps_original_line_numbers_and_skips_fences():
    fence = chr(96) * 3
    markdown = "\n".join([
        "# Shipping", "", "Costs are 1.25x. Update when behavior changes.", "",
        fence + "py", "ignored = 1", fence, "",
    ])
    sentences = parse_markdown_sentences(markdown)
    assert [(item.line, item.text) for item in sentences] == [
        (3, "Costs are 1.25x."),
        (3, "Update when behavior changes."),
    ]


def test_no_finding_when_documentation_already_matches():
    old = "def calculate_shipping(subtotal):\n    return subtotal * 1.25\n"
    new = "def calculate_shipping(subtotal):\n    return subtotal * 1.5\n"
    assert compare_shipping_multiplier(old, new, "Shipping uses a 1.5 multiplier.") == []


def test_shipping_detector_requires_shipping_context():
    old = "def calculate_shipping(subtotal):\n    return subtotal * 1.25\n"
    new = "def calculate_shipping(subtotal):\n    return subtotal * 1.5\n"
    assert compare_shipping_multiplier(old, new, "The subtotal uses a 1.25 factor.") == []


def test_shipping_detector_ignores_unrelated_numeric_constants():
    old = "def calculate_shipping(subtotal):\n    tax = 0.2\n    return subtotal * 1.25\n"
    new = "def calculate_shipping(subtotal):\n    tax = 0.18\n    return subtotal * 1.5\n"
    findings = compare_shipping_multiplier(old, new, "Shipping is 1.25 times the subtotal.")
    assert len(findings) == 1
    assert "1.5 times" in findings[0].suggested_correction


def test_negative_shipping_factor_is_reported():
    old = "def calculate_shipping(subtotal):\n    return subtotal * 1.25\n"
    new = "def calculate_shipping(subtotal):\n    return subtotal * -1.5\n"
    assert compare_shipping_multiplier(old, new, "Shipping is 1.25 times the subtotal.") == []


def test_non_shipping_function_is_not_reported():
    old = "def calculate_total(subtotal):\n    return subtotal * 1.25\n"
    new = "def calculate_total(subtotal):\n    return subtotal * 1.5\n"
    assert compare_shipping_multiplier(old, new, "Shipping is 1.25 times the subtotal.") == []


def test_repository_analysis_finds_code_only_change_against_unchanged_readme(tmp_path):
    """A code-only PR still needs its unchanged documentation checked."""
    git(tmp_path, "init")
    git(tmp_path, "config", "user.name", "DocuGuard Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    (tmp_path / "shipping.py").write_text(
        "def calculate_shipping(subtotal):\n    return subtotal * 1.25\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "Shipping is calculated at 1.25 times the subtotal.\n",
        encoding="utf-8",
    )
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "baseline")
    base = git(tmp_path, "rev-parse", "HEAD")

    (tmp_path / "shipping.py").write_text(
        "def calculate_shipping(subtotal):\n    return subtotal * 1.5\n",
        encoding="utf-8",
    )
    git(tmp_path, "add", "shipping.py")
    git(tmp_path, "commit", "-m", "change shipping")
    head = git(tmp_path, "rev-parse", "HEAD")

    result = analyze_repository(str(tmp_path), base, head)
    assert result.changed_files == ["shipping.py"]
    assert len(result.findings) == 1
    # The review reminder stays distinct from a confirmed finding.
    assert result.review_prompts == [
        "Python code changed without a Markdown update. This is only a review prompt, not a confirmed documentation problem."
    ]
    assert result.findings[0].documentation_evidence.path == "README.md"
    assert result.findings[0].documentation_evidence.line == 1


def test_invalid_repository_returns_clear_error(tmp_path):
    try:
        analyze_repository(str(tmp_path), "main", "HEAD")
    except ValueError as error:
        assert "local Git repository" in str(error)
    else:
        raise AssertionError("Expected a clear error for a folder without Git")
