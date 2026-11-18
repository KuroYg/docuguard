# Hosted accounts, recovery, and scale plan

## What is implemented in this prototype

- The dashboard includes email/password create-account and sign-in screens backed by Supabase Auth when configured.
- Repository analysis sends a short-lived bearer token; when `DOCUGUARD_AUTH_REQUIRED=true`, FastAPI independently asks Supabase Auth to validate the token before starting the Git scan. Missing configuration fails closed with HTTP 503; missing, invalid, or expired identity returns HTTP 401.
- The customer profile table stores only an account UUID, account status, and creation time. Supabase Auth owns password credentials and sessions. Repository source, local paths, and analysis results are deliberately not stored in the hosted database.
- Sign out everywhere uses Supabase's global sign-out scope. Refresh tokens for every device are revoked after the server confirms the action. Existing access JWTs remain valid until expiry, so configure a short JWT lifetime and protect sensitive operations by verifying current identity server-side.
- A customer can create an account deletion request. Completion requires a trusted operator workflow that deletes the Auth user; the foreign-key cascade then removes the profile and request rows. This prototype does not pretend that clicking the button completes an asynchronous hosted deletion.

No hosted multi-customer service is deployed from this workspace. A configured Supabase account project can handle sign-in and minimal account records; production backups, alerts, lockout tuning, and remote analysis remain separate operational work.

## Provider setup before account launch

1. Create a Supabase project in the intended region and restrict dashboard access to named operators with MFA. The project URL and public anon/publishable key are available in the project's API settings; they are public identifiers, not substitutes for authentication.
2. Apply `backend/migrations/001_customer_accounts.sql` using the Supabase SQL editor or a linked CLI migration workflow. Confirm row-level security, function grants, and account creation trigger in a staging project.
3. Copy `frontend/.env.example` to `frontend/.env.local` and `backend/.env.example` to `backend/.env`. Replace the placeholders with the *same* project URL and public anon/publishable key. Keep the service-role/secret key out of both files and the browser. Set `VITE_API_URL=` for the same-origin packaged app, or leave the local default when running the API on port 8000.
4. In Supabase Auth URL settings, allow the local callback `http://127.0.0.1:8010/**` (and `http://localhost:8010/**` only if you use that hostname). Set the Site URL to the local app URL for local testing. For a later hosted domain, add only that exact HTTPS origin and callback.
5. In Supabase Auth settings, require email verification, configure password policy, enable CAPTCHA/bot protection, tune auth rate limits, and set a **7-day time-boxed session**. Supabase documents time-box controls as Pro plan and above. Set access-token JWT expiry to 5–15 minutes to bound the post-revocation window. Do not enable production until cross-device sign-out and expiry flows pass in staging.
6. Set `DOCUGUARD_AUTH_REQUIRED=true` in the API `.env` only after both API variables are present. Restart the API after changing environment files. Confirm a missing/expired bearer token gets 401 and an unavailable provider fails closed with 503. Partial, placeholder, or malformed settings also now fail closed rather than silently disabling auth.
6. Add recovery email/identity verification and alert routing in the provider console. Establish a monitored on-call contact and test alert delivery; this codebase has no alert destination configured yet.

## Lockout, session, and authorization controls

- Supabase Auth owns password hashing, email verification, token rotation, global refresh-token revocation, and abusive sign-in throttling. Configure provider-side lockout/rate limits and CAPTCHA; never build a custom password database in this API.
- All repository-analysis API calls validate the bearer token against the provider, not merely decode claims in the browser. Do not trust `user_metadata` for roles. A privileged role must be set only by a trusted admin workflow in `app_metadata` or equivalent server-managed policy.
- Current roles are `user` by default. There are no admin-only product routes yet. If any are added, enforce the trusted role on every server handler and add negative authorization tests.
- Keep account deletion and operator privileges out of ordinary user routes. Require verified operator identity, audit the action without logging secrets, and process deletion idempotently.

### Local environment setup (PowerShell)

Run these from the repository root after creating the Supabase project and applying the SQL migration:

```powershell
Copy-Item frontend/.env.example frontend/.env.local
Copy-Item backend/.env.example backend/.env
code frontend/.env.local
code backend/.env
```

Paste the project URL and the same public anon/publishable key into both files, then change `DOCUGUARD_AUTH_REQUIRED=true` in `backend/.env`. Keep these local files untracked; `.gitignore` excludes `.env*` except the safe example files. Rebuild the frontend and restart the API so both processes load the new settings. Verify the UI says **Sign in**, register a test account, verify its email, sign in, and run the repository analysis. Also test an expired/invalid token and a disabled profile; both must be rejected by the API. Do not share screenshots that reveal keys or project IDs unnecessarily.

The workspace currently has no Supabase project URL or key configured. The code and database migration are ready for configuration, but no real hosted account project has been provisioned or exercised from this workspace yet.

## Database backup and incident recovery

- Choose the Supabase plan and region based on required recovery-point and recovery-time objectives. Enable point-in-time recovery or the provider's appropriate backup plan; verify retention, encryption, and restore scope in current provider settings before launch.
- Schedule a restore drill in a separate staging project. A backup is not considered usable until a restore has been tested.
- For service failures: keep the local review workflow usable; show an honest auth/service outage state; do not queue or duplicate account mutations blindly. The API applies a short auth verification timeout and fails closed for protected scans. Retry transient reads with bounded exponential backoff and jitter; never retry bad credentials or validation errors.
- Wire health checks and provider/API error-rate alerts to an actual team destination before launch. Page the team on sustained auth failures, database errors, backup failures, or latency; no alerts are claimed active in the local build.
- Document incident owner, provider status link, credential rotation, user notification, and restore runbook before public launch.

## Capacity for 100 to 10,000 users

This is a capacity plan, not a claim that capacity has already been load-tested. Supabase Auth/Postgres provides a managed starting point. For an initial 100 users, begin with conservative plan sizing, pooling, indexes and request limits; measure concurrent analyses rather than only registered accounts. To grow toward 10,000 users:

1. Move Git analysis into isolated background workers with per-user quotas, bounded queue depth, CPU/memory/time limits, and cancellation. Never let an API worker clone arbitrary URLs or accept a caller-selected server filesystem path in a public deployment.
2. Keep request handlers stateless; use a managed queue and Postgres connection pooler. Add indexes only for measured account/job queries.
3. Keep repository content out of the account database by default. If a future hosted scan feature stores source or findings, add explicit opt-in, tenant-level authorization, encryption/key rotation, retention controls, and deletion/backup semantics first.
4. Add rate limits by user and IP, per-plan concurrency caps, provider quotas, and load shedding with clear retry-after messages.
5. Run staged load tests at expected peak concurrency and twice that level. Track p50/p95 latency, auth-provider error rate, queue wait, database saturation, worker memory, and cost. Scale based on measurements; do not claim 10,000-user readiness until the target workload passes.

## Local vs hosted boundary

The current Git-diff analyzer reads a path on the machine running FastAPI. Keep that API bound to loopback for local review. It is not a safe hosted multi-customer architecture: a remote client-selected path could expose host files. A hosted release needs a separately designed repository connection/import flow and isolated workers, HTTPS, secrets management, network firewall rules, logging/monitoring, threat review, and production deployment configuration.
