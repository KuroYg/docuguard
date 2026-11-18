import { useEffect, useState } from "react";
import { Activity, ArrowLeftRight, BookOpen, Check, CircleHelp, Clipboard, FileCode2, FileText, FolderGit2, LoaderCircle, LockKeyhole, Play, RotateCcw, ShieldCheck, Trash2 } from "lucide-react";
import { PolicyModal } from "./LegalContent.jsx";
import { hostedAuthReady, supabase } from "./authClient.js";

// Production serves the dashboard and API from one local origin; Vite proxies these paths in development.
const API = import.meta.env.VITE_API_URL || "";
const repoPlaceholder = "C:\\Users\\you\\projects\\my-python-app";

function Evidence({ title, icon: Icon, evidence, tone }) {
  return <section className={`evidence-card ${tone || ""}`} aria-label={`${title}: ${evidence.path}`}>
    <div className="evidence-heading"><Icon size={14} aria-hidden="true" />{title}<span className="file-location">{evidence.path}:{evidence.line ?? "—"}</span></div>
    <pre>{evidence.excerpt}</pre>
  </section>;
}

function FindingCard({ finding, index }) {
  const [copied, setCopied] = useState(false);
  async function copySuggestion() {
    try {
      await navigator.clipboard.writeText(finding.suggested_correction);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }
  return <article className="finding">
    <div className="finding-top"><div className="finding-title"><span className="finding-number">{String(index + 1).padStart(2, "0")}</span><div><h3>{finding.title}</h3><p>{finding.summary}</p></div></div><span className="rule-badge">EVIDENCE MATCH</span></div>
    <div className="evidence-grid"><Evidence title="CURRENT CODE" icon={FileCode2} evidence={finding.code_evidence} /><Evidence title="DOCUMENTATION" icon={FileText} evidence={finding.documentation_evidence} tone="docs" /></div>
    <div className="correction"><div><span className="field-label">SUGGESTED CORRECTION</span><p>{finding.suggested_correction}</p></div><button className="copy-button" type="button" onClick={copySuggestion} aria-label="Copy suggested correction">{copied ? <Check size={14} /> : <Clipboard size={14} />}{copied ? "Copied" : "Copy"}</button></div>
  </article>;
}

export default function App() {
  const [repo, setRepo] = useState("");
  const [base, setBase] = useState("HEAD~1");
  const [head, setHead] = useState("HEAD");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [policy, setPolicy] = useState("");
  const [showIntro, setShowIntro] = useState(() => !sessionStorage.getItem("docuguard-intro-seen"));
  const [showNotice, setShowNotice] = useState(() => !sessionStorage.getItem("docuguard-notice-seen"));
  const [authStatus, setAuthStatus] = useState("Hosted accounts are not configured");
  const [session, setSession] = useState(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [authMessage, setAuthMessage] = useState("");

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => setSession(nextSession));
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    // Health check is informational. The actual analysis request handles an unavailable API too.
    fetch(`${API}/health`).catch(() => setError("The local analysis service is offline. Start the API, then try again."));
    if (hostedAuthReady) setAuthStatus("Hosted login configured · server protection depends on API settings");
  }, []);

  function dismissIntro() {
    sessionStorage.setItem("docuguard-intro-seen", "1");
    setShowIntro(false);
  }

  async function analyze(baseRef, headRef) {
    setBusy(true); setError("");
    try {
      const accessToken = session?.access_token;
      const response = await fetch(`${API}/analyze/repository`, {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json", ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
        body: JSON.stringify({ repository_path: repo, base_ref: baseRef, head_ref: headRef }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || `Analysis failed (${response.status}). Check the folder and Git references.`);
      setResult(payload);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Analysis failed. Please retry.");
    } finally { setBusy(false); }
  }

  async function submitAuth(event) {
    event.preventDefault(); setAuthMessage("");
    if (!supabase) return setAuthMessage("Hosted account service is not configured yet. Set the Vite public Supabase URL and anon key, then restart the dashboard.");
    if (authMode === "signup" && !termsAccepted) return setAuthMessage("Please accept the terms and privacy policy to create an account.");
    try {
      const result = authMode === "signup"
        ? await supabase.auth.signUp({ email: email.trim(), password })
        : await supabase.auth.signInWithPassword({ email: email.trim(), password });
      if (result.error) throw result.error;
      setAuthMessage(authMode === "signup" && !result.data.session ? "Check your email to verify the account, then sign in." : "Signed in successfully.");
      if (result.data.session) setAuthOpen(false);
    } catch (err) { setAuthMessage(err?.message || "Sign-in failed. Try again in a moment."); }
  }

  async function endAllSessions() {
    if (!supabase || !session) return;
    setAuthMessage("");
    try {
      const { error: signOutError } = await supabase.auth.signOut({ scope: "global" });
      if (signOutError) throw signOutError;
      setSession(null); setAuthMessage("Signed out here. Other devices will be signed out when their short-lived access token expires or they next refresh.");
    } catch (err) { setAuthMessage(err?.message || "Could not confirm server sign-out. Your current session remains active."); }
  }

  function clearSession() {
    setRepo(""); setBase("HEAD~1"); setHead("HEAD"); setResult(null); setError("");
  }

  async function requestDeletion() {
    clearSession();
    if (session && supabase) {
      // Only the signed-in customer can create a deletion request for their own account;
      // database row-level security enforces the matching auth.uid() on the server.
      // The database RPC derives the account ID from the verified session and
      // makes repeated clicks idempotent; the browser cannot choose request status.
      const { error: deletionError } = await supabase.rpc("request_account_deletion");
      if (deletionError) setError("This tab was cleared, but the account deletion request could not be saved. Please sign in and retry.");
      else setError("Your tab was cleared. The account deletion request was recorded; account removal still requires the operator workflow described in the privacy policy.");
      return;
    }
    try { await fetch(`${API}/privacy/deletion-request`, { method: "POST" }); }
    catch { setError("This tab was cleared. The local service could not confirm its no-storage status while offline."); }
  }

  return <div className="app-shell">
    <aside className="rail" aria-label="DocuGuard"><div className="brand-mark"><ShieldCheck size={19} /></div><div className="rail-rule" /><button className="rail-icon active" aria-label="Analysis"><Activity size={17} /></button><button className="rail-icon" aria-label="How to use" onClick={() => setShowIntro(true)}><CircleHelp size={17} /></button><div className="rail-bottom"><LockKeyhole size={15} /></div></aside>
    <div className="workspace">
      <header className="topbar"><div className="breadcrumb"><span>WORKSPACE</span><span className="slash">/</span><b>Documentation review</b></div><div className="topbar-right"><span className="local-pill"><span className="pulse" />LOCAL ANALYSIS</span>{session ? <button className="account-button" onClick={endAllSessions} title="End sessions on all devices"><LockKeyhole size={13} />Account · End all sessions</button> : <button className="account-button" onClick={() => { setAuthOpen(true); setAuthMessage(""); }}>{hostedAuthReady ? "Sign in" : "Accounts off"}</button>}</div></header>
      <main className="content">
        <section className="hero"><div className="eyebrow"><span className="eyebrow-dot" />PROOF BEFORE PROSE</div><h1>Keep your docs<br /><span>in sync with code.</span></h1><p>When a code change contradicts your README, DocuGuard shows the exact code line, the stale sentence, and a minimal correction. You verify it; DocuGuard never edits your files for you.</p></section>
        <section className="analysis-panel" aria-labelledby="analysis-title"><div className="panel-title-row"><div><p className="panel-kicker">START A REVIEW</p><h2 id="analysis-title">Choose what to compare</h2></div><p className="privacy-note"><LockKeyhole size={13} />Repo stays on this machine</p></div>
          <label className="field-label" htmlFor="repo-path">PYTHON REPOSITORY FOLDER</label><div className="repo-input"><FolderGit2 size={16} /><input id="repo-path" value={repo} onChange={e => setRepo(e.target.value)} placeholder={repoPlaceholder} autoComplete="off" /><span className="python-tag"><span />PYTHON</span></div>
          <div className="ref-grid"><div><label className="field-label" htmlFor="base-ref">BASE VERSION</label><div className="ref-input"><input id="base-ref" value={base} onChange={e => setBase(e.target.value)} /></div></div><span className="ref-arrow"><ArrowLeftRight size={15} /></span><div><label className="field-label" htmlFor="head-ref">COMPARE WITH</label><div className="ref-input"><input id="head-ref" value={head} onChange={e => setHead(e.target.value)} /></div></div></div>
          <div className="panel-actions"><button className="primary-button" type="button" disabled={busy || !repo.trim() || (hostedAuthReady && !session)} onClick={() => analyze(base, head)}>{busy ? <LoaderCircle className="spin" size={15} /> : <Play size={14} />}{busy ? "Reviewing…" : "Review changes"}</button><button className="text-button" type="button" disabled={!result && !repo && !error} onClick={clearSession}><RotateCcw size={14} />Clear</button><span className="scope-note">READ-ONLY · NO FILES CHANGED</span></div>
        </section>
        {error && <div className="error-banner" role="alert"><CircleHelp size={16} />{error}</div>}
        {!result && !error && <div className="empty-state"><span className="empty-icon"><BookOpen size={17} /></span><div><b>Evidence first. You stay in control.</b><p>Every finding includes a code line, a documentation line, and a proposed correction for your review.</p></div></div>}
        {result && <section className="results" aria-live="polite"><div className="results-header"><div><p className="panel-kicker">REVIEW COMPLETE · {result.repository}</p><h2>{result.findings.length ? `${result.findings.length} evidence-backed ${result.findings.length === 1 ? "finding" : "findings"}` : result.review_prompts?.length ? "One thing to review" : "No supported drift found"}</h2></div><span className={`result-status ${result.findings.length || result.review_prompts?.length ? "warning" : "clear"}`}><span />{result.findings.length ? "PROOF FOUND" : result.review_prompts?.length ? "REVIEW PROMPT" : "NO MATCH FOUND"}</span></div>
          <div className="stats-row"><div className="stat"><span>FILES CHECKED</span><b>{result.changed_files.length}</b></div><div className="stat"><span>FINDINGS</span><b>{result.findings.length}</b></div><div className="stat"><span>AI REVIEW</span><b>{result.ai_validation?.status || "disabled"}</b></div></div>
          {result.findings.map((finding, index) => <FindingCard key={`${finding.code_evidence.path}:${finding.code_evidence.line}:${index}`} finding={finding} index={index} />)}
          {result.review_prompts?.map((prompt, i) => <div className="review-prompt" key={i}><CircleHelp size={16} /><div><b>Worth a quick look</b><p>{prompt}</p></div></div>)}
          <div className="result-foot"><div className="changed-files"><FolderGit2 size={13} /><span>{result.changed_files.join(" · ") || "No changed files"}</span></div><span className="human-review"><Check size={13} />Suggestions are yours to review</span></div>
          <p className="note">{result.ai_validation?.message || "Deterministic evidence remains the source of truth."}</p>{result.notes?.map((note, i) => <p className="note" key={i}>{note}</p>)}
        </section>}
        <footer className="footer"><span>DOCUGUARD · LOCAL-FIRST REVIEW</span><nav aria-label="Policies"><button onClick={() => setPolicy("privacy")}>Privacy</button><button onClick={() => setPolicy("terms")}>Terms</button><button onClick={() => setPolicy("cookies")}>Cookies</button><button onClick={() => setPolicy("security")}>Security guide</button><button onClick={clearSession}><RotateCcw size={12} />Clear this session</button>{session && <button onClick={requestDeletion}><Trash2 size={12} />Request account deletion</button>}</nav></footer>
      </main>
      {showNotice && <aside className="privacy-banner" aria-label="Privacy notice"><span><LockKeyhole size={15} />No tracking cookies or ads. Inputs remain in this tab for now.</span><button onClick={() => { sessionStorage.setItem("docuguard-notice-seen", "1"); setShowNotice(false); }}>Continue</button><button className="banner-link" onClick={() => setPolicy("cookies")}>Cookie policy</button></aside>}
      {showIntro && <div className="dialog-backdrop"><section className="welcome-dialog" role="dialog" aria-modal="true" aria-labelledby="welcome-title"><div className="welcome-icon"><ShieldCheck size={24} /></div><p className="section-label">WELCOME TO DOCUGUARD</p><h2 id="welcome-title">Documentation drift,<br />with proof.</h2><p>When code changes but docs do not, DocuGuard finds a mismatch and points to both sides. You decide what to update.</p><div className="welcome-steps"><div><span>01</span><b>Compare Git versions</b><small>Choose a Python repository and two refs.</small></div><div><span>02</span><b>Inspect the evidence</b><small>Review exact code and Markdown lines.</small></div><div><span>03</span><b>Apply only what you trust</b><small>Suggestions are optional; your files stay untouched.</small></div></div><div className="account-note"><LockKeyhole size={15} /><span>{authStatus}. Repository files stay on this machine; account records contain only identity and security status.</span></div><div className="welcome-actions"><button className="primary-button" onClick={dismissIntro}><Play size={14} />Start a repository review</button></div></section></div>}
      {authOpen && <div className="dialog-backdrop"><section className="document-dialog auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-title"><div className="dialog-heading"><div><p className="section-label">SECURE ACCOUNT</p><h2 id="auth-title">{authMode === "signin" ? "Sign in to DocuGuard" : "Create your account"}</h2></div><button className="icon-button" onClick={() => setAuthOpen(false)} aria-label="Close sign in">×</button></div>{hostedAuthReady ? <form className="auth-form" onSubmit={submitAuth}><label>Email address<input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} /></label><label>Password<input type="password" autoComplete={authMode === "signin" ? "current-password" : "new-password"} minLength={10} required value={password} onChange={e => setPassword(e.target.value)} /></label>{authMode === "signup" && <label className="consent-row"><input type="checkbox" checked={termsAccepted} onChange={e => setTermsAccepted(e.target.checked)} /><span>I agree to the <button type="button" onClick={() => setPolicy("terms")}>Terms</button> and have read the <button type="button" onClick={() => setPolicy("privacy")}>Privacy Policy</button>.</span></label>}<button className="primary-button" type="submit">{authMode === "signin" ? "Sign in" : "Create account"}</button><button className="text-button" type="button" onClick={() => { setAuthMode(authMode === "signin" ? "signup" : "signin"); setAuthMessage(""); }}>{authMode === "signin" ? "New here? Create an account" : "Already registered? Sign in"}</button></form> : <p className="auth-message">Hosted accounts are not configured yet. Set the project URL and public publishable key, then rebuild the dashboard.</p>}{authMessage && <p className="auth-message" role="status">{authMessage}</p>}<p className="auth-caption">Sessions are managed by the hosted identity provider. The API checks the bearer token before analyzing a repository.</p></section></div>}
      {policy && <PolicyModal name={policy} onClose={() => setPolicy("")} />}
    </div>
  </div>;
}
