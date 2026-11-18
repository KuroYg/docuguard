"""Authentication checks stay server-side and fail closed when configured."""

from urllib.error import HTTPError, URLError

from app import auth


def test_auth_is_optional_only_for_local_unconfigured_development(monkeypatch):
    monkeypatch.delenv("DOCUGUARD_AUTH_REQUIRED", raising=False)
    monkeypatch.delenv("DOCUGUARD_SUPABASE_URL", raising=False)
    monkeypatch.delenv("DOCUGUARD_SUPABASE_ANON_KEY", raising=False)
    assert auth.auth_is_required() is False
    assert auth.auth_configuration() is None
    assert not auth.protected_route_needs_auth("/analyze/repository")


def test_required_auth_fails_closed_without_provider_settings(monkeypatch):
    monkeypatch.setenv("DOCUGUARD_AUTH_REQUIRED", "true")
    monkeypatch.delenv("DOCUGUARD_SUPABASE_URL", raising=False)
    monkeypatch.delenv("DOCUGUARD_SUPABASE_ANON_KEY", raising=False)
    assert auth.protected_route_needs_auth("/analyze/repository")


def test_auth_configuration_requires_https_and_both_public_values(monkeypatch):
    monkeypatch.setenv("DOCUGUARD_SUPABASE_URL", "http://supabase.example")
    monkeypatch.setenv("DOCUGUARD_SUPABASE_ANON_KEY", "anon")
    assert auth.auth_configuration() is None
    monkeypatch.setenv("DOCUGUARD_SUPABASE_URL", "https://project.supabase.co")
    assert auth.auth_configuration() == ("https://project.supabase.co", "anon")


def test_partial_or_placeholder_supabase_settings_require_auth_and_fail_closed(monkeypatch):
    monkeypatch.setenv("DOCUGUARD_AUTH_REQUIRED", "false")
    monkeypatch.setenv("DOCUGUARD_SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.delenv("DOCUGUARD_SUPABASE_ANON_KEY", raising=False)
    assert auth.auth_configuration() is None
    assert auth.protected_route_needs_auth("/analyze/repository")

    monkeypatch.setenv("DOCUGUARD_SUPABASE_URL", "https://your-project.supabase.co")
    monkeypatch.setenv("DOCUGUARD_SUPABASE_ANON_KEY", "replace-with-public-anon-key")
    assert auth.auth_configuration() is None
    assert auth.protected_route_needs_auth("/analyze/repository")


def test_malformed_or_oversized_tokens_are_rejected():
    assert auth.bearer_token_from_header("Basic credentials") is None
    assert auth.bearer_token_from_header("Bearer ") is None
    assert auth.bearer_token_from_header("Bearer " + ("x" * 9000)) is None
    assert auth.bearer_token_from_header("Bearer signed-token") == "signed-token"


def test_configured_provider_auto_enforces_bearer_even_if_dev_flag_false(monkeypatch):
    monkeypatch.setenv("DOCUGUARD_AUTH_REQUIRED", "false")
    monkeypatch.setenv("DOCUGUARD_SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("DOCUGUARD_SUPABASE_ANON_KEY", "anon")
    assert auth.protected_route_needs_auth("/analyze/repository")


def test_provider_verification_returns_only_provider_user_claims(monkeypatch):
    monkeypatch.setenv("DOCUGUARD_SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("DOCUGUARD_SUPABASE_ANON_KEY", "public-anon")
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, _size): return b'{"id":"user-123","app_metadata":{"role":"user"}}'
    monkeypatch.setattr(auth, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    assert auth._verify_with_supabase("signed", ("https://project.supabase.co", "anon"))["id"] == "user-123"


def test_provider_rejection_is_treated_as_an_invalid_session(monkeypatch):
    def rejected(*_args, **_kwargs):
        raise HTTPError("https://project.supabase.co/auth/v1/user", 401, "invalid", {}, None)

    monkeypatch.setattr(auth, "urlopen", rejected)
    assert auth._verify_with_supabase("secret-token", ("https://project.supabase.co", "anon")) is None


def test_provider_outage_is_not_misreported_as_an_invalid_session(monkeypatch):
    monkeypatch.setattr(auth, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("private token leaked")))
    try:
        auth._verify_with_supabase("secret-token", ("https://project.supabase.co", "anon"))
    except auth.AuthProviderUnavailable:
        pass
    else:
        raise AssertionError("provider outage must be distinguishable from invalid credentials")


def test_provider_throttle_is_reported_as_unavailable(monkeypatch):
    def throttled(*_args, **_kwargs):
        raise HTTPError("https://project.supabase.co/auth/v1/user", 429, "rate limited", {}, None)

    monkeypatch.setattr(auth, "urlopen", throttled)
    try:
        auth._verify_with_supabase("signed-token", ("https://project.supabase.co", "anon"))
    except auth.AuthProviderUnavailable:
        pass
    else:
        raise AssertionError("provider throttling must be retryable")


def test_health_route_is_not_marked_protected(monkeypatch):
    monkeypatch.setenv("DOCUGUARD_AUTH_REQUIRED", "true")
    assert not auth.protected_route_needs_auth("/health")


def test_authorization_uses_only_trusted_app_metadata():
    assert auth.authorized_role({"user_metadata": {"role": "admin"}}) == "user"
    assert auth.authorized_role({"app_metadata": {"role": "user"}}) == "user"
    assert auth.authorized_role({"app_metadata": {"role": "admin"}}) == "admin"
    assert auth.authorized_role({"app_metadata": {"role": "owner"}}) is None


def test_customer_profile_authorization_is_scoped_to_verified_user_and_session(monkeypatch):
    observed = {}

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, _size): return b'[{"account_status":"active"}]'

    def fake_urlopen(request, **_kwargs):
        observed["url"] = request.full_url
        observed["headers"] = request.header_items()
        return FakeResponse()

    monkeypatch.setattr(auth, "urlopen", fake_urlopen)
    assert auth._active_customer_profile("customer-123", "signed-token", ("https://project.supabase.co", "public-anon")) is True
    assert "user_id=eq.customer-123" in observed["url"]
    assert dict(observed["headers"])["Authorization"] == "Bearer signed-token"


def test_customer_profile_authorization_fails_closed_for_inactive_or_unavailable_accounts(monkeypatch):
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, _size): return b'[{"account_status":"deletion_pending"}]'

    monkeypatch.setattr(auth, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    config = ("https://project.supabase.co", "public-anon")
    assert auth._active_customer_profile("customer-123", "signed-token", config) is False
    monkeypatch.setattr(auth, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("offline")))
    assert auth._active_customer_profile("customer-123", "signed-token", config) is None
