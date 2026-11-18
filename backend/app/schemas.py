"""Pydantic response models keep the API's evidence shape predictable."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Evidence(BaseModel):
    """A source location and excerpt that lets a person verify a claim."""

    path: str
    line: int | None = None
    excerpt: str


class Finding(BaseModel):
    """A documentation drift result backed by code and Markdown evidence."""

    title: str
    summary: str
    rule: str = "shipping_multiplier"
    confidence: float = Field(ge=0, le=1, description="Rule-match indicator; not a calibrated probability.")
    code_evidence: Evidence
    documentation_evidence: Evidence
    suggested_correction: str
    # This status is assigned by the API server after its validation gate.
    ai_validation_status: Literal["disabled", "validated", "fallback"] = "disabled"


class AIValidation(BaseModel):
    """Server-owned account of whether optional AI output passed its gate."""

    status: Literal["disabled", "validated", "partial", "fallback", "skipped"] = "disabled"
    provider: str = "local Ollama"
    model: str | None = None
    validated_count: int = 0
    fallback_count: int = 0
    message: str = "AI explanations are off; deterministic findings are returned unchanged."


class SecurityStatus(BaseModel):
    """Safe-to-display local security posture; never returns secrets or paths."""

    network_scope: str
    repository_access: str
    persistence: str
    api_keys_in_browser: bool
    remote_ai_allowed: bool
    ai_enabled: bool
    hosted_auth_configured: bool
    hosted_auth_required: bool
    transport: str
    note: str


class DeletionStatus(BaseModel):
    """The deletion endpoint confirms what was cleared without recording a request."""

    status: Literal["no_saved_data"] = "no_saved_data"
    message: str


class AnalysisResponse(BaseModel):
    """Stable result returned by the local repository-analysis endpoint."""

    repository: str
    base_ref: str
    head_ref: str
    changed_files: list[str]
    findings: list[Finding]
    # These are workflow prompts, not verified contradictions or failing alerts.
    review_prompts: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    ai_validation: AIValidation = Field(default_factory=AIValidation)


class AIProposal(BaseModel):
    """Strict, limited shape accepted from the optional local language model."""

    model_config = ConfigDict(extra="forbid", strict=True)

    finding_index: int = Field(ge=0, le=19)
    summary: str = Field(min_length=20, max_length=320)
    suggested_correction: str = Field(min_length=10, max_length=500)


class AIProposalBatch(BaseModel):
    """The model must return one proposal for each reviewed finding."""

    model_config = ConfigDict(extra="forbid", strict=True)

    proposals: list[AIProposal] = Field(min_length=1, max_length=20)


class RepositoryAnalysisRequest(BaseModel):
    """Local Git repository and the two revisions to compare."""

    repository_path: str = Field(min_length=1, max_length=4096)
    base_ref: str = "HEAD~1"
    head_ref: str = "HEAD"

    @field_validator("base_ref", "head_ref")
    @classmethod
    def validate_git_ref(cls, value: str) -> str:
        """Keep refs bounded and prevent Git option injection at process calls."""
        if not value or len(value) > 255 or value.startswith("-") or any(ord(char) < 32 for char in value):
            raise ValueError("Use a valid local Git branch, tag, or commit reference.")
        return value
