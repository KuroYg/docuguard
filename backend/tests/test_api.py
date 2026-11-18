"""Endpoint contract tests run handlers directly for fast, port-free checks."""

import pytest
from fastapi import HTTPException

from app.main import analyze, health, security_status
from app.schemas import RepositoryAnalysisRequest


def test_health_endpoint():
    assert health() == {"status": "ok"}


def test_security_status_does_not_disclose_secrets_or_local_paths():
    payload = security_status()
    assert payload.api_keys_in_browser is False
    assert payload.remote_ai_allowed is False
    assert payload.repository_access == "Read-only Git inspection"
    assert "not TLS encryption" in payload.note


def test_git_option_injection_is_rejected_before_repository_access():
    with pytest.raises(ValueError, match="valid local Git"):
        RepositoryAnalysisRequest(repository_path="C:/sample", base_ref="--upload-pack=evil")


def test_invalid_repository_returns_actionable_http_error(tmp_path):
    request = RepositoryAnalysisRequest(
        repository_path=str(tmp_path), base_ref="main", head_ref="HEAD"
    )
    with pytest.raises(HTTPException) as error:
        analyze(request)
    assert error.value.status_code == 400
    assert "local Git repository" in error.value.detail
