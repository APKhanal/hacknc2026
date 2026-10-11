"use client";

// Sign-in for the workspace. Two modes behind one interface (signIn / signOut / useSession):
//
// - Supabase Auth, when NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are set. Accounts are
//   created by `python -m data.supabase_setup`; each user's customer_id lives in app_metadata, which only
//   the server can change, so a user can't switch themselves to someone else's bank profile.
// - A local demo fallback otherwise (no network): the same six accounts, checked in the browser. NOT real
//   security; it keeps the app usable without a Supabase project.
import { useEffect, useState } from "react";
import type { Session, SupabaseClient, User } from "@supabase/supabase-js";

export interface AuthUser { id: string; email: string; name: string; customerId: string }
export interface AuthSession { user: AuthUser; expiresAt: number }

interface DemoAccount extends AuthUser { password: string }

// One account per cached Nessie customer (data/cache/seeded); mirrors data/supabase_setup.py.
export const DEMO_ACCOUNTS: DemoAccount[] = [
  { id: "demo-jordan", name: "Jordan", email: "jordan@pocketwatch.tech", password: "jordan-aero", customerId: "7b3e4794-645b-481b-b8d1-a7a1ebffee47" },
  { id: "demo-alex", name: "Alex", email: "alex@pocketwatch.tech", password: "alex-aero", customerId: "39b2bdb2-e13c-4734-8522-1e2d43df6d1f" },
  { id: "demo-blair", name: "Blair", email: "blair@pocketwatch.tech", password: "blair-aero", customerId: "62be185a-effc-4f17-bd5e-61b2336836e8" },
  { id: "demo-casey", name: "Casey", email: "casey@pocketwatch.tech", password: "casey-aero", customerId: "75414169-d39d-4cbe-aed5-765c496ccbb7" },
  { id: "demo-drew", name: "Drew", email: "drew@pocketwatch.tech", password: "drew-aero", customerId: "4ba43709-2dbc-483e-8ca4-cf1959052b71" },
  { id: "demo-ellis", name: "Ellis", email: "ellis@pocketwatch.tech", password: "ellis-aero", customerId: "27dc775c-a552-453f-831b-5cf060de367c" },
];

/** Public profile info for the user tiles on the login screen (no passwords). */
export const LOGIN_PROFILES: AuthUser[] = DEMO_ACCOUNTS.map(({ password: _password, ...user }) => user);

const SESSION_KEY = "pocketwatch.session.v1";
const SESSION_HOURS = 12;
const listeners = new Set<() => void>();

export class AuthError extends Error {}

// Next.js inlines NEXT_PUBLIC_* values at build time; the try keeps non-Next runtimes (tests) working.
function supabaseConfig(): { url: string; key: string } | null {
  try {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL, key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    return url && key ? { url, key } : null;
  } catch { return null; }
}

export const authMode: "supabase" | "demo" = supabaseConfig() ? "supabase" : "demo";

let client: Promise<SupabaseClient> | null = null;
function supabase(): Promise<SupabaseClient> {
  const config = supabaseConfig()!;
  client ??= import("@supabase/supabase-js").then(({ createClient }) =>
    createClient(config.url, config.key, { auth: { persistSession: true, autoRefreshToken: true, storageKey: "pocketwatch.auth" } }));
  return client;
}

function fromSupabase(session: Session | null): AuthSession | null {
  const user: User | undefined = session?.user;
  const customerId = user?.app_metadata?.customer_id;
  if (!session || !user || typeof customerId !== "string") return null;
  const name = typeof user.user_metadata?.name === "string" ? user.user_metadata.name
    : LOGIN_PROFILES.find(p => p.customerId === customerId)?.name ?? user.email ?? "You";
  return { user: { id: user.id, email: user.email ?? "", name, customerId }, expiresAt: (session.expires_at ?? 0) * 1000 };
}

/** Demo mode only (synchronous, from browser storage). In Supabase mode use useSession. */
export function getSession(): AuthSession | null {
  try {
    const session = JSON.parse(localStorage.getItem(SESSION_KEY) ?? "null") as AuthSession | null;
    if (!session?.user?.customerId || !(session.expiresAt > Date.now())) return null;
    return session;
  } catch { return null; }
}

export async function signIn(email: string, password: string): Promise<AuthSession> {
  if (authMode === "supabase") {
    let result;
    try { result = await (await supabase()).auth.signInWithPassword({ email: email.trim(), password }); }
    catch { throw new AuthError("Couldn't reach the sign-in service. Check your connection and try again."); }
    if (result.error) {
      throw new AuthError(result.error.status === 400 ? "Incorrect email or password." : "Sign-in failed. Try again in a moment.");
    }
    const session = fromSupabase(result.data.session);
    if (!session) {
      await (await supabase()).auth.signOut();
      throw new AuthError("This account isn't linked to a bank profile yet.");
    }
    return session;
  }
  const account = DEMO_ACCOUNTS.find(a => a.email.toLowerCase() === email.trim().toLowerCase());
  if (!account || account.password !== password) throw new AuthError("Incorrect email or password.");
  const { password: _password, ...user } = account;
  const session: AuthSession = { user, expiresAt: Date.now() + SESSION_HOURS * 3600_000 };
  try { localStorage.setItem(SESSION_KEY, JSON.stringify(session)); }
  catch { throw new AuthError("This browser blocked storage, so you can't stay signed in. Allow site data and try again."); }
  listeners.forEach(notify => notify());
  return session;
}

export async function signOut(): Promise<void> {
  if (authMode === "supabase") {
    try { await (await supabase()).auth.signOut(); } catch { /* Already signed out locally. */ }
    return;
  }
  try { localStorage.removeItem(SESSION_KEY); } catch { /* Nothing stored. */ }
  listeners.forEach(notify => notify());
}

/** Current session; `undefined` until it has been checked (avoids a login flash). */
export function useSession(): AuthSession | null | undefined {
  const [session, setSession] = useState<AuthSession | null | undefined>(undefined);
  useEffect(() => {
    if (authMode === "supabase") {
      let active = true, unsubscribe = () => {};
      supabase().then(sb => {
        if (!active) return;
        sb.auth.getSession().then(({ data }) => { if (active) setSession(fromSupabase(data.session)); },
          () => { if (active) setSession(null); });
        const { data } = sb.auth.onAuthStateChange((_event, next) => { if (active) setSession(fromSupabase(next)); });
        unsubscribe = () => data.subscription.unsubscribe();
      }, () => { if (active) setSession(null); });
      return () => { active = false; unsubscribe(); };
    }
    const update = () => setSession(getSession());
    update();
    listeners.add(update);
    window.addEventListener("storage", update);
    return () => { listeners.delete(update); window.removeEventListener("storage", update); };
  }, []);
  return session;
}

/** Only allow same-site paths as a post-login destination. */
export function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/?view=overview";
}
