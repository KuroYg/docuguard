# Public release and hosting plan

## Two meanings of “public”

DocuGuard can be published as public source code today after the normal repository review. The working product in this branch is still a **local-first desktop-style tool**: the analysis API reads a Git folder on the same computer and rejects non-loopback network connections.

That product cannot be turned into a useful public website by uploading the current dashboard to Vercel. A visitor's local folder path is not available to a remote server, and opening the path-based API to the internet would expose the server filesystem. Do not deploy `backend/app/main.py` as a public API, even with Supabase login switched on.

## Current public-ready path

- Publish the source on GitHub and use the included CI workflow to verify backend tests and the frontend build on each pull request.
- Customers can install the root GitHub Action in a repository workflow. It runs in the customer's GitHub runner with `contents: read`, writes the review summary to that run, and sends no source to DocuGuard.
- Customers run the local launcher from their own machine. Repository contents stay local.
- Vercel, Render, and a public Supabase database are not required for local use or the customer-run Action.

## Hosted product path

For a real hosted service, replace the folder-path workflow with a GitHub App integration. Customers install the app on selected repositories. The app should accept signed pull-request webhooks, fetch only authorized changed files with short-lived read-only access, enforce account and repository ownership, and run bounded jobs in isolated workers. Do not accept filesystem paths, arbitrary clone URLs, or user-controlled server paths in public endpoints. Keep source and findings ephemeral unless a customer explicitly opts into storage.

Once that architecture exists, the provider setup is:

1. **GitHub** — public source repository, CI checks, and a GitHub App registration. Start with read-only repository contents and pull-request metadata. Add write permissions only for a specific feature such as publishing a check result; request no broad organization permissions.
2. **Vercel** — static React dashboard and product site. Configure the production dashboard URL and a server API URL only after the hosted backend exists. Keep Supabase secret keys and GitHub App private keys out of Vite/browser environment variables.
3. **Supabase** — account sign-in and minimal account/installation records. Apply migrations, verify row-level security, configure production auth URLs, backups, abuse limits and a tested restore before accepting customers.
4. **Render** — Python API and isolated worker service. Configure health checks, HTTPS, private networking where available, deployment secrets, resource limits and alert routing. Add a managed queue before enabling sustained background analysis.

The user already has GitHub, Vercel and Supabase accounts. **Render is the additional host account needed for the recommended future hosted backend.** GitHub App registration is done inside GitHub and does not require a separate provider account. A hosted queue may add another service/account later; choose it after measuring workload rather than adding it to the initial setup.

## Release gates

Before a public hosted launch, complete and verify all of the following:

- Authenticated GitHub App installation and signed webhook verification.
- Per-customer repository authorization, rate limits, request size limits and safe job cancellation.
- Isolated analysis workers with no arbitrary filesystem or network fetch surface.
- Production HTTPS origins and API CORS policy, secret storage and rotation.
- Supabase RLS and deletion flows, backup/restore drill, alert delivery, and session expiry.
- End-to-end tests using a staging GitHub App and staging Supabase project.
- Load tests for the intended concurrency, including worker saturation and provider failure recovery.

The existing Supabase project has the account migration applied and ignored local environment files configured. The provider API connectivity and full sign-up/sign-in round trip still need a live verification. No Vercel or Render deployment is configured, and no hosted GitHub App exists yet. Do not describe the service as hosted or customer-ready until those gates pass.
