"""Failure-focused tests for the API server's local-AI validation gate."""

import json

import pytest

from app import server_ai
from app.analyzer import compare_shipping_multiplier
from app.schemas import AnalysisResponse


def sample_analysis():
    """Build a deterministic finding fixture without shipping a demo endpoint."""
    before = "def calculate_shipping(subtotal):\n    return subtotal * 1.25\n"
    after = "def calculate_shipping(subtotal):\n    return subtotal * 1.5\n"
    documentation = "Shipping costs are calculated at 1.25 times the order subtotal."
    return AnalysisResponse(
        repository="test-repository",
        base_ref="before",
        head_ref="after",
        changed_files=["shipping.py"],
        findings=compare_shipping_multiplier(before, after, documentation),
    )


class FakeResponse:
    """A tiny urllib response stand-in; no model or network is needed in tests."""

    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size=-1):
        return self.body


def model_body(summary, correction=None, *, proposals=None):
    """Wrap a model draft in Ollama's JSON envelope."""
    finding = sample_analysis().findings[0]
    if proposals is None:
        proposals = [{
            "finding_index": 0,
            "summary": summary,
            "suggested_correction": correction or finding.suggested_correction,
        }]
    return json.dumps({"response": json.dumps({"proposals": proposals})}).encode("utf-8")


def enabled(monkeypatch):
    """Opt tests into local-AI mode while keeping its endpoint loopback-only."""
    monkeypatch.setenv("DOCUGUARD_AI_ENABLED", "true")
    monkeypatch.setenv("DOCUGUARD_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
    monkeypatch.setenv("DOCUGUARD_OLLAMA_MODEL", "test-model")


def test_ai_is_disabled_by_default_and_does_not_call_a_model(monkeypatch):
    monkeypatch.delenv("DOCUGUARD_AI_ENABLED", raising=False)
    monkeypatch.setattr(server_ai, "urlopen", lambda *_a, **_k: pytest.fail("model should stay off"))

    result = server_ai.validate_ai_output(sample_analysis())

    assert result.ai_validation.status == "disabled"
    assert result.findings[0].ai_validation_status == "disabled"
    assert "1.5 times" in result.findings[0].suggested_correction


def test_valid_ai_summary_is_accepted_but_correction_stays_rule_checked(monkeypatch):
    enabled(monkeypatch)
    monkeypatch.setattr(server_ai, "urlopen", lambda *_a, **_k: FakeResponse(model_body(
        "Shipping changed from 1.25 to 1.5, so the shipping documentation sentence is outdated."
    )))

    result = server_ai.validate_ai_output(sample_analysis())

    assert result.ai_validation.status == "validated"
    assert result.ai_validation.validated_count == 1
    assert result.findings[0].ai_validation_status == "validated"
    assert "1.25 to 1.5" in result.findings[0].summary
    assert result.findings[0].suggested_correction == "Shipping costs are calculated at 1.5 times the order subtotal."
    assert result.findings[0].code_evidence.path == "shipping.py"


def test_new_numeric_claim_is_rejected_with_deterministic_fallback(monkeypatch):
    enabled(monkeypatch)
    monkeypatch.setattr(server_ai, "urlopen", lambda *_a, **_k: FakeResponse(model_body(
        "Shipping changed from 1.25 to 1.5, an increase of 20%, so the documentation is outdated."
    )))

    result = server_ai.validate_ai_output(sample_analysis())

    assert result.ai_validation.status == "fallback"
    assert result.findings[0].ai_validation_status == "fallback"
    assert result.findings[0].summary.startswith("The return expression now multiplies by 1.5")


def test_model_cannot_change_the_deterministic_correction(monkeypatch):
    enabled(monkeypatch)
    monkeypatch.setattr(server_ai, "urlopen", lambda *_a, **_k: FakeResponse(model_body(
        "Shipping changed from 1.25 to 1.5, so the shipping documentation sentence is outdated.",
        "Shipping costs should now be 1.75 times the order subtotal.",
    )))

    result = server_ai.validate_ai_output(sample_analysis())

    assert result.ai_validation.status == "fallback"
    assert result.findings[0].suggested_correction == "Shipping costs are calculated at 1.5 times the order subtotal."


def test_malformed_model_json_falls_back_without_breaking_analysis(monkeypatch):
    enabled(monkeypatch)
    monkeypatch.setattr(server_ai, "urlopen", lambda *_a, **_k: FakeResponse(b'{"response":"not-json"}'))

    result = server_ai.validate_ai_output(sample_analysis())

    assert result.ai_validation.status == "fallback"
    assert result.findings[0].code_evidence.line == 2
    assert "deterministic findings" in result.ai_validation.message


def test_missing_or_duplicate_finding_indices_fall_back(monkeypatch):
    enabled(monkeypatch)
    one = {
        "finding_index": 0,
        "summary": "Shipping changed from 1.25 to 1.5, so the shipping documentation is outdated.",
        "suggested_correction": "Shipping costs are calculated at 1.5 times the order subtotal.",
    }
    duplicate = model_body(one["summary"], proposals=[one, one])
    monkeypatch.setattr(server_ai, "urlopen", lambda *_a, **_k: FakeResponse(duplicate))

    result = server_ai.validate_ai_output(sample_analysis())

    assert result.ai_validation.status == "fallback"


@pytest.mark.parametrize("failure", [TimeoutError("slow"), OSError("offline")])
def test_timeout_and_unavailable_model_fall_back(failure, monkeypatch):
    enabled(monkeypatch)

    def unavailable(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(server_ai, "urlopen", unavailable)
    result = server_ai.validate_ai_output(sample_analysis())

    assert result.ai_validation.status == "fallback"
    assert result.findings[0].suggested_correction.endswith("1.5 times the order subtotal.")


def test_remote_model_endpoint_is_rejected_before_any_request(monkeypatch):
    enabled(monkeypatch)
    monkeypatch.setenv("DOCUGUARD_OLLAMA_URL", "https://example.com/api/generate")
    monkeypatch.setattr(server_ai, "urlopen", lambda *_a, **_k: pytest.fail("remote endpoint must not be called"))

    result = server_ai.validate_ai_output(sample_analysis())

    assert result.ai_validation.status == "fallback"
    assert "only a local Ollama endpoint" in result.ai_validation.message


def test_empty_result_skips_ai_and_loopback_check_is_strict(monkeypatch):
    enabled(monkeypatch)
    empty = sample_analysis().model_copy(update={"findings": []})
    result = server_ai.validate_ai_output(empty)

    assert result.ai_validation.status == "skipped"
    assert server_ai.is_loopback_peer("127.0.0.1")
    assert server_ai.is_loopback_peer("::1")
    assert not server_ai.is_loopback_peer("192.168.1.20")
    assert not server_ai.is_loopback_peer(None)
