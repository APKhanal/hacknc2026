"use client";

// Front-end-only demo login. NOT real security: the accounts below ship in the
// browser bundle and the session lives in localStorage.
//
// The shape mirrors Supabase Auth so it can be swapped in later without
// touching the UI: signIn -> supabase.auth.signInWithPassword, signOut ->
// supabase.auth.signOut, getSession -> supabase.auth.getSession, and
// customerId -> user.app_metadata.customer_id (set by an admin, not the user).
import { useEffect, useState } from "react";

export interface AuthUser { id: string; email: string; name: string; customerId: string }
export interface AuthSession { user: AuthUser; expiresAt: number }

interface DemoAccount extends AuthUser { password: string }

// One account per cached demo customer (data/cache/seeded).
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

export function getSession(): AuthSession | null {
  try {
    const session = JSON.parse(localStorage.getItem(SESSION_KEY) ?? "null") as AuthSession | null;
    if (!session?.user?.customerId || !(session.expiresAt > Date.now())) return null;
    return session;
  } catch { return null; }
}

export async function signIn(email: string, password: string): Promise<AuthSession> {
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
  try { localStorage.removeItem(SESSION_KEY); } catch { /* Nothing stored. */ }
  listeners.forEach(notify => notify());
}

/** Current session; `undefined` until the browser has been checked (avoids a login flash). */
export function useSession(): AuthSession | null | undefined {
  const [session, setSession] = useState<AuthSession | null | undefined>(undefined);
  useEffect(() => {
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
