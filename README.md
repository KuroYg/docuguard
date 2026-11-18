# DocuGuard

**Find the documentation sentence a code change made stale, and show the proof.**

DocuGuard is a local-first Python repository review tool. It compares two Git revisions, extracts changed Python functions with the AST, and checks those behavior changes against Markdown prose with original line numbers. Every result links the code excerpt and documentation sentence so a developer can verify it before editing anything.

## Launch the complete local product

Install Python 3 and Node.js, then run this from PowerShell in the project folder:

```powershell
.\Launch-DocuGuard.ps1
```

The launcher creates an isolated Python environment, installs the backend packages, builds the React dashboard, starts the API and finished dashboard together on loopback, waits for the health check, and opens Chrome. The address is `http://127.0.0.1:8010`. Enter a local Python Git repository folder, choose the base and head refs, and select **Review changes**. The app reads Git history locally and never uploads source files.

For dashboard development with hot reload, install packages under `frontend` with `npm install`, run the API on `127.0.0.1:8000`, then run `npm run dev` in `frontend`. Vite proxies API calls to that loopback service.

Stop the local release server by closing the DocuGuard Python process from Task Manager. Release logs are stored in `.local` and are excluded from Git.

## Accounts and safe preview boundaries

The dashboard includes Supabase email/password sign-up and sign-in. Local Supabase settings live in ignored `frontend/.env.local` and `backend/.env` files. Only the project's URL and public publishable key are used; never place a Supabase secret/service-role key in the browser or public repository. The migration at `backend/migrations/001_customer_accounts.sql` creates minimal account records with row-level security; repository content and analysis results are never stored there.

The database stores only an account ID, status, creation time, and deletion request. It intentionally does not save repository content or findings. Configure Supabase email verification, CAPTCHA/rate limits, a seven-day session timebox, and short-lived access JWTs in the provider console; the timebox setting is plan-dependent. **This is a deployable local product, not a hosted multi-customer service. Hosted accounts, backups, lockout policy, alerts, and cloud recovery are not active until an operator creates and configures a provider project.** Follow `docs/HOSTED_OPERATIONS.md` for the setup and recovery checklist.

The local analysis API accepts a folder path from the same machine, so it must remain loopback-only. Authentication does not make this path-based API safe to expose to the internet. A remote hosted version needs a separately designed repository import and isolated worker system.

To end a signed-in user's sessions, choose **End all sessions**. Supabase revokes refresh tokens for all devices; already-issued access tokens last until their configured expiry. See the security guide for this limitation.

## API

### `GET /health`

Returns `{ "status": "ok" }`.

### `POST /analyze/repository`

Request:

```json
{
  "repository_path": "C:/projects/storefront",
  "base_ref": "main",
  "head_ref": "HEAD"
}
```

The response includes the revision range, changed paths, a short rule scope note, and findings. A finding contains code and documentation evidence (path, line and excerpt), the deterministic rule identifier, and a suggested sentence. DocuGuard never applies the suggestion automatically.

## What the first rule checks

The MVP detects a changed return multiplication factor in a Python function whose name contains `ship`, then searches tracked Markdown at the head revision for a shipping sentence that states the old factor. Searching all Markdown matters because the docs often remain unchanged in the very pull request that caused the drift.

It is intentionally a focused rule, not a general-purpose semantic detector. A clear result means this rule found no matching shipping multiplier mismatch; it does not prove that all documentation is current. The `confidence` field is a rule-match indicator for API compatibility, not a calibrated probability. The language model layer from the agreed hybrid design remains optional and disabled until deterministic checks are proven useful.

## Development and tests

From the project root:

```powershell
python -m pytest backend
```

To run the dashboard production build:

```powershell
cd frontend
npm run build
```

## Why DocuGuard can stand out

Existing tools already cover AST checks, docstring/signature drift, CI gates, optional AI, history and fix proposals. DocuGuard's first differentiator is the reviewer experience: show a changed behavior beside the exact stale claim, give both locations as evidence, state the rule's scope, and offer a correction preview for a human to accept.

Public projects reviewed for this MVP:

- [drift](https://github.com/pallaprolus/drift) — editor extension, CLI, GitHub Action and AST-based checks.
- [doc-drift-guard](https://github.com/melonusers/doc-drift-guard) — repository indexing and evidence-backed, optional AI analysis.
- [DocSentinel](https://github.com/DsChauhan08/docsentinel) — local CLI/TUI, history and finding review.
- [docugardener](https://github.com/docugardener/docugardener) — pull request checks with triage and override workflows.
- [driftguard](https://github.com/mahimathacker/driftguard) — SDK surface snapshots, example checks and SARIF output.
- [docsync](https://github.com/Dvorinka/docsync) — deterministic validation for configuration and repository references.
- [autodocs](https://github.com/msiric/autodocs) — maps changes to documentation and proposes verified replacements.
- [DocDrift GitHub Action](https://github.com/marketplace/actions/docdrift) — changed-symbol analysis and interactive remediation.

These links informed product positioning, not code reuse. DocuGuard does not copy their source code.

## Next customer-facing increments

1. Add rules for changed public function signatures and documented CLI options.
2. Add a side-by-side patch preview and export a Markdown review artifact.
3. Add opt-in local open-weight LLM explanations grounded only in deterministic evidence.
4. Add a GitHub Action after local accuracy and false-positive behavior are understood.

## Project layout

- `backend/app/analyzer.py` — Git revision reading, Python AST extraction, Markdown line parsing and the first drift rule.
- `backend/app/schemas.py` — Pydantic request/response models.
- `backend/app/main.py` — FastAPI endpoints.
- `backend/tests/` — rule and API tests.
- `frontend/src/` — React/Vite dashboard.
