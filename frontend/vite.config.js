import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The same anti-framing policy applies in the development preview and production preview.
const securityHeaders = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "no-referrer",
  "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' http://127.0.0.1:8000 http://localhost:8000 http://127.0.0.1:8765 http://localhost:8765 https://*.supabase.co wss://*.supabase.co; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
};

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    headers: securityHeaders,
    // Keep local development same-origin so API requests avoid broad CORS rules.
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/security": "http://127.0.0.1:8000",
      "/privacy": "http://127.0.0.1:8000",
      "/analyze": "http://127.0.0.1:8000",
    },
  },
  preview: { host: "127.0.0.1", headers: securityHeaders },
});
