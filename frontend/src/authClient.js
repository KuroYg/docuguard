import { createClient } from "@supabase/supabase-js";

// Only the Supabase URL and public anon key belong in a browser build. Never put
// the service-role key here; it bypasses database row-level security.
const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const hostedAuthReady = Boolean(url && anonKey);
export const supabase = hostedAuthReady
  ? createClient(url, anonKey, {
      auth: {
        // Keep account sessions in this tab instead of leaving a long-lived token
        // in localStorage on shared machines. The hosted seven-day limit remains
        // authoritative across devices.
        storage: window.sessionStorage,
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null;
