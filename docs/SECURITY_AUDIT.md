# Security audit and safe-use guide

**Product:** DocuGuard preview with optional hosted accounts
**Last reviewed:** 19 November 2026

## Current security boundary

DocuGuard is designed for one user's local machine. Start FastAPI on `127.0.0.1`; the API also rejects non-loopback peers and unexpected browser origins on state-changing requests. CORS permits only the local Vite origins used by this project. The frontend uses frame-denial and a restrictive Content Security Policy. The API returns anti-framing, no-sniff, no-referrer, and no-store headers.

This is **not an encrypted firewall**. HTTP traffic over localhost is not TLS-encrypted, and loopback restrictions do not isolate DocuGuard from other programs running as your Windows user. Do not bind the API or Vite server to `0.0.0.0`, expose port 8000 on a LAN, or treat CORS as authentication. Supabase email/password sign-in is optional until configured. If required, the API validates each analysis bearer token with the provider. This path-based local Git API must never be exposed remotely.

## Data and permissions

- The folder path and Git refs are the only analysis inputs. The server uses the current Windows account's filesystem permissions; it does not request elevation or grant itself access.
- Git is invoked with argument arrays, bounded execution time, and no shell. Analysis reads commit objects and does not write to the selected repository.
- The API does not retain repository results in a database. It does not log request bodies or excerpts. Clear the tab to remove visible in-memory analysis state.
- Do not enter repositories you are not authorized to inspect. Prefer a normal user account and only the folder permissions you need.

## AI and secrets

- Local AI is disabled by default. When enabled, only bounded evidence excerpts for deterministic findings are sent to a loopback Ollama endpoint.
- The server refuses remote model URLs, validates structured model output, rejects new numeric claims or changed corrections, and falls back to deterministic evidence on errors.
- DocuGuard does not require an API key. Never place a token or private key in React code, Vite variables, screenshots, or a public repository. Keep local environment files out of Git.

## XSS, CSRF, and clickjacking

- XSS: findings and repository excerpts are rendered as React text, not injected HTML. Keep `dangerouslySetInnerHTML` out of the client. The frontend Content Security Policy limits script, frame, and network sources.
- CSRF: hosted access tokens are held in tab session storage and sent as explicit bearer headers, not ambient cookies. State-changing API requests require an approved local `Origin`; CORS and loopback-peer checks add boundaries. They are not authentication. Do not switch to cookie authentication without SameSite and CSRF-token controls.
- Clickjacking: frontend and API responses deny framing with `frame-ancestors 'none'` and `X-Frame-Options: DENY`.

## Third-party component audit

The browser bundle uses React/React DOM, Lucide React, Vite, and Supabase JS Auth when configured. There are no analytics, ads, remote fonts, hosted AI, or telemetry SDKs. Run `npm audit` when dependencies change and inspect the lockfile diff before release. Ollama is an optional separate local program, not bundled into DocuGuard.

## Release checklist

1. Confirm the API and frontend bind only to loopback.
2. Check browser dependencies and backend packages for known vulnerabilities.
3. Scan the staged diff for keys, tokens, passwords, and private repository excerpts.
4. Confirm privacy, terms, cookie, and security pages still match the actual data flow.
5. Exercise XSS text rendering, rejected cross-origin POSTs, model timeout/malformed output fallback, and the clear/deletion controls.
6. Do not announce encryption, firewall protection, legal compliance, or hosted security until those controls actually exist and are reviewed.
