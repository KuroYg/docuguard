"""One hundred reproducible randomized examples of the shipping drift rule.

The fixed seed makes failures repeatable while still exploring many different
factors, function names, evidence line positions, and sentence phrasing.
"""

import random

import pytest

from app.analyzer import compare_shipping_multiplier


def _examples():
    rng = random.Random(20261119)
    examples = []
    for case in range(100):
        old_tenths = rng.randint(10, 49)
        new_tenths = rng.choice([value for value in range(10, 50) if value != old_tenths])
        old_factor = f"{old_tenths / 10:.1f}"
        new_factor = f"{new_tenths / 10:.1f}"
        function_name = f"calculate_shipping_{case}"
        before = f"def {function_name}(subtotal):\n    return subtotal * {old_factor}\n"
        after = f"def {function_name}(subtotal):\n    return subtotal * {new_factor}\n"
        filler = "\n" * rng.randint(0, 8)
        phrasing = rng.choice((
            f"Shipping costs are {old_factor} times subtotal.",
            f"For shipping, multiply subtotal by {old_factor}.",
            f"The shipping charge uses a {old_factor} multiplier.",
        ))
        examples.append((before, after, filler + phrasing, old_factor, new_factor, len(filler.splitlines()) + 1))
    return examples


@pytest.mark.parametrize(
    "before,after,markdown,old_factor,new_factor,expected_line",
    _examples(),
    ids=[f"random-case-{index:03}" for index in range(100)],
)
def test_randomized_shipping_factor_changes_have_exact_evidence(
    before, after, markdown, old_factor, new_factor, expected_line
):
    """Each generated case must point to the changed return and stale prose."""
    findings = compare_shipping_multiplier(before, after, markdown)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.code_evidence.line == 2
    assert finding.documentation_evidence.line == expected_line
    assert old_factor in finding.documentation_evidence.excerpt
    canonical_new = new_factor.rstrip("0").rstrip(".")
    assert canonical_new in finding.suggested_correction
