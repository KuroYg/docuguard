"""Deterministic, evidence-backed checks for documentation drift.

The first rule is intentionally narrow: when a changed Python shipping function
multiplies its input by a new factor, look through the repository's Markdown at
the new revision for a shipping sentence that still states the old factor.
Keeping this rule small makes the result reproducible and easy to verify.
"""

import ast
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .schemas import AnalysisResponse, Evidence, Finding


@dataclass
class MarkdownSentence:
    """One prose sentence, paired with its original 1-based line number."""

    line: int
    text: str


def parse_markdown_sentences(markdown: str) -> list[MarkdownSentence]:
    """Collect prose sentences while ignoring headings and fenced code.

    Line numbers are captured before any text is cleaned, so a finding points
    back to the line the author sees in their editor.
    """
    sentences: list[MarkdownSentence] = []
    inside_fence = False
    for line_number, raw_line in enumerate(markdown.splitlines(), start=1):
        if re.match(r"^\s{0,3}(`{3,}|~{3,})", raw_line):
            inside_fence = not inside_fence
            continue
        if inside_fence:
            continue
        cleaned = re.sub(r"^\s{0,3}(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)", "", raw_line).strip()
        if not cleaned or raw_line.lstrip().startswith("#"):
            continue
        for part in re.split(r"(?<=[.!?])\s+", cleaned):
            if part:
                sentences.append(MarkdownSentence(line=line_number, text=part))
    return sentences


def extract_functions(source: str) -> dict[str, tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]]:
    """Map each function to its syntax tree node and exact source excerpt."""
    tree = ast.parse(source)
    lines = source.splitlines()
    functions: dict[str, tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            excerpt = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            # A qualified name prevents nested or repeated function names from
            # silently overwriting one another in the lookup.
            functions[f"{node.name}@{node.lineno}"] = (node, excerpt)
    return functions


def _multiplier_returns(node: ast.AST) -> list[tuple[float, int]]:
    """Find numeric factors only when they multiply a non-literal value."""
    factors: list[tuple[float, int]] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Return) or child.value is None:
            continue
        value = child.value
        if not isinstance(value, ast.BinOp) or not isinstance(value.op, ast.Mult):
            continue
        for possible_factor, other_side in ((value.left, value.right), (value.right, value.left)):
            if (
                isinstance(possible_factor, ast.Constant)
                and isinstance(possible_factor.value, (int, float))
                and not isinstance(possible_factor.value, bool)
                and not isinstance(other_side, ast.Constant)
            ):
                factors.append((float(possible_factor.value), child.lineno))
    return factors


def _number_text(value: float) -> str:
    """Format whole-number factors without an unnecessary .0 suffix."""
    return str(int(value)) if value.is_integer() else str(value)


def _number_pattern(value: float) -> str:
    """Match the displayed factor, including harmless trailing zeroes."""
    displayed = re.escape(_number_text(value))
    if value.is_integer():
        displayed += r"(?:\.0+)?"
    # A sentence-ending period is punctuation, while a period followed by a
    # digit continues a decimal number such as 4.25.
    return rf"(?<![\w.]){displayed}(?!\w|\.\d)"


def _mentions_number(sentence: str, number: float) -> bool:
    """Match a factor as a whole number token (so 1.5 does not match 1.50)."""
    return bool(re.search(_number_pattern(number), sentence))


def compare_shipping_multiplier(
    before_source: str,
    after_source: str,
    markdown: str,
    python_path: str = "shipping.py",
    markdown_path: str = "README.md",
) -> list[Finding]:
    """Find stale shipping factors and return evidence from both files."""
    before_functions = extract_functions(before_source)
    after_functions = extract_functions(after_source)
    sentences = parse_markdown_sentences(markdown)
    findings: list[Finding] = []

    # Pair functions by their name, preferring the same qualified source line.
    before_by_name = {key.split("@", 1)[0]: (node, excerpt) for key, (node, excerpt) in before_functions.items()}
    for _, (after_node, after_excerpt) in after_functions.items():
        name = after_node.name
        if "ship" not in name.lower() or name not in before_by_name:
            continue
        before_node, _ = before_by_name[name]
        old_factors = _multiplier_returns(before_node)
        new_factors = _multiplier_returns(after_node)
        for old_factor, _ in old_factors:
            for new_factor, code_line in new_factors:
                if old_factor == new_factor:
                    continue
                for sentence in sentences:
                    lower = sentence.text.lower()
                    if "ship" not in lower or not _mentions_number(sentence.text, old_factor):
                        continue
                    corrected = re.sub(
                        _number_pattern(old_factor),
                        _number_text(new_factor),
                        sentence.text,
                        count=1,
                    )
                    findings.append(
                        Finding(
                            title=f"Shipping behavior changed in {name}()",
                            summary=(
                                f"The return expression now multiplies by {new_factor:g}, "
                                f"while this documentation sentence still says {old_factor:g}."
                            ),
                            # The displayed label names the deterministic rule;
                            # a numeric confidence would imply calibration we do not have.
                            confidence=1.0,
                            code_evidence=Evidence(
                                path=python_path,
                                line=code_line,
                                excerpt=after_excerpt,
                            ),
                            documentation_evidence=Evidence(
                                path=markdown_path,
                                line=sentence.line,
                                excerpt=sentence.text,
                            ),
                            suggested_correction=corrected,
                        )
                    )
    return findings


