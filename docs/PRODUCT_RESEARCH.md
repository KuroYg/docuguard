# Product research and positioning

**Reviewed:** 19 November 2026
**Scope:** documentation drift in software repositories, customer trust in automated maintenance, and the existing review workflow.

## What the evidence says

1. A 2024 empirical study examined more than 3,000 popular GitHub projects. It found at least one outdated code-element reference in 28.9% of the top-project sample and in 5.4% of the Google-project sample. In its top-1,000 subset, 19.2% of documents contained at least one stale code reference. The large difference between samples is a warning against presenting a single prevalence number as universal. The paper's detector matched code references in docs against code elements that disappeared from source. [Study and methods](https://link.springer.com/article/10.1007/s10664-023-10397-6)
2. An October 2026 preprint studied 29,669 AI-authored pull requests from 2,585 repositories. 63.2% changed code without a documentation co-change; refactors were at 77.5%. It defines this as a proxy for drift, not proof that a particular page is wrong. It also reports that drifted files were re-documented within 90 days less often (24% vs. 48%). These results are specific to the dataset and are not a general industry-wide rate. [Preprint and limitations](https://arxiv.org/abs/2610.27381)
3. Existing products already compare code and docs and may generate or open auto-fix pull requests. GitHub itself supports status checks, code-owner routing, and protected branches to put automated findings into a human-reviewed merge workflow. A new tool cannot stand out merely by claiming to detect drift or use AI. [Detail auto-fix workflow](https://docs.detail.dev/features/doc-fixes/), [GitHub pull request controls](https://docs.github.com/en/pull-requests/reference/managing-and-standardizing-pull-requests)
4. Google's developer documentation guidance frames docs around clear, consistent language for developers and practitioners. The practical implication for findings is to explain the mismatch in plain terms, point to verifiable evidence, and keep the suggested action easy to review. [Google developer documentation guide](https://developers.google.com/style/)

## Customer problems translated into product choices

| Customer problem | Product response |
| --- | --- |
| A real contradiction is hard to find across a large README/docs set | Search the complete tracked Markdown snapshot at the selected head, not only Markdown files in the diff. Preserve original line numbers and show both sides. |
| “Code changed but docs did not” creates noise when docs were not relevant | Keep this as a separate **review prompt**, never label it a proven defect. Only call something drift when a deterministic rule finds a contradictory documented fact. |
| AI summaries and auto-fixes are hard to trust | Deterministic rules own evidence and corrections. Optional local AI can explain a finding only after server-side validation. Never modify files automatically. |
| Repository access feels risky for a small utility | Analyze a local Git path, keep it read-only and loopback-bound, and keep source text and findings out of the hosted account database. |
| A finding without a next step adds more review work | Show exact code/doc line locations, the old and new fact, a copyable minimal replacement, and an explicit “you decide” state. |
| Automated tooling should fit existing reviews | Build toward a non-blocking GitHub status check/PR annotation so teams can adopt it before considering required checks. Don't make an advisory heuristic block merges. |

## DocuGuard's positioning

**Unique selling proposition:** *Proof before prose.* DocuGuard only calls a mismatch a finding when it can show the changed code fact and the exact stale documentation sentence together. It separates confirmed contradictions from softer “docs may deserve a look” review prompts, never edits files or opens PRs without a human, and keeps repository content on the developer's machine.

This is a focused differentiation to validate with users, not a claim that no competitor offers related features. Existing tools already detect several drift types and some automate pull requests. DocuGuard should win trust through evidence quality, cautious confidence, privacy by default, and a low-friction review—not by claiming broader coverage than the MVP supports.

## Changes made from the research

- Preserve the existing exact-evidence shipping-multiplier finding as the first supported contradiction rule.
- Keep “no docs changed” as a distinct informational review prompt; it must not inflate the confirmed-finding count or fail a CI check.
- Make the welcome screen and result copy explain the customer outcome and the limits of the current rule.
- Keep optional language-model output as a validated explanation layer, not a source of facts or edits.
- Document a future PR workflow as advisory-first, with human approval and measured false-positive rates before any merge gate.

## Validation questions for customer trials

- Can a reviewer verify a finding in under a minute from the two source locations?
- Are review prompts useful without being mistaken for confirmed drift?
- Which sources of truth matter most next: CLI flags, exported Python symbols, configuration defaults, environment variables, or API schema?
- How often do users accept, edit, or dismiss a suggestion? Track these only after a clear opt-in product decision and data-minimization review.
