# Privacy policy

**Product:** DocuGuard preview with optional hosted accounts
**Last updated:** 19 November 2026

## What DocuGuard handles

The preview has no active hosted account service unless the operator configures Supabase. When configured, Supabase Auth processes the email and password needed to create and secure an account. The account database stores a random user ID, account status, creation time, and deletion request. It does not store repository source, local folder paths, Git refs, or analysis results. The dashboard stores the sign-in session in the current browser tab's session storage.

Repository analysis remains local: the browser sends a local folder path and Git refs to the local API, which reads Git objects using the permissions of the Windows account running it. It does not modify the repository. Do not enable a hosted API for this path-based analyzer; a separate isolated repository import and worker design is needed first.

## Optional local AI

AI review is off by default. If enabled, the API can send bounded code and documentation excerpts for existing findings to an Ollama endpoint on the same computer. The server refuses non-loopback AI endpoints and validates model output before returning it. If the model is absent or fails, deterministic findings remain.

## Storage and sharing

The optional hosted account database stores only account metadata and deletion requests; it does not store analysis history. DocuGuard does not set cookies, use analytics, or load remote fonts or scripts. The only clipboard access happens when you select **Copy suggestion**. Supabase is the identity provider when configured.

## Your choices and deletion

Use **Clear this session** to erase repository paths, revisions, messages, and findings held in the current tab. A signed-in customer may submit an account deletion request; it is stored against their account and requires a trusted operator workflow to complete. The preview does not automatically delete the hosted Auth identity yet. Your source repository is not deleted by either action.

## Security limits

The local API accepts loopback connections only and checks browser origins for state-changing requests. If hosted authentication is configured and required, repository analysis requires a provider-verified bearer token. Localhost HTTP is not TLS encryption and does not protect against other software running as your Windows user. The Git path API is not safe for remote deployment.

## Contact and accuracy

No support mailbox is configured. This page describes preview behavior; it is not a claim of legal compliance and must be reviewed for the actual operator and jurisdictions before a hosted launch. Hosted services are inactive until setup described in `HOSTED_OPERATIONS.md` is complete.