def _git(repository: Path, *args: str, allow_missing: bool = False) -> str:
    """Call Git with an argument list (never a shell string)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        )
    except FileNotFoundError as error:
        raise ValueError("Git is not installed or is not available on this computer.") from error
    except subprocess.TimeoutExpired as error:
        raise ValueError("Git took too long to read this local repository.") from error
    except OSError as error:
        raise ValueError("Git could not read this local repository.") from error
    if result.returncode:
        if allow_missing:
            return ""
        raise ValueError(result.stderr.strip() or "Git could not read this repository.")
    return result.stdout


def _revision_file(repository: Path, revision: str, path: str) -> str:
    """Read a file from a Git revision, returning empty text if it did not exist."""
    return _git(repository, "show", f"{revision}:{path}", allow_missing=True)


def analyze_repository(repository_path: str, base_ref: str, head_ref: str) -> AnalysisResponse:
    """Compare Git revisions and search all tracked Markdown at the head.

    Documentation commonly remains unchanged when code behavior changes. For
    that reason, we search the full Markdown corpus at the new revision rather
    than only Markdown files included in the same diff.
    """
    repository = Path(repository_path).expanduser().resolve()
    if not repository.is_dir():
        raise ValueError("Choose a folder inside a local Git repository.")
    # rev-parse works with linked worktrees, whose .git entry is a file.
    try:
        _git(repository, "rev-parse", "--show-toplevel")
    except ValueError as error:
        raise ValueError("Choose a folder inside a local Git repository.") from error
    try:
        _git(repository, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
        _git(repository, "rev-parse", "--verify", f"{head_ref}^{{commit}}")
    except ValueError as error:
        raise ValueError("Choose base and changed refs that exist as Git commits.") from error

    changed = _git(repository, "diff", "--name-only", f"{base_ref}...{head_ref}").splitlines()
    python_files = [path for path in changed if path.endswith(".py")]
    tracked_at_head = _git(repository, "ls-tree", "-r", "--name-only", head_ref).splitlines()
    markdown_files = [
        path for path in tracked_at_head
        if path.lower().endswith((".md", ".markdown"))
        and not any(part in {".git", "node_modules", ".venv", "venv"} for part in Path(path).parts)
    ][:200]

    findings: list[Finding] = []
    notes = ["Rule checked: changed shipping return multipliers against shipping sentences in tracked Markdown."]
    if len(tracked_at_head) > 200:
        notes.append("Markdown search is capped at the first 200 tracked files for this MVP.")
    for python_path in python_files:
        old = _revision_file(repository, base_ref, python_path)
        new = _revision_file(repository, head_ref, python_path)
        if not old or not new:
            # New/deleted files have no before/after function pair to compare.
            continue
        for markdown_path in markdown_files:
            markdown = _revision_file(repository, head_ref, markdown_path)
            findings.extend(compare_shipping_multiplier(old, new, markdown, python_path, markdown_path))

    if not python_files:
        notes.append("No changed Python files were found in the selected revision range.")
    if not markdown_files:
        notes.append("No tracked Markdown files were found at the selected head revision.")
    changed_markdown = any(path.lower().endswith((".md", ".markdown")) for path in changed)
    review_prompts = []
    if python_files and not changed_markdown:
        # Co-change absence is a useful reminder, but it is not proof that docs
        # are stale; many implementation changes need no prose change at all.
        review_prompts.append(
            "Python code changed without a Markdown update. This is only a review prompt, not a confirmed documentation problem."
        )
    return AnalysisResponse(
        repository=str(repository),
        base_ref=base_ref,
        head_ref=head_ref,
        changed_files=changed,
        findings=findings,
        review_prompts=review_prompts,
        notes=notes,
    )
