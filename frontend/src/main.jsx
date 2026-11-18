import React, { Component } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

// A rendering bug should produce a useful recovery screen instead of a blank page.
class AppErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <main role="alert" style={{ maxWidth: 640, margin: "12vh auto", padding: 32, color: "#f4f7fb", fontFamily: "system-ui, sans-serif" }}>
          <p style={{ color: "#91a7c4", letterSpacing: ".12em", fontSize: 12 }}>DOCUGUARD COULD NOT LOAD</p>
          <h1 style={{ fontSize: 32 }}>The workspace hit a snag.</h1>
          <p style={{ color: "#c4cfde", lineHeight: 1.6 }}>Refresh the page to try again. Your repository files are not changed by this screen.</p>
          <button type="button" onClick={() => window.location.reload()} style={{ padding: "12px 18px", border: 0, borderRadius: 10, background: "#78e0c2", color: "#09131f", fontWeight: 700, cursor: "pointer" }}>Refresh DocuGuard</button>
        </main>
      );
    }
    return this.props.children;
  }
}

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("The DocuGuard page is missing its root element.");

createRoot(rootElement).render(
  <React.StrictMode><AppErrorBoundary><App /></AppErrorBoundary></React.StrictMode>,
);
