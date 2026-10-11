"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, Bird, Fish, Flower2, KeyRound, Leaf, Power, Snowflake, Sun, XCircle, type LucideIcon } from "lucide-react";
import { PocketwatchLogo } from "@/components/ui/aero";
import { AuthError, LOGIN_PROFILES, safeNext, signIn, useSession } from "@/lib/auth";

// Nature "user pictures" in the spirit of XP's flower/frog/duck tiles.
const PICTURES: LucideIcon[] = [Fish, Leaf, Flower2, Bird, Snowflake, Sun];

// Windows XP welcome screen, Frutiger Aero edition: click your name, type your
// password, press the green arrow. "?" shows a password hint balloon.
export function LoginScreen() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const session = useSession();
  const [selected, setSelected] = React.useState<string | null>(null);
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [balloon, setBalloon] = React.useState<"hint" | "error" | null>(null);
  const [error, setError] = React.useState("");
  const [pending, setPending] = React.useState(false);
  const [off, setOff] = React.useState(false);
  const passwordRef = React.useRef<HTMLInputElement>(null);
  const emailRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => { if (session) router.replace(next); }, [session, next, router]);
  React.useEffect(() => { (selected === "other" ? emailRef : passwordRef).current?.focus(); }, [selected]);

  function choose(id: string, profileEmail = "") {
    if (selected === id) return;
    setSelected(id); setEmail(profileEmail); setPassword(""); setError(""); setBalloon(null);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!email.trim() || !password) { setError("Type your email and password, then press the green arrow."); setBalloon("error"); return; }
    setPending(true); setBalloon(null);
    try { await signIn(email, password); router.replace(next); }
    catch (err) {
      setError(err instanceof AuthError ? err.message : "Sign-in failed. Try again.");
      setBalloon("error"); setPassword(""); passwordRef.current?.focus();
    } finally { setPending(false); }
  }

  const passwordForm = (label: string, hint: string) => <form className="xp-login-form" onSubmit={submit}>
    {selected === "other" && <input ref={emailRef} className="xp-login-input" type="email" autoComplete="username" placeholder="you@pocketwatch.tech" aria-label="Email" value={email} onChange={e => { setEmail(e.target.value); setBalloon(null); }} />}
    <span className="xp-login-prompt">Type your password</span>
    <div className="xp-login-password">
      <input ref={passwordRef} className="xp-login-input" type="password" autoComplete="current-password" aria-label={`Password for ${label}`} value={password} onChange={e => { setPassword(e.target.value); setBalloon(null); }} disabled={pending} />
      <button type="submit" className="xp-login-gel xp-login-gel--go" aria-label="Sign in" disabled={pending}><ArrowRight size={16} strokeWidth={3} aria-hidden="true" /></button>
      <button type="button" className="xp-login-gel xp-login-gel--help" aria-label="Password hint" aria-expanded={balloon === "hint"} onClick={() => setBalloon(b => b === "hint" ? null : "hint")}>?</button>
    </div>
    {balloon && <div className="xp-balloon" role={balloon === "error" ? "alert" : "status"}>
      {balloon === "error"
        ? <><strong><XCircle size={15} aria-hidden="true" />Did you forget your password?</strong><p>{error}</p><p>Press the &ldquo;?&rdquo; button to see your password hint.</p></>
        : <><strong>Password hint</strong><p>{hint}</p></>}
    </div>}
  </form>;

  if (off) return <button type="button" className="xp-login-off" onClick={() => setOff(false)}>
    <span>It&rsquo;s now safe to turn off your computer.</span><small>(Click anywhere to come back.)</small>
  </button>;

  return <div className="xp-login" data-has-selection={selected !== null}>
    <div className="xp-login-sky" aria-hidden="true"><span className="xp-login-aurora" /><span className="xp-login-aurora xp-login-aurora--two" /><span className="xp-login-water" /></div>
    <div className="xp-login-bubbles" aria-hidden="true">{Array.from({ length: 9 }, (_, i) => <span key={i} />)}</div>
    <header className="xp-login-band xp-login-band--top" />
    <main className="xp-login-main">
      <section className="xp-login-brand">
        <div className="xp-login-wordmark">
          <PocketwatchLogo size={84} />
          <h1>Pocketwatch</h1>
        </div>
        <p className="xp-login-tagline">See what a purchase does to your next two years, before you make it.</p>
        <p>To begin, click your user name</p>
      </section>
      <div className="xp-login-divider" aria-hidden="true" />
      <section className="xp-login-users" aria-label="User accounts">
        {session === undefined ? null : <ul>
          {LOGIN_PROFILES.map((profile, i) => {
            const Picture = PICTURES[i % PICTURES.length];
            return <li key={profile.id} data-selected={selected === profile.id}>
              <button type="button" className="xp-login-user" onClick={() => choose(profile.id, profile.email)} aria-expanded={selected === profile.id}>
                <span className={`xp-login-picture xp-login-picture--${i % PICTURES.length}`} aria-hidden="true"><Picture size={28} strokeWidth={1.75} /></span>
                <span className="xp-login-name">{profile.name}<small>{selected === profile.id ? profile.email : "1 bank profile"}</small></span>
              </button>
              {selected === profile.id && passwordForm(profile.name, `Your first name in lowercase, then "-aero".`)}
            </li>;
          })}
          <li data-selected={selected === "other"}>
            <button type="button" className="xp-login-user" onClick={() => choose("other")} aria-expanded={selected === "other"}>
              <span className="xp-login-picture xp-login-picture--other" aria-hidden="true"><KeyRound size={26} strokeWidth={1.75} /></span>
              <span className="xp-login-name">Other user<small>Sign in with email</small></span>
            </button>
            {selected === "other" && passwordForm("your account", `Demo emails look like "jordan@pocketwatch.tech"; the password is the first name, then "-aero".`)}
          </li>
        </ul>}
      </section>
    </main>
    <footer className="xp-login-band xp-login-band--bottom">
      <button type="button" className="xp-login-turnoff" onClick={() => setOff(true)}>
        <span className="xp-login-power" aria-hidden="true"><Power size={18} strokeWidth={3} /></span>Turn off Pocketwatch
      </button>
      <p>After you sign in, you can ask about your own account.<br />Replay links you were texted open without signing in.</p>
    </footer>
  </div>;
}
