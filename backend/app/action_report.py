"""Render a safe, human-readable report for the customer-run GitHub Action."""

from html import escape
import re

from .schemas import AnalysisResponse


def _markdown_text(value: str) -> str:
    """Escape customer-controlled text before placing it in a Markdown heading."""
    escaped = escape(value, quote=False)
    for character in "\\`*_{}[]()#+-.!|>":
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def _code_block(value: str) -> str:
    """Choose a fence longer than any run of backticks in repository content."""
    # A deliberately longer fence prevents repository content from closing it.
    longest = max((len(run) for run in re.findall(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{value}\n{fence}"


def render_action_summary(result: AnalysisResponse) -> str:
    """Format findings without turning repository text into executable markup."""
    count = len(result.findings)
    lines = [
        "## DocuGuard review",
        "",
        f"**Evidence-backed findings:** {count}",
        f"**Changed files:** {len(result.changed_files)}",
        "",
    ]

    if count == 0:
        lines.append("No supported shipping-multiplier drift was found by this rule.")
    else:
        for index, finding in enumerate(result.findings[:20], start=1):
            lines.extend([
                f"### {index}. {_markdown_text(finding.title)}",
                "",
                _markdown_text(finding.summary),
                "",
                f"**Code evidence · {_markdown_text(finding.code_evidence.path)}:{finding.code_evidence.line or '—'}**",
                "",
                _code_block(finding.code_evidence.excerpt),
                "",
                f"**Documentation evidence · {_markdown_text(finding.documentation_evidence.path)}:{finding.documentation_evidence.line or '—'}**",
                "",
                _code_block(finding.documentation_evidence.excerpt),
                "",
                f"**Suggested correction:** {_markdown_text(finding.suggested_correction)}",
                "",
            ])
        if count > 20:
            lines.append(f"Showing the first 20 findings; {count - 20} additional findings were omitted from this summary.")

    if result.review_prompts:
        lines.extend(["", "### Review prompts", ""])
        lines.extend(f"- {_markdown_text(prompt)}" for prompt in result.review_prompts)

    lines.extend(["", "_This focused rule is a review aid, not proof that every document is current. No files were changed._"])
    return "\n".join(lines) + "\n"
